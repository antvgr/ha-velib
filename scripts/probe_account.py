"""Standalone probe for the Vélib' private API (no Home Assistant needed).

Usage (credentials are read from the environment or a git-ignored .env file):

    pip install aiohttp
    set VELIB_USERNAME=...   (PowerShell: $env:VELIB_USERNAME="...")
    set VELIB_PASSWORD=...
    python scripts/probe_account.py            # summary
    python scripts/probe_account.py --raw      # dump raw JSON to probe_output/

The raw dump contains personal data: it is written to probe_output/, which is
git-ignored. Do not share it without cleaning it.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys

import aiohttp

ROOT = Path(__file__).resolve().parent.parent

# Load api.py directly, without importing the Home Assistant package.
_spec = importlib.util.spec_from_file_location(
    "velib_api", ROOT / "custom_components" / "velib" / "api.py"
)
api = importlib.util.module_from_spec(_spec)
sys.modules["velib_api"] = api
_spec.loader.exec_module(api)


def urllib_test(username: str, password: str, codes: list[str], raw: bool) -> int:
    """Run the login + battery test with the stdlib urllib client.

    Used when aiohttp is blocked (e.g. Cloudflare on some hosts). Both are plain
    HTTP clients; this only swaps the library, it does not spoof anything.
    """
    import json as _json
    import urllib.error
    import urllib.request

    def _req(url: str, data: bytes | None = None, token: str | None = None):
        headers = {
            "User-Agent": api.USER_AGENT,
            "Accept": "application/json",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
            headers["Origin"] = api.SITE_BASE
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, _json.loads(resp.read().decode("utf-8"))

    try:
        body = _json.dumps({"_username": username, "_password": password}).encode()
        status, data = _req(api.LOGIN_TOKEN_URL, data=body)
    except urllib.error.HTTPError as err:
        if err.code in (400, 401):
            print("[urllib] Login refused (bad credentials?)")
            return 1
        print(f"[urllib] Login blocked too (HTTP {err.code}). This host cannot reach the API.")
        return 2
    except Exception as err:  # noqa: BLE001
        print(f"[urllib] Login failed: {err}")
        return 2

    token = (data or {}).get("token")
    if not token:
        print("[urllib] No token returned.")
        return 1
    print("[urllib] Login OK (bearer token obtained)")

    test_codes = codes or ["9020", "40001", "16107"]
    print(f"\n== Battery test (urllib) on stations {test_codes} ==")
    try:
        url = f"{api.MAP_DETAILS_URL}?listeCodeStation={','.join(test_codes)}"
        _, details = _req(url, token=token)
    except Exception as err:  # noqa: BLE001
        print(f"  /api/map/details failed: {err}")
        return 2

    any_bikes = False
    for entry in details or []:
        if not isinstance(entry, dict):
            continue
        code = str((entry.get("station") or {}).get("code") or "")
        bikes = entry.get("bikes") or []
        print(f"  station {code}: {len(bikes)} bike(s) in 'bikes' array")
        for b in bikes[:8]:
            bk = api.ElectricBike.from_api(b)
            any_bikes = True
            print(
                f"    #{bk.number} {'elec' if bk.electric else 'meca'} "
                f"battery={bk.battery_level}/{bk.battery_max} (~{bk.battery_percent}%) "
                f"charging={bk.charging} rating={bk.rating} dock={bk.dock_position}"
            )
    if any_bikes:
        print("\n  ✅ SUCCESS: your bearer token returns per-bike battery + rating.")
    else:
        print(
            "\n  ❌ No 'bikes' array with your token. The app's static key is probably"
            " required for that endpoint (see docs/API.md)."
        )
    if raw:
        out = ROOT / "probe_output"
        out.mkdir(exist_ok=True)
        (out / "map_details_auth.json").write_text(
            _json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Raw JSON written to {out}")
    return 0


def _load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


async def main(raw: bool, stations: list[str]) -> int:
    _load_env()
    username = os.environ.get("VELIB_USERNAME")
    password = os.environ.get("VELIB_PASSWORD")

    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
        public = api.VelibPublicClient(session)
        all_stations = await public.async_get_stations()
        print(f"GBFS: {len(all_stations)} stations")
        for code in stations:
            s = all_stations.get(code)
            print(f"  {code}: {s}" if s else f"  {code}: unknown")

        if not (username and password):
            print("VELIB_USERNAME / VELIB_PASSWORD not set: skipping account.")
            return 0

        client = api.VelibAccountClient(session, username, password)
        try:
            await client.async_login()
        except api.VelibAuthError:
            print("Login refused (bad credentials?)")
            return 1
        except api.VelibConnectionError as err:
            print(f"\n[aiohttp] blocked: {err}")
            print("[aiohttp] Falling back to urllib (stdlib HTTP client)...\n")
            return urllib_test(username, password, [c for c in stations if c], raw)
        print("Login OK (bearer token obtained)")

        # --- DECISIVE TEST: does the bearer token unlock the per-bike list? ---
        test_codes = [c for c in stations if c] or ["9020", "40001", "16107"]
        print(f"\n== Battery test on stations {test_codes} ==")
        try:
            bikes_by_station = await client.async_get_station_bikes(test_codes)
        except api.VelibError as err:
            print(f"  /api/map/details (authenticated) failed: {err}")
            bikes_by_station = {}
        any_bikes = False
        for code, bikes in bikes_by_station.items():
            print(f"  station {code}: {len(bikes)} bike(s) in 'bikes' array")
            for bk in bikes[:8]:
                any_bikes = True
                print(
                    f"    #{bk.number} {'elec' if bk.electric else 'meca'} "
                    f"battery={bk.battery_level}/{bk.battery_max} "
                    f"(~{bk.battery_percent}%) charging={bk.charging} "
                    f"rating={bk.rating} dock={bk.dock_position}"
                )
        if any_bikes:
            print("\n  ✅ SUCCESS: your bearer token returns per-bike battery + rating.")
        else:
            print(
                "\n  ❌ No 'bikes' array with your token. The app's static key is"
                " probably required for that endpoint (see docs/API.md)."
            )

        infos = await client.async_get_all_infos_user()
        courses = await client.async_get_course_list(limit=10)
        trips, total = await client.async_get_trips(limit=10)

        indicators = (infos.get("generalDetails") or {}).get("customerIndicators") or {}
        print("Top-level keys of getAllInfosUser:", sorted(infos))
        print("customerIndicators:", json.dumps(indicators, ensure_ascii=False))
        print(f"Trips: {total} in total, last {len(trips)}:")
        for t in trips:
            print(
                f"  {t.date}  {'élec' if t.electric else 'méca'}  bike={t.bike_id}  "
                f"{(t.distance_m or 0) / 1000:.2f} km  {(t.duration_s or 0) / 60:.0f} min  "
                f"{t.departure_station} -> {t.arrival_station}"
            )

        if raw:
            out = ROOT / "probe_output"
            out.mkdir(exist_ok=True)
            (out / "getAllInfosUser.json").write_text(
                json.dumps(infos, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (out / "getCourseList.json").write_text(
                json.dumps(courses, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            try:
                raw_details = await client._authed_get(
                    api.MAP_DETAILS_URL,
                    params={"listeCodeStation": ",".join(test_codes)},
                )
                (out / "map_details_auth.json").write_text(
                    json.dumps(raw_details, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except api.VelibError:
                pass
            print(f"Raw JSON written to {out}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", action="store_true", help="dump raw JSON payloads")
    parser.add_argument("stations", nargs="*", help="station codes to show")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.raw, args.stations)))
