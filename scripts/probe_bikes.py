"""Find which authentication makes /api/map/details return the per-bike list.

Static analysis confirmed the response model has a ``bikes`` array (battery +
rating), but it is omitted unless the request is authenticated the right way.
This tries each combination and reports which one works. Uses urllib (stdlib),
so it works even where aiohttp is Cloudflare-blocked.

Run it yourself (credentials in .env, app key in secrets.local.json):

    python scripts/probe_bikes.py 9020 40001 16107
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://www.velib-metropole.fr"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


def _load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def _get(url: str, headers: dict[str, str]):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_json(url: str, payload: dict, headers: dict[str, str] | None = None):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"User-Agent": UA, "Accept": "application/json",
                 "Content-Type": "application/json", "Origin": SITE, **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _count_bikes(data) -> tuple[int, int, dict | None]:
    stations = sum(1 for e in data if isinstance(e, dict))
    with_bikes = sum(1 for e in data if isinstance(e, dict) and e.get("bikes"))
    sample = next((e["bikes"][0] for e in data if isinstance(e, dict) and e.get("bikes")), None)
    return stations, with_bikes, sample


def main(codes: list[str]) -> int:
    _load_env()
    codes = codes or ["9020", "40001", "16107"]
    q = ",".join(codes)
    url = f"{SITE}/api/map/details?listeCodeStation={q}"

    # App key (optional) from gitignored local file.
    basic = None
    keyfile = ROOT / "secrets.local.json"
    if keyfile.exists():
        k = json.loads(keyfile.read_text(encoding="utf-8"))
        raw = f"{k['app_basic_user']}:{k['app_basic_token']}".encode()
        basic = "Basic " + base64.b64encode(raw).decode()
        print("App key loaded from secrets.local.json")
    else:
        print("No secrets.local.json — skipping app-key combinations")

    # User token (optional) from .env credentials.
    bearer = None
    u, p = os.environ.get("VELIB_USERNAME"), os.environ.get("VELIB_PASSWORD")
    if u and p:
        try:
            tok = _post_json(f"{SITE}/api/secured/login_check_client", {"_username": u, "_password": p}).get("token")
            if tok:
                bearer = f"Bearer {tok}"
                print("User token obtained from login")
        except urllib.error.HTTPError as err:
            print(f"Login failed (HTTP {err.code})")
    else:
        print("No VELIB_USERNAME/PASSWORD in .env — skipping user-token combinations")

    combos: list[tuple[str, dict[str, str]]] = [("anonymous", {})]
    if bearer:
        combos.append(("bearer (user)", {"Authorization": bearer}))
    if basic:
        combos.append(("basic (app key)", {"Authorization": basic}))
    if basic and bearer:
        combos.append(("basic + X-Auth bearer", {"Authorization": basic, "X-Authorization": bearer}))
        combos.append(("basic + Cookie token", {"Authorization": basic, "Cookie": f"token={bearer.split()[1]}"}))

    winner = None
    for name, headers in combos:
        try:
            data = _get(url, headers)
        except urllib.error.HTTPError as err:
            print(f"  {name:28s} -> HTTP {err.code}")
            continue
        except Exception as err:  # noqa: BLE001
            print(f"  {name:28s} -> error {err}")
            continue
        stations, with_bikes, sample = _count_bikes(data)
        print(f"  {name:28s} -> {stations} stations, {with_bikes} with bikes[]")
        if with_bikes and sample:
            winner = name
            print("      sample bike:", {kk: sample.get(kk) for kk in (
                "bikeName", "bikeElectric", "bikeBatteryLevel", "bikeRate", "charging", "dockPosition")})

    print()
    if winner:
        print(f"✅ WORKS with: {winner}")
    else:
        print("❌ No combination returned bikes[]. A live capture of the app (HTTP Toolkit)"
              " is needed to see the exact request that works.")
    return 0


if __name__ == "__main__":
    sys.exit(main([a for a in sys.argv[1:] if not a.startswith("-")]))
