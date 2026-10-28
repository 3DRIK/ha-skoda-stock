"""Binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SkodaStockCoordinator
from .sensor import device_info


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([FavoritesChanged(hass.data[DOMAIN]["coordinator"], entry)])


class FavoritesChanged(CoordinatorEntity[SkodaStockCoordinator], BinarySensorEntity):
    """On when a favourite changed price, got reserved or left the stock in the last 24 h."""

    _attr_has_entity_name = True
    _attr_name = "Zmena u obľúbených"
    _attr_icon = "mdi:star-circle"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_favorites_changed"
        self._attr_device_info = device_info(entry)

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data["favorites_changed"])

    @property
    def extra_state_attributes(self):
        return {"cars": self.coordinator.data["favorites_changed"][:20]}
