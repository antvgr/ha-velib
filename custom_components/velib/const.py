"""Constants for the Vélib' Métropole integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "velib"
MANUFACTURER: Final = "Vélib' Métropole"

CONF_ENTRY_TYPE: Final = "entry_type"
ENTRY_TYPE_STATIONS: Final = "stations"
ENTRY_TYPE_ACCOUNT: Final = "account"

CONF_STATIONS: Final = "stations"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_SEARCH: Final = "search"

DEFAULT_STATIONS_INTERVAL: Final = 120  # seconds, the GBFS feed refreshes ~1/min
MIN_STATIONS_INTERVAL: Final = 60
ACCOUNT_INTERVAL: Final = timedelta(minutes=15)

TRIPS_FETCHED: Final = 10
EVENT_NEW_TRIP: Final = f"{DOMAIN}_new_trip"
