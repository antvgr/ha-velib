"""Clients for the Vélib' Métropole APIs.

This module has no Home Assistant dependency so it can be reused by the
standalone probe script in ``scripts/``.

Two APIs are used:

* the public GBFS open data feed (no authentication), station level only;
* the private API of www.velib-metropole.fr, authenticated with the session
  cookie obtained through the website login form.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

GBFS_BASE = "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole"
STATION_INFORMATION_URL = f"{GBFS_BASE}/station_information.json"
STATION_STATUS_URL = f"{GBFS_BASE}/station_status.json"

SITE_BASE = "https://www.velib-metropole.fr"
LOGIN_TOKEN_URL = f"{SITE_BASE}/api/secured/login_check_client"
ALL_INFOS_USER_URL = f"{SITE_BASE}/api/private/getAllInfosUser"
COURSE_LIST_URL = f"{SITE_BASE}/api/private/getCourseList"
MAP_DETAILS_URL = f"{SITE_BASE}/api/map/details"
SEARCH_STATION_URL = f"{SITE_BASE}/api/secured/searchStation"

# bikeBatteryLevel is a coarse 0..3 level, exactly like the app's battery bars.
BATTERY_LEVELS = {"0_SUR_3": 0, "1_SUR_3": 1, "2_SUR_3": 2, "3_SUR_3": 3}
BATTERY_MAX = 3

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
TIMEOUT = aiohttp.ClientTimeout(total=30)


def _blocking_post_json(url: str, body: dict[str, Any], headers: dict[str, str]) -> Any:
    """POST JSON with the stdlib client (fallback when aiohttp is blocked).

    Runs in a worker thread via ``asyncio.to_thread``. Uses only Python's standard
    HTTP client — no custom TLS fingerprinting.
    """
    import json as _json
    import urllib.request

    data = _json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return _json.loads(resp.read().decode("utf-8"))


class VelibError(Exception):
    """Base error."""


class VelibConnectionError(VelibError):
    """The API could not be reached or returned something unexpected."""


class VelibAuthError(VelibError):
    """The credentials were rejected."""


# --------------------------------------------------------------------------- #
# Public GBFS API
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class Station:
    """A station, merged from station_information and station_status."""

    station_id: str
    code: str
    name: str
    latitude: float
    longitude: float
    capacity: int | None = None
    bikes_available: int | None = None
    mechanical_available: int | None = None
    ebike_available: int | None = None
    docks_available: int | None = None
    is_installed: bool | None = None
    is_renting: bool | None = None
    is_returning: bool | None = None
    last_reported: datetime | None = None
    # Per-bike battery/rating (from searchStation); empty if not fetched/available.
    bikes: list["ElectricBike"] = field(default_factory=list)

    @property
    def electric_bikes(self) -> list["ElectricBike"]:
        """Available electric bikes that report a battery level."""
        return [b for b in self.bikes if b.electric and b.battery_level is not None]


def _bike_types(raw: list[dict[str, Any]] | None) -> dict[str, int]:
    """Flatten ``[{"mechanical": 1}, {"ebike": 2}]`` into a dict."""
    out: dict[str, int] = {}
    for item in raw or []:
        if isinstance(item, dict):
            for key, value in item.items():
                if isinstance(value, int):
                    out[key] = value
    return out


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


class VelibPublicClient:
    """Client for the public GBFS feed."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._info_cache: dict[str, dict[str, Any]] | None = None
        self._info_cache_time = 0.0

    async def _get_json(self, url: str) -> Any:
        try:
            async with self._session.get(
                url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}
            ) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise VelibConnectionError(f"Error fetching {url}: {err}") from err

    async def async_get_station_information(
        self, max_age: float = 6 * 3600
    ) -> dict[str, dict[str, Any]]:
        """Return station_information keyed by station code (cached)."""
        if self._info_cache is not None and time.monotonic() - self._info_cache_time < max_age:
            return self._info_cache
        data = await self._get_json(STATION_INFORMATION_URL)
        try:
            stations = data["data"]["stations"]
        except (KeyError, TypeError) as err:
            raise VelibConnectionError("Unexpected station_information payload") from err
        self._info_cache = {
            str(s.get("stationCode")): s for s in stations if s.get("stationCode") is not None
        }
        self._info_cache_time = time.monotonic()
        return self._info_cache

    async def async_get_stations(self) -> dict[str, Station]:
        """Return every station with its live status, keyed by station code."""
        info = await self.async_get_station_information()
        data = await self._get_json(STATION_STATUS_URL)
        try:
            statuses = data["data"]["stations"]
        except (KeyError, TypeError) as err:
            raise VelibConnectionError("Unexpected station_status payload") from err

        result: dict[str, Station] = {}
        for code, i in info.items():
            result[code] = Station(
                station_id=str(i.get("station_id")),
                code=code,
                name=i.get("name") or code,
                latitude=i.get("lat"),
                longitude=i.get("lon"),
                capacity=i.get("capacity"),
            )
        for s in statuses:
            code = str(s.get("stationCode"))
            station = result.get(code)
            if station is None:
                continue
            types = _bike_types(s.get("num_bikes_available_types"))
            station.bikes_available = s.get("num_bikes_available")
            station.mechanical_available = types.get("mechanical")
            station.ebike_available = types.get("ebike")
            station.docks_available = s.get("num_docks_available")
            station.is_installed = _as_bool(s.get("is_installed"))
            station.is_renting = _as_bool(s.get("is_renting"))
            station.is_returning = _as_bool(s.get("is_returning"))
            if isinstance(s.get("last_reported"), (int, float)):
                station.last_reported = datetime.fromtimestamp(
                    s["last_reported"], tz=timezone.utc
                )
        return result

    async def _post_search(self, station_name: str) -> list[dict[str, Any]]:
        """POST /api/secured/searchStation (public — no account needed).

        ``disponibility: "yes"`` is what makes the response include the per-bike
        ``bikes`` array (battery + rating). ``Authorization: Bearer null`` is what
        the app sends when logged out, and the endpoint accepts it.

        velib-metropole.fr sits behind Cloudflare, which rejects some HTTP clients
        with 403 depending on host/IP. aiohttp is tried first; on failure the same
        request is retried with the stdlib client in a worker thread.
        """
        body = {"disponibility": "yes", "stationName": station_name}
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
            "Authorization": "Bearer null",
        }
        try:
            async with self._session.post(
                SEARCH_STATION_URL, json=body, headers=headers, timeout=TIMEOUT
            ) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            _LOGGER.debug("searchStation via aiohttp failed (%s); trying stdlib", err)
            try:
                data = await asyncio.to_thread(
                    _blocking_post_json, SEARCH_STATION_URL, body, headers
                )
            except Exception as err2:  # noqa: BLE001
                raise VelibConnectionError(f"searchStation failed: {err2}") from err2
        return data if isinstance(data, list) else []

    async def async_get_station_bikes(
        self, stations: dict[str, str]
    ) -> dict[str, list["ElectricBike"]]:
        """Return the per-bike list (battery + rating) for each station.

        ``stations`` maps station code -> station name. One searchStation call is
        made per distinct name (names are a substring filter); results are matched
        back by exact station code, so a query is kept small even with many
        followed stations.
        """
        out: dict[str, list[ElectricBike]] = {code: [] for code in stations}
        for name in sorted({n for n in stations.values() if n}):
            entries = await self._post_search(name)
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                code = str((entry.get("station") or {}).get("code") or "")
                if code not in out:
                    continue
                bikes = entry.get("bikes")
                if isinstance(bikes, list):
                    out[code] = [
                        ElectricBike.from_api(b) for b in bikes if isinstance(b, dict)
                    ]
        return out


# --------------------------------------------------------------------------- #
# Private account API (www.velib-metropole.fr)
# --------------------------------------------------------------------------- #


def parse_operation_date(value: Any) -> datetime | None:
    """Parse a trip date (ISO 8601 string or epoch, seconds or ms)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        ts = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            # The website renders it with the browser's local time zone.
            from zoneinfo import ZoneInfo

            dt = dt.replace(tzinfo=ZoneInfo("Europe/Paris"))
        return dt
    return None


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return float(value.replace(",", "."))
        except ValueError:
            return None
    return None


@dataclass(slots=True)
class Trip:
    """One trip, from ``getCourseList`` ``walletOperations``."""

    date: datetime | None
    electric: bool | None
    bike_id: str | None
    distance_m: float | None
    duration_s: float | None
    average_speed_kmh: float | None
    co2_saved_g: float | None
    price: float | None
    departure_station: str | None
    arrival_station: str | None
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def uid(self) -> str:
        """Stable-ish identifier used to detect new trips."""
        return f"{self.raw.get('operationDate')}|{self.bike_id}"

    @classmethod
    def from_api(cls, op: dict[str, Any]) -> Trip:
        p3 = op.get("parameter3") or {}
        if not isinstance(p3, dict):
            p3 = {}
        p1 = op.get("parameter1")
        dep = p3.get("departureStationId")
        arr = p3.get("arrivalStationId")
        bike = p3.get("BIKEID")
        return cls(
            date=parse_operation_date(op.get("operationDate")),
            electric=(str(p1).lower() == "yes") if p1 is not None else None,
            bike_id=str(bike) if bike is not None else None,
            distance_m=_num(p3.get("DISTANCE")),
            duration_s=_num(op.get("quantity")),
            average_speed_kmh=_num(p3.get("AVERAGE_SPEED")),
            co2_saved_g=_num(p3.get("SAVED_CARBON_DIOXIDE")),
            price=_num(op.get("amountWithTax")),
            departure_station=str(dep) if dep is not None else None,
            arrival_station=str(arr) if arr is not None else None,
            raw=op,
        )


@dataclass(slots=True)
class ElectricBike:
    """One bike parked at a station (from the ``bikes`` array of searchStation).

    Mirrors the mobile app's ``BikeDto``. ``battery_level`` is a coarse 0..3
    value (like the app's battery bars), not a percentage. ``rating`` is 1..3
    stars, or None if the bike is unrated.
    """

    number: str
    electric: bool
    dock_position: str | None
    status: str | None
    charging: bool | None
    battery_level: int | None
    battery_max: int
    rating: int | None
    number_of_rates: int | None
    last_rate_date: str | None
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def battery_percent(self) -> int | None:
        """Approximate percentage from the 0..3 level, for display only."""
        if self.battery_level is None:
            return None
        return round(100 * self.battery_level / self.battery_max)

    @classmethod
    def from_api(cls, b: dict[str, Any]) -> ElectricBike:
        # bikeRate may be an int (searchStation) or a string (older payloads).
        try:
            rate = int(b.get("bikeRate"))
        except (TypeError, ValueError):
            rate = 0
        try:
            n_rates = int(b.get("numberOfRates"))
        except (TypeError, ValueError):
            n_rates = None
        return cls(
            number=str(b.get("bikeName") or ""),
            electric=str(b.get("bikeElectric")).lower() == "yes",
            dock_position=b.get("dockPosition") or None,
            status=b.get("bikeStatus") or None,
            charging=b.get("charging"),
            battery_level=BATTERY_LEVELS.get(str(b.get("bikeBatteryLevel"))),
            battery_max=BATTERY_MAX,
            rating=rate if rate > 0 else None,
            number_of_rates=n_rates,
            last_rate_date=b.get("lastRateDate") or None,
            raw=b,
        )


class VelibAccountClient:
    """Client for the private API of the Vélib' website.

    Authentication mirrors the mobile app: POST ``/api/secured/login_check_client``
    with ``{"_username", "_password"}`` to obtain a bearer token, then send
    ``Authorization: Bearer <token>`` on ``/api/private/*``. The token is
    transparently renewed when the API answers 401/403.
    """

    def __init__(
        self, session: aiohttp.ClientSession, username: str, password: str
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._token: str | None = None
        self._lock = asyncio.Lock()

    @property
    def username(self) -> str:
        return self._username

    @property
    def token(self) -> str | None:
        return self._token

    async def async_login(self) -> None:
        """Obtain a bearer token. Raises VelibAuthError on bad credentials."""
        try:
            async with self._session.post(
                LOGIN_TOKEN_URL,
                json={"_username": self._username, "_password": self._password},
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Origin": SITE_BASE,
                },
                timeout=TIMEOUT,
            ) as resp:
                status = resp.status
                if status in (400, 401, 403):
                    # 403 may also be Cloudflare; distinguish by body when possible.
                    body = await resp.text()
                    if "token" not in body and status in (400, 401):
                        raise VelibAuthError("Invalid credentials")
                    if status == 403:
                        raise VelibConnectionError(
                            "Login blocked (HTTP 403) — likely Cloudflare"
                        )
                    raise VelibAuthError("Invalid credentials")
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise VelibConnectionError(f"Login request failed: {err}") from err

        token = (data or {}).get("token")
        if not token:
            raise VelibAuthError("No token returned")
        self._token = token
        _LOGGER.debug("Obtained Vélib' bearer token")

    async def _authed_get(
        self, url: str, params: dict[str, Any] | None = None
    ) -> Any:
        async with self._lock:
            if self._token is None:
                await self.async_login()
            for attempt in (1, 2):
                try:
                    async with self._session.get(
                        url,
                        params=params,
                        headers={
                            "User-Agent": USER_AGENT,
                            "Accept": "application/json",
                            "Authorization": f"Bearer {self._token}",
                        },
                        timeout=TIMEOUT,
                    ) as resp:
                        if resp.status in (401, 403) and attempt == 1:
                            _LOGGER.debug("Token rejected (HTTP %s), renewing", resp.status)
                            await self.async_login()
                            continue
                        if resp.status in (401, 403):
                            raise VelibAuthError(f"Unauthorized ({resp.status})")
                        resp.raise_for_status()
                        return await resp.json(content_type=None)
                except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
                    raise VelibConnectionError(f"Error fetching {url}: {err}") from err
            raise VelibConnectionError("Unreachable")

    async def async_get_all_infos_user(self) -> dict[str, Any]:
        """Return the raw ``getAllInfosUser`` payload."""
        data = await self._authed_get(ALL_INFOS_USER_URL)
        if not isinstance(data, dict):
            raise VelibConnectionError("Unexpected getAllInfosUser payload")
        return data

    async def async_get_course_list(self, limit: int = 10, offset: int = 0) -> dict[str, Any]:
        """Return the raw ``getCourseList`` payload."""
        data = await self._authed_get(
            COURSE_LIST_URL, params={"limit": str(limit), "offset": str(offset)}
        )
        if not isinstance(data, dict):
            raise VelibConnectionError("Unexpected getCourseList payload")
        return data

    async def async_get_trips(self, limit: int = 10) -> tuple[list[Trip], int | None]:
        """Return the latest trips (most recent first) and the total count."""
        data = await self.async_get_course_list(limit=limit)
        ops = data.get("walletOperations") or []
        trips = [Trip.from_api(op) for op in ops if isinstance(op, dict)]
        trips.sort(
            key=lambda t: t.date or datetime.min.replace(tzinfo=timezone.utc), reverse=True
        )
        total = (data.get("paging") or {}).get("totalNumberOfRecords")
        return trips, total if isinstance(total, int) else None
