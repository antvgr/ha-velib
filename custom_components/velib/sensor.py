"""Sensors for Vélib' Métropole."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    EntityCategory,
    UnitOfLength,
    UnitOfMass,
    UnitOfSpeed,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VelibConfigEntry
from .api import Station, Trip
from .coordinator import AccountData, VelibAccountCoordinator, VelibStationsCoordinator
from .entity import VelibAccountEntity, VelibStationEntity

BIKES = "vélos"


def _bike_dict(b) -> dict[str, Any]:
    """Serialize an ElectricBike for the card (type-normalized)."""
    return {
        "number": b.number,
        "type": "electric" if b.electric else "mechanical",
        "dock": b.dock_position,
        "battery_level": b.battery_level,
        "battery_max": b.battery_max,
        "battery_percent": b.battery_percent,
        "charging": b.charging,
        "rating": b.rating,
        "rates": b.number_of_rates,
        "status": b.status,
        "available": (b.status or "").lower() not in ("indisponible", "unavailable"),
        "last_rate_date": b.last_rate_date,
    }


# --------------------------------------------------------------------------- #
# Station sensors
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, kw_only=True)
class VelibStationSensorDescription(SensorEntityDescription):
    value_fn: Callable[[Station], Any]


STATION_SENSORS: tuple[VelibStationSensorDescription, ...] = (
    VelibStationSensorDescription(
        key="bikes",
        translation_key="bikes",
        native_unit_of_measurement=BIKES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.bikes_available,
    ),
    VelibStationSensorDescription(
        key="mechanical",
        translation_key="mechanical",
        native_unit_of_measurement=BIKES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.mechanical_available,
    ),
    VelibStationSensorDescription(
        key="ebike",
        translation_key="ebike",
        native_unit_of_measurement=BIKES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.ebike_available,
    ),
    VelibStationSensorDescription(
        key="docks",
        translation_key="docks",
        native_unit_of_measurement="bornes",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.docks_available,
    ),
    VelibStationSensorDescription(
        key="capacity",
        translation_key="capacity",
        native_unit_of_measurement="bornes",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.capacity,
    ),
    VelibStationSensorDescription(
        key="last_reported",
        translation_key="last_reported",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.last_reported,
    ),
)


class VelibStationSensor(VelibStationEntity, SensorEntity):
    entity_description: VelibStationSensorDescription

    def __init__(
        self,
        coordinator: VelibStationsCoordinator,
        code: str,
        description: VelibStationSensorDescription,
    ) -> None:
        super().__init__(coordinator, code, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        station = self.station
        return self.entity_description.value_fn(station) if station else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        s = self.station
        if s is None:
            return None
        if self.entity_description.key == "bikes":
            # Full station payload consumed by the velib-station-card.
            return {
                "station_code": s.code,
                "station_name": s.name,
                ATTR_LATITUDE: s.latitude,
                ATTR_LONGITUDE: s.longitude,
                "capacity": s.capacity,
                "free_docks": s.docks_available,
                "mechanical_available": s.mechanical_available,
                "ebike_available": s.ebike_available,
                "bikes": [_bike_dict(b) for b in s.bikes],
            }
        if self.entity_description.key == "ebike":
            # Per-bike battery and rating, electric bikes only (back-compat).
            return {"bikes": [_bike_dict(b) for b in s.electric_bikes]}
        return None


# --------------------------------------------------------------------------- #
# Account sensors
# --------------------------------------------------------------------------- #


def _trip_attrs(data: AccountData, trip: Trip | None) -> dict[str, Any] | None:
    if trip is None:
        return None
    return {
        "electric": trip.electric,
        "bike_id": trip.bike_id,
        "distance_km": round(trip.distance_m / 1000, 2) if trip.distance_m is not None else None,
        "duration_min": round(trip.duration_s / 60, 1) if trip.duration_s is not None else None,
        "average_speed_kmh": trip.average_speed_kmh,
        "co2_saved_g": trip.co2_saved_g,
        "price": trip.price,
        "departure_station": data.station_name(trip.departure_station),
        "arrival_station": data.station_name(trip.arrival_station),
    }


def _last(fn: Callable[[Trip], Any]) -> Callable[[AccountData], Any]:
    return lambda d: fn(d.last_trip) if d.last_trip else None


def _indicator(key: str, scale: float = 1) -> Callable[[AccountData], Any]:
    def get(d: AccountData) -> Any:
        value = d.indicators.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return round(value * scale, 3)
        return None

    return get


def _bonus(d: AccountData) -> Any:
    value = (d.general.get("customerBonusDetails") or {}).get("currentYear")
    return value if isinstance(value, (int, float)) else None


@dataclass(frozen=True, kw_only=True)
class VelibAccountSensorDescription(SensorEntityDescription):
    value_fn: Callable[[AccountData], Any]
    attrs_fn: Callable[[AccountData], dict[str, Any] | None] | None = None


ACCOUNT_SENSORS: tuple[VelibAccountSensorDescription, ...] = (
    VelibAccountSensorDescription(
        key="last_trip",
        translation_key="last_trip",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_last(lambda t: t.date),
        attrs_fn=lambda d: _trip_attrs(d, d.last_trip),
    ),
    VelibAccountSensorDescription(
        key="last_trip_distance",
        translation_key="last_trip_distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=2,
        value_fn=_last(lambda t: t.distance_m),
    ),
    VelibAccountSensorDescription(
        key="last_trip_duration",
        translation_key="last_trip_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=_last(lambda t: t.duration_s),
    ),
    VelibAccountSensorDescription(
        key="last_trip_speed",
        translation_key="last_trip_speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=1,
        value_fn=_last(lambda t: t.average_speed_kmh),
    ),
    VelibAccountSensorDescription(
        key="trip_count",
        translation_key="trip_count",
        native_unit_of_measurement="trajets",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.indicators.get("tripCounter")
        if isinstance(d.indicators.get("tripCounter"), int)
        else d.total_trips,
    ),
    VelibAccountSensorDescription(
        key="total_distance",
        translation_key="total_distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=1,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_indicator("distanceGlobalCounter"),
    ),
    VelibAccountSensorDescription(
        key="co2_saved",
        translation_key="co2_saved",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.GRAMS,
        suggested_unit_of_measurement=UnitOfMass.KILOGRAMS,
        suggested_display_precision=1,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_indicator("globalSavedCarbonDioxide"),
    ),
    VelibAccountSensorDescription(
        key="bonus_minutes",
        translation_key="bonus_minutes",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=_bonus,
    ),
)


class VelibAccountSensor(VelibAccountEntity, SensorEntity):
    entity_description: VelibAccountSensorDescription

    def __init__(
        self,
        coordinator: VelibAccountCoordinator,
        description: VelibAccountSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VelibConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data.coordinator
    if isinstance(coordinator, VelibAccountCoordinator):
        async_add_entities(
            VelibAccountSensor(coordinator, desc) for desc in ACCOUNT_SENSORS
        )
        return
    async_add_entities(
        VelibStationSensor(coordinator, code, desc)
        for code in coordinator.station_codes
        for desc in STATION_SENSORS
    )
