"""Škoda Stock – track new Škoda stock offers in Slovakia."""
from __future__ import annotations

from pathlib import Path

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from . import websocket
from .const import CARD_FILE, CARD_URL, DOMAIN, VERSION
from .coordinator import SkodaStockCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
FAV_SCHEMA = vol.Schema({vol.Required("vin"): cv.string})


def _coordinator(hass: HomeAssistant) -> SkodaStockCoordinator:
    coord = hass.data.get(DOMAIN, {}).get("coordinator")
    if coord is None:
        raise ServiceValidationError("Škoda Stock is not set up")
    return coord


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    websocket.async_register(hass)

    js = Path(__file__).parent / "frontend" / CARD_FILE
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(js), False)])
    add_extra_js_url(hass, f"{CARD_URL}?v={VERSION}")

    async def refresh(call: ServiceCall) -> None:
        await _coordinator(hass).async_manual_refresh()

    async def add_favorite(call: ServiceCall) -> None:
        await _coordinator(hass).async_set_favorite(call.data["vin"], True)

    async def remove_favorite(call: ServiceCall) -> None:
        await _coordinator(hass).async_set_favorite(call.data["vin"], False)

    async def fetch_equipment(call: ServiceCall) -> None:
        await _coordinator(hass).async_fetch_missing_details()

    hass.services.async_register(DOMAIN, "refresh", refresh)
    hass.services.async_register(DOMAIN, "fetch_equipment", fetch_equipment)
    hass.services.async_register(DOMAIN, "add_favorite", add_favorite, schema=FAV_SCHEMA)
    hass.services.async_register(DOMAIN, "remove_favorite", remove_favorite, schema=FAV_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = SkodaStockCoordinator(hass, entry)
    await coordinator.async_load()
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN]["coordinator"] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop("coordinator", None)
    return ok


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
