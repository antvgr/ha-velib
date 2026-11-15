"""Data update coordinators for Vélib' Métropole."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    Station,
    Trip,
    VelibAccountClient,
    VelibAuthError,
    VelibError,
    VelibPublicClient,
)
from .const import ACCOUNT_INTERVAL, DOMAIN, EVENT_NEW_TRIP, TRIPS_FETCHED

_LOGGER = logging.getLogger(__name__)


class VelibStationsCoordinator(DataUpdateCoordinator[dict[str, Station]]):
    """Polls the public GBFS feed and keeps the selected stations."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: VelibPublicClient,
        station_codes: list[str],
        interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_stations",
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self.station_codes = station_codes

    async def _async_update_data(self) -> dict[str, Station]:
        try:
            stations = await self.client.async_get_stations()
        except VelibError as err:
            raise UpdateFailed(str(err)) from err
        followed = {
            code: stations[code] for code in self.station_codes if code in stations
        }
        # Enrich with per-bike battery/rating (best effort; never fail the update).
        try:
            bikes = await self.client.async_get_station_bikes(
                {code: st.name for code, st in followed.items()}
            )
            for code, station in followed.items():
                station.bikes = bikes.get(code, [])
        except VelibError as err:
            _LOGGER.debug("Battery fetch failed (keeping station counts): %s", err)
        return followed


@dataclass(slots=True)
class AccountData:
    """Data fetched for an account."""

    infos: dict[str, Any]
    trips: list[Trip]
    total_trips: int | None
    station_names: dict[str, str] = field(default_factory=dict)

    @property
    def general(self) -> dict[str, Any]:
        return self.infos.get("generalDetails") or {}

    @property
    def indicators(self) -> dict[str, Any]:
        return self.general.get("customerIndicators") or {}

    @property
    def last_trip(self) -> Trip | None:
        return self.trips[0] if self.trips else None

    def station_name(self, station: str | None) -> str | None:
        if station is None:
            return None
        return self.station_names.get(station, station)


class VelibAccountCoordinator(DataUpdateCoordinator[AccountData]):
    """Polls the user's account information and trips."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: VelibAccountClient,
        public: VelibPublicClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_account",
            update_interval=ACCOUNT_INTERVAL,
        )
        self.client = client
        self.public = public
        self._seen_trips: set[str] | None = None

    async def _station_names(self) -> dict[str, str]:
        """Map station codes and GBFS ids to names, best effort."""
        try:
            info = await self.public.async_get_station_information(max_age=24 * 3600)
        except VelibError:
            return self.data.station_names if self.data else {}
        names: dict[str, str] = {}
        for code, station in info.items():
            name = station.get("name")
            if not name:
                continue
            names[code] = name
            if station.get("station_id") is not None:
                names[str(station["station_id"])] = name
        return names

    async def _async_update_data(self) -> AccountData:
        try:
            infos = await self.client.async_get_all_infos_user()
            trips, total = await self.client.async_get_trips(limit=TRIPS_FETCHED)
        except VelibAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except VelibError as err:
            raise UpdateFailed(str(err)) from err

        data = AccountData(
            infos=infos,
            trips=trips,
            total_trips=total,
            station_names=await self._station_names(),
        )
        self._fire_new_trip_events(data)
        return data

    def _fire_new_trip_events(self, data: AccountData) -> None:
        uids = {t.uid for t in data.trips}
        if self._seen_trips is None:  # first refresh: don't replay history
            self._seen_trips = uids
            return
        for trip in reversed(data.trips):
            if trip.uid in self._seen_trips:
                continue
            self.hass.bus.async_fire(
                EVENT_NEW_TRIP,
                {
                    "account": self.client.username,
                    "date": trip.date.isoformat() if trip.date else None,
                    "electric": trip.electric,
                    "bike_id": trip.bike_id,
                    "distance_m": trip.distance_m,
                    "duration_s": trip.duration_s,
                    "average_speed_kmh": trip.average_speed_kmh,
                    "co2_saved_g": trip.co2_saved_g,
                    "price": trip.price,
                    "departure_station": data.station_name(trip.departure_station),
                    "arrival_station": data.station_name(trip.arrival_station),
                },
            )
        self._seen_trips = uids
