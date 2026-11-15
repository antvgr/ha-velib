"""Binary sensors for Vélib' Métropole stations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VelibConfigEntry
from .api import Station
from .coordinator import VelibStationsCoordinator
from .entity import VelibStationEntity


@dataclass(frozen=True, kw_only=True)
class VelibBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[Station], bool | None]


BINARY_SENSORS: tuple[VelibBinarySensorDescription, ...] = (
    VelibBinarySensorDescription(
        key="renting",
        translation_key="renting",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.is_renting,
    ),
    VelibBinarySensorDescription(
        key="returning",
        translation_key="returning",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.is_returning,
    ),
)


class VelibBinarySensor(VelibStationEntity, BinarySensorEntity):
    entity_description: VelibBinarySensorDescription

    def __init__(
        self,
        coordinator: VelibStationsCoordinator,
        code: str,
        description: VelibBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, code, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        station = self.station
        return self.entity_description.value_fn(station) if station else None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VelibConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors (stations only)."""
    coordinator = entry.runtime_data.coordinator
    if not isinstance(coordinator, VelibStationsCoordinator):
        return
    async_add_entities(
        VelibBinarySensor(coordinator, code, desc)
        for code in coordinator.station_codes
        for desc in BINARY_SENSORS
    )
