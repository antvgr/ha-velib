"""Diagnostics for Vélib' Métropole.

For an account entry, the raw private API payloads are included (with personal
data redacted) so users can share the response structure in bug reports.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import VelibConfigEntry
from .coordinator import VelibAccountCoordinator

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    "address",
    "contactDetails",
    "name",
    "firstName",
    "lastName",
    "email",
    "login",
    "phone",
    "phoneNumber",
    "mobilePhone",
    "birthDate",
    "dateOfBirth",
    "customerExternalCode",
    "externalCode",
    "accessId",
    "cardNumber",
    "maskedPan",
    "iban",
    "card",
    "token",
    "unique_id",
    "title",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VelibConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data.coordinator
    result: dict[str, Any] = {"entry": async_redact_data(entry.as_dict(), TO_REDACT)}
    if isinstance(coordinator, VelibAccountCoordinator):
        data = coordinator.data
        result["getAllInfosUser"] = async_redact_data(data.infos, TO_REDACT)
        result["trips"] = [async_redact_data(t.raw, TO_REDACT) for t in data.trips]
        result["total_trips"] = data.total_trips
    else:
        result["stations"] = {
            code: {k: str(v) if v is not None else None for k, v in asdict(s).items()}
            for code, s in coordinator.data.items()
        }
    return result
