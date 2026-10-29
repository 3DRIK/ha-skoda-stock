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

from .api import SkodaStockError, build_link, fetch_all, fetch_detail
from .const import (CONF_INCLUDE_DEMO, CONF_INTERVAL_HOURS, CONF_LINK_TEMPLATE,
                    CONF_MAX_KM, CONF_MAX_PRICE, CONF_MODELS, DEFAULT_INTERVAL_HOURS,
                    DEFAULT_MODELS, DETAIL_DELAY, DETAIL_NEW_CAP, DETAIL_RETRY_HOURS,
                    DOMAIN, EVT_NEW, EVT_UPDATED, STORAGE_VERSION)
from .engine import (apply_update, car_view, compute_stats, merge_equipment,
                     missing_equipment, new_db, parse_equipment, used_catalog)

_LOGGER = logging.getLogger(__name__)


class SkodaStockCoordinator(DataUpdateCoordinator[dict]):
    """Polls the Škoda stock API and keeps history, equipment and favorites."""

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
        self._detail_task: asyncio.Task | None = None

    def link(self, car: dict) -> str:
        return build_link(car, self.link_template)

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if stored:
            self.db = {**new_db(), **stored}

    # ------------------------------------------------------------ details
    async def _fetch_details(self, vins: list[str]) -> int:
        """Fetch equipment for the given cars (sequentially, politely). Returns successes."""
        session = async_get_clientsession(self.hass)
        ok = 0
        for i, vin in enumerate(vins):
            rec = self.db["cars"].get(vin)
            if not rec:
                continue
            now = dt_util.utcnow().isoformat()
            rec["equip_attempt"] = now
            try:
                parsed = parse_equipment(await fetch_detail(session, rec["car"]["id"]))
            except SkodaStockError as err:
                _LOGGER.debug("Detail fetch failed for %s: %s", vin, err)
                parsed = None
            if parsed:
                merge_equipment(self.db, vin, parsed[0], parsed[1], now)
                ok += 1
            if i < len(vins) - 1:
                await asyncio.sleep(DETAIL_DELAY)
        return ok

    def _schedule_details(self) -> None:
        if self._detail_task and not self._detail_task.done():
            return
        if not missing_equipment(self.db, dt_util.utcnow().isoformat(), DETAIL_RETRY_HOURS, 1):
            return
        self._detail_task = self.config_entry.async_create_background_task(
            self.hass, self._detail_loop(), f"{DOMAIN}_details")

    async def _detail_loop(self) -> None:
        try:
            while True:
                vins = missing_equipment(self.db, dt_util.utcnow().isoformat(), DETAIL_RETRY_HOURS, 20)
                if not vins:
                    break
                await self._fetch_details(vins)
                await self._store.async_save(self.db)
                self.hass.bus.async_fire(EVT_UPDATED)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Equipment background fetch failed")

    async def async_fetch_missing_details(self) -> None:
        """Service: retry equipment for all cars lacking it right now."""
        for rec in self.db["cars"].values():
            if not rec.get("equipment"):
                rec.pop("equip_attempt", None)
        self._schedule_details()

    # ------------------------------------------------------------- update
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

        # Fetch equipment for freshly announced cars first, so their alert can list packages.
        new_vins = [p["vin"] for k, p in events if k == EVT_NEW][:DETAIL_NEW_CAP]
        new_vins = [v for v in new_vins if not self.db["cars"][v].get("equipment")]
        if new_vins:
            await self._fetch_details(new_vins)
        for kind, data in events:
            eq = self.db["cars"].get(data["vin"], {}).get("equipment")
            if kind == EVT_NEW and eq and eq["packages"]:
                names = [p["t"] for p in eq["packages"]]
                data["packages"] = names
                data["message"] += " · Balíky: " + ", ".join(names)

        await self._store.async_save(self.db)
        for kind, data in events:
            self.hass.bus.async_fire(kind, data)
        self.hass.bus.async_fire(EVT_UPDATED)
        self._schedule_details()
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
            "catalog": used_catalog(self.db),
            "updated_at": self._last_fetch.isoformat() if self._last_fetch else None,
            "interval_hours": self.interval_hours,
        }
