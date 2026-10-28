"""WebSocket API used by the Lovelace card."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


def _coord(hass: HomeAssistant):
    return hass.data.get(DOMAIN, {}).get("coordinator")


@callback
def async_register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_favorite)
    websocket_api.async_register_command(hass, ws_refresh)


@websocket_api.websocket_command({vol.Required("type"): "skoda_stock/list"})
@callback
def ws_list(hass, connection, msg):
    coord = _coord(hass)
    if coord is None:
        connection.send_error(msg["id"], "not_loaded", "Škoda Stock is not set up")
        return
    connection.send_result(msg["id"], coord.snapshot())


@websocket_api.websocket_command({
    vol.Required("type"): "skoda_stock/favorite",
    vol.Required("vin"): str,
    vol.Required("favorite"): bool,
})
@websocket_api.async_response
async def ws_favorite(hass, connection, msg):
    coord = _coord(hass)
    if coord is None:
        connection.send_error(msg["id"], "not_loaded", "Škoda Stock is not set up")
        return
    await coord.async_set_favorite(msg["vin"], msg["favorite"])
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command({vol.Required("type"): "skoda_stock/refresh"})
@websocket_api.async_response
async def ws_refresh(hass, connection, msg):
    coord = _coord(hass)
    if coord is None:
        connection.send_error(msg["id"], "not_loaded", "Škoda Stock is not set up")
        return
    await coord.async_manual_refresh()
    connection.send_result(msg["id"], {"ok": True})
