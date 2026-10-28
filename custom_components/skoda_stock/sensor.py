"""Sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (SensorDeviceClass, SensorEntity,
                                             SensorEntityDescription)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SkodaStockCoordinator


@dataclass(frozen=True, kw_only=True)
class SkodaSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any]
    attrs_fn: Callable[[dict], dict] | None = None


def _count(key: str) -> Callable[[dict], int]:
    return lambda s: len(s[key])


SENSORS: tuple[SkodaSensorDescription, ...] = (
    SkodaSensorDescription(
        key="total", name="Počet áut", icon="mdi:car-multiple",
        native_unit_of_measurement="áut",
        value_fn=lambda s: s["total"], attrs_fn=lambda s: {"by_model": s["by_model"]}),
    SkodaSensorDescription(
        key="cheapest", name="Najlacnejšie auto", icon="mdi:cash",
        device_class=SensorDeviceClass.MONETARY, native_unit_of_measurement="EUR",
        value_fn=lambda s: s["cheapest"]["price"] if s["cheapest"] else None,
        attrs_fn=lambda s: s["cheapest"] or {}),
    SkodaSensorDescription(
        key="new24", name="Nové ponuky za 24 h", icon="mdi:car-clock",
        native_unit_of_measurement="áut",
        value_fn=_count("new24"), attrs_fn=lambda s: {"cars": s["new24"][:20]}),
    SkodaSensorDescription(
        key="drops24", name="Zníženia cien za 24 h", icon="mdi:tag-arrow-down",
        native_unit_of_measurement="áut",
        value_fn=_count("drops24"), attrs_fn=lambda s: {"cars": s["drops24"][:20]}),
    SkodaSensorDescription(
        key="reserved", name="Rezervované autá", icon="mdi:bookmark-check",
        native_unit_of_measurement="áut", value_fn=lambda s: s["reserved"]),
    SkodaSensorDescription(
        key="demo", name="Predvádzacie autá", icon="mdi:steering",
        native_unit_of_measurement="áut", value_fn=lambda s: s["demo"]),
    SkodaSensorDescription(
        key="favorites", name="Obľúbené autá", icon="mdi:star",
        native_unit_of_measurement="áut",
        value_fn=_count("favorites"), attrs_fn=lambda s: {"cars": s["favorites"][:20]}),
    SkodaSensorDescription(
        key="updated_at", name="Posledná aktualizácia", icon="mdi:update",
        device_class=SensorDeviceClass.TIMESTAMP, value_fn=lambda s: s["updated_at"]),
)


def device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name="Škoda Stock",
                      manufacturer="Škoda Auto", entry_type=DeviceEntryType.SERVICE)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    coordinator: SkodaStockCoordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities(SkodaSensor(coordinator, entry, d) for d in SENSORS)


class SkodaSensor(CoordinatorEntity[SkodaStockCoordinator], SensorEntity):
    _attr_has_entity_name = True
    entity_description: SkodaSensorDescription

    def __init__(self, coordinator, entry, description) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = device_info(entry)

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self):
        fn = self.entity_description.attrs_fn
        return fn(self.coordinator.data) if fn else None
