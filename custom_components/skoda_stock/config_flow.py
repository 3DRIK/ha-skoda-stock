"""Config + options flow."""
from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (BooleanSelector, NumberSelector,
                                            NumberSelectorConfig, NumberSelectorMode,
                                            SelectSelector, SelectSelectorConfig,
                                            SelectSelectorMode, TextSelector)

from .api import SkodaStockError, fetch_page
from .const import (CONF_INCLUDE_DEMO, CONF_INTERVAL_HOURS, CONF_LINK_TEMPLATE,
                    CONF_MAX_KM, CONF_MAX_PRICE, CONF_MODELS, DEFAULT_INTERVAL_HOURS,
                    DEFAULT_MODELS, DOMAIN, MODEL_OPTIONS)


def _box(min_: int, max_: int, step: int, unit: str) -> NumberSelector:
    return NumberSelector(NumberSelectorConfig(
        min=min_, max=max_, step=step, mode=NumberSelectorMode.BOX, unit_of_measurement=unit))


def _schema(d: dict) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_MODELS, default=d.get(CONF_MODELS, DEFAULT_MODELS)): SelectSelector(
            SelectSelectorConfig(options=MODEL_OPTIONS, multiple=True, custom_value=True,
                                 mode=SelectSelectorMode.DROPDOWN)),
        vol.Required(CONF_INTERVAL_HOURS, default=d.get(CONF_INTERVAL_HOURS, DEFAULT_INTERVAL_HOURS)):
            _box(1, 24, 1, "h"),
        vol.Optional(CONF_MAX_PRICE, default=d.get(CONF_MAX_PRICE, 0)): _box(0, 200000, 500, "€"),
        vol.Optional(CONF_MAX_KM, default=d.get(CONF_MAX_KM, 0)): _box(0, 300000, 500, "km"),
        vol.Required(CONF_INCLUDE_DEMO, default=d.get(CONF_INCLUDE_DEMO, True)): BooleanSelector(),
        vol.Optional(CONF_LINK_TEMPLATE, default=d.get(CONF_LINK_TEMPLATE, "")): TextSelector(),
    })


def _clean(user_input: dict) -> dict:
    out = dict(user_input)
    out[CONF_MODELS] = [m.strip().upper() for m in out.get(CONF_MODELS, []) if m.strip()]
    out[CONF_INTERVAL_HOURS] = int(out.get(CONF_INTERVAL_HOURS) or DEFAULT_INTERVAL_HOURS)
    out[CONF_MAX_PRICE] = int(out.get(CONF_MAX_PRICE) or 0)
    out[CONF_MAX_KM] = int(out.get(CONF_MAX_KM) or 0)
    return out


class SkodaStockConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _clean(user_input)
            if not data[CONF_MODELS]:
                errors["base"] = "no_models"
            else:
                try:
                    res = await fetch_page(async_get_clientsession(self.hass), data[CONF_MODELS], 1)
                    if "cars" not in (res.get("results") or {}):
                        raise SkodaStockError("unexpected response")
                except (SkodaStockError, aiohttp.ClientError):
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(title="Škoda Stock", data={}, options=data)
        return self.async_show_form(step_id="user", data_schema=_schema(user_input or {}), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return SkodaStockOptionsFlow()


class SkodaStockOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=_clean(user_input))
        return self.async_show_form(step_id="init", data_schema=_schema(dict(self.config_entry.options)))
