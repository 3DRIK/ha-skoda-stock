"""Data coordinator."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import SkodaStockError, build_link, fetch_all
from .const import (CONF_INCLUDE_DEMO, CONF_INTERVAL_HOURS, CONF_LINK_TEMPLATE,
                    CONF_MAX_KM, CONF_MAX_PRICE, CONF_MODELS, DEFAULT_INTERVAL_HOURS,
                    DEFAULT_MODELS, DOMAIN, EVT_UPDATED, STORAGE_VERSION)
from .engine import apply_update, car_view, compute_stats, new_db

_LOGGER = logging.getLogger(__name__)


class SkodaStockCoordinator(DataUpdateCoordinator[dict]):
    """Polls the Škoda stock API and keeps history + favorites."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        opts = entry.options
        self.models: list[str] = list(opts.get(CONF_MODELS) or DEFAULT_MODELS)
        self.interval_hours = int(opts.get(CONF_INTERVAL_HOURS) or DEFAULT_INTERVAL_HOURS)
        self.flt = {
            "max_price": opts.get(CONF_MAX_PRICE) or 0,
            "max_km": opts.get(CONF_MAX_KM) or 0,
            "include_demo": opts.get(CONF_INCLUDE_DEMO, True),
        }
        self.link_template: str = opts.get(CONF_LINK_TEMPLATE) or ""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, config_entry=entry,
            update_interval=timedelta(hours=self.interval_hours),
        )
        self._store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.db: dict = new_db()
        self._last_fetch = None

    def link(self, car: dict) -> str:
        return build_link(car, self.link_template)

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if stored:
            self.db = {**new_db(), **stored}

    async def _async_update_data(self) -> dict:
        try:
            current = await fetch_all(async_get_clientsession(self.hass), self.models)
        except SkodaStockError as err:
            raise UpdateFailed(str(err)) from err
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"Network error: {err}") from err

        now = dt_util.utcnow()
        self._last_fetch = now
        events = apply_update(self.db, current, self.models, now.isoformat(), self.flt, self.link)
        await self._store.async_save(self.db)
        for evt, data in events:
            self.hass.bus.async_fire(evt, data)
        self.hass.bus.async_fire(EVT_UPDATED)
        return compute_stats(self.db, now, self.link)

    async def async_manual_refresh(self) -> None:
        if self._last_fetch and dt_util.utcnow() - self._last_fetch < timedelta(minutes=10):
            _LOGGER.warning("Refresh skipped: last fetch was less than 10 minutes ago")
            return
        await self.async_refresh()

    async def async_set_favorite(self, vin: str, favorite: bool) -> None:
        favs = set(self.db.get("favorites", []))
        if favorite:
            favs.add(vin)
        else:
            favs.discard(vin)
        self.db["favorites"] = sorted(favs)
        await self._store.async_save(self.db)
        self.async_set_updated_data(compute_stats(self.db, dt_util.utcnow(), self.link))
        self.hass.bus.async_fire(EVT_UPDATED)

    def snapshot(self) -> dict:
        favs = set(self.db.get("favorites", []))
        cars = [car_view(v, r, favs, self.link) for v, r in self.db["cars"].items()]
        cars.sort(key=lambda c: c.get("order", 0))
        return {
            "cars": cars,
            "updated_at": self._last_fetch.isoformat() if self._last_fetch else None,
            "interval_hours": self.interval_hours,
        }
