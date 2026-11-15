"""Base entities for Vélib' Métropole."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Station
from .const import DOMAIN, MANUFACTURER
from .coordinator import VelibAccountCoordinator, VelibStationsCoordinator


class VelibStationEntity(CoordinatorEntity[VelibStationsCoordinator]):
    """An entity attached to a station."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: VelibStationsCoordinator, code: str, key: str) -> None:
        super().__init__(coordinator)
        self.code = code
        station = coordinator.data.get(code)
        name = station.name if station else f"Station {code}"
        self._attr_unique_id = f"station_{code}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"station_{code}")},
            name=f"Vélib' {name}",
            manufacturer=MANUFACTURER,
            model=f"Station {code}",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"https://www.velib-metropole.fr/map#/station/{code}",
        )

    @property
    def station(self) -> Station | None:
        return self.coordinator.data.get(self.code)

    @property
    def available(self) -> bool:
        return super().available and self.station is not None


class VelibAccountEntity(CoordinatorEntity[VelibAccountCoordinator]):
    """An entity attached to a Vélib' account."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: VelibAccountCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"account_{entry_id}")},
            name=f"Vélib' {coordinator.config_entry.title}",
            manufacturer=MANUFACTURER,
            model="Compte abonné",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.velib-metropole.fr/private/account",
        )
