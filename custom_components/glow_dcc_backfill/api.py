from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from aiohttp import ClientSession

from .const import (
    TARIFF_COUNT_SINGLE,
    TARIFF_COUNT_TWO,
    TARIFF_COUNT_THREE,
)

APP_ID = "b0f1b774-a586-4f72-9edd-27ead8aa7a8d"
BASE_URL = "https://api.glowmarkt.com/api/v0-1"


class GlowDccApiError(Exception):
    """Base error for Glow DCC API."""


class GlowDccAuthError(GlowDccApiError):
    """Authentication failed."""


class GlowDccResourceError(GlowDccApiError):
    """Resource discovery or resource use failed."""


def _parse_time(value: str) -> int:
    """Convert HH:MM string to minutes since midnight."""
    hour_str, minute_str = value.split(":", 1)
    return int(hour_str) * 60 + int(minute_str)


def _in_window(slot_minute: int, start: str, end: str) -> bool:
    """Return true if a slot is inside a tariff window."""
    start_minute = _parse_time(start)
    end_minute = _parse_time(end)

    if start_minute == end_minute:
        return False

    if start_minute < end_minute:
        return start_minute <= slot_minute < end_minute

    return slot_minute >= start_minute or slot_minute < end_minute


def _normalise_virtual_entities(data) -> list[dict]:
    """Normalise virtual entity API responses."""
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("virtualEntities", "virtual_entities", "data", "ves"):
            value = data.get(key)
            if isinstance(value, list):
                return value

    return []


def _normalise_resources(data) -> list[dict]:
    """Normalise resource API responses."""
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("resources", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value

    return []


def _extract_rate_from_tariff(data) -> float | None:
    """Extract a unit rate from a tariff response.

    Glowmarkt commonly exposes currentRates.rate in pence/kWh.
    We return GBP/kWh.
    """
    if not isinstance(data, dict):
        return None

    possible_containers = [
        data.get("currentRates"),
        data.get("current_rates"),
        data.get("current"),
        data.get("tariff"),
        data,
    ]

    for container in possible_containers:
        if not isinstance(container, dict):
            continue

        for key in (
            "rate",
            "unitRate",
            "unit_rate",
            "unitRateInclVat",
            "unit_rate_inc_vat",
            "unit_rate_incl_vat",
        ):
            value = container.get(key)

            if value is None:
                continue

            try:
                rate = float(value)
            except (TypeError, ValueError):
                continue

            # Glowmarkt tariff rates are normally pence/kWh, e.g. 20.81.
            # Our integration stores GBP/kWh, e.g. 0.2081.
            if rate > 1:
                rate = rate / 100

            return round(rate, 4)

    return None


class GlowDccApiClient:
    """Client for Glowmarkt/Bright DCC readings."""

    def __init__(
        self,
        session: ClientSession,
        email: str,
        password: str,
        timezone: str,
        resource_id: str | None = None,
    ) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._resource_id = resource_id
        self._timezone = timezone
        self._token: str | None = None

    def set_resource_id(self, resource_id: str) -> None:
        """Set the active resource ID."""
        self._resource_id = resource_id

    async def _authenticate(self) -> str:
        """Authenticate and return token."""
        response = await self._session.post(
            f"{BASE_URL}/auth",
            headers={
                "Content-Type": "application/json",
                "applicationId": APP_ID,
            },
            json={
                "username": self._email,
                "password": self._password,
            },
        )

        data = await response.json(content_type=None)

        token = data.get("token")
        if not token:
            raise GlowDccAuthError(f"Authentication failed: {data}")

        self._token = token
        return token

    async def _get_token(self) -> str:
        """Get cached token or authenticate."""
        if self._token:
            return self._token

        return await self._authenticate()

    async def async_list_resources(self) -> list[dict]:
        """List all resources available on the Bright account."""
        token = await self._get_token()

        response = await self._session.get(
            f"{BASE_URL}/virtualentity",
            headers={
                "Content-Type": "application/json",
                "applicationId": APP_ID,
                "token": token,
            },
        )

        virtual_entity_data = await response.json(content_type=None)
        virtual_entities = _normalise_virtual_entities(virtual_entity_data)

        resources: list[dict] = []

        for virtual_entity in virtual_entities:
            ve_id = (
                virtual_entity.get("veId")
                or virtual_entity.get("ve_id")
                or virtual_entity.get("id")
            )

            ve_name = (
                virtual_entity.get("name")
                or virtual_entity.get("displayName")
                or virtual_entity.get("display_name")
                or "Unnamed location"
            )

            if not ve_id:
                continue

            resource_response = await self._session.get(
                f"{BASE_URL}/virtualentity/{ve_id}/resources",
                headers={
                    "Content-Type": "application/json",
                    "applicationId": APP_ID,
                    "token": token,
                },
            )

            resource_data = await resource_response.json(content_type=None)
            resource_list = _normalise_resources(resource_data)

            for resource in resource_list:
                resource_id = (
                    resource.get("resourceId")
                    or resource.get("resource_id")
                    or resource.get("id")
                )

                classifier = resource.get("classifier")
                if isinstance(classifier, dict):
                    classifier = classifier.get("name") or classifier.get("value")

                resources.append(
                    {
                        "virtual_entity_id": ve_id,
                        "virtual_entity_name": ve_name,
                        "resource_id": resource_id,
                        "name": resource.get("name"),
                        "description": resource.get("description"),
                        "classifier": classifier,
                        "base_unit": resource.get("baseUnit")
                        or resource.get("base_unit"),
                        "active": resource.get("active", True),
                    }
                )

        return resources

    async def async_list_electricity_consumption_resources(self) -> list[dict]:
        """List electricity consumption resources."""
        resources = await self.async_list_resources()

        return [
            resource
            for resource in resources
            if resource.get("classifier") == "electricity.consumption"
            and resource.get("resource_id")
            and resource.get("active", True)
        ]

    async def async_get_current_unit_rate(
        self,
        resource_id: str | None = None,
    ) -> float | None:
        """Return the current unit rate in GBP/kWh, if Glowmarkt provides it."""
        token = await self._get_token()

        selected_resource_id = resource_id or self._resource_id
        if not selected_resource_id:
            raise GlowDccResourceError("No resource_id has been selected")

        response = await self._session.get(
            f"{BASE_URL}/resource/{selected_resource_id}/tariff",
            headers={
                "Content-Type": "application/json",
                "applicationId": APP_ID,
                "token": token,
            },
        )

        data = await response.json(content_type=None)
        return _extract_rate_from_tariff(data)

    async def _catchup(self) -> None:
        """Ask Glowmarkt to catch up the resource."""
        if not self._resource_id:
            raise GlowDccResourceError("No resource_id has been selected")

        token = await self._get_token()

        await self._session.get(
            f"{BASE_URL}/resource/{self._resource_id}/catchup",
            headers={
                "Content-Type": "application/json",
                "applicationId": APP_ID,
                "token": token,
            },
        )

    async def _readings(self, target_date: str, offset: int) -> list:
        """Fetch PT30M readings for a date."""
        if not self._resource_id:
            raise GlowDccResourceError("No resource_id has been selected")

        token = await self._get_token()

        response = await self._session.get(
            f"{BASE_URL}/resource/{self._resource_id}/readings",
            headers={
                "Content-Type": "application/json",
                "applicationId": APP_ID,
                "token": token,
            },
            params={
                "from": f"{target_date}T00:00:00",
                "to": f"{target_date}T23:59:59",
                "period": "PT30M",
                "offset": str(offset),
                "function": "sum",
            },
        )

        data = await response.json(content_type=None)

        if "data" not in data:
            raise GlowDccApiError(f"No readings data returned: {data}")

        return data["data"]

    async def async_get_yesterday(
        self,
        tariff_count: str,
        cheap_rate: float,
        standard_rate: float,
        peak_rate: float,
        cheap_start: str,
        cheap_end: str,
        peak_start: str,
        peak_end: str,
    ) -> dict:
        """Fetch yesterday's readings and split by tariff."""
        tz = ZoneInfo(self._timezone)
        today = datetime.now(tz).date()
        yesterday = today - timedelta(days=1)
        target_date = yesterday.isoformat()

        midday = datetime.combine(yesterday, time(12, 0), tzinfo=tz)
        utc_offset = midday.utcoffset() or timedelta(0)
        api_offset = int(-(utc_offset.total_seconds() / 60))

        await self._catchup()
        readings = await self._readings(target_date, api_offset)

        tariff_count = str(tariff_count)

        cheap_kwh = 0.0
        standard_kwh = 0.0
        peak_kwh = 0.0

        slots = 0

        for reading in readings:
            if not isinstance(reading, list) or len(reading) < 2:
                continue

            kwh = float(reading[1] or 0)
            slot_minute = slots * 30

            if tariff_count == TARIFF_COUNT_SINGLE:
                standard_kwh += kwh

            elif tariff_count == TARIFF_COUNT_TWO:
                if _in_window(slot_minute, cheap_start, cheap_end):
                    cheap_kwh += kwh
                else:
                    standard_kwh += kwh

            elif tariff_count == TARIFF_COUNT_THREE:
                if _in_window(slot_minute, cheap_start, cheap_end):
                    cheap_kwh += kwh
                elif _in_window(slot_minute, peak_start, peak_end):
                    peak_kwh += kwh
                else:
                    standard_kwh += kwh

            else:
                standard_kwh += kwh

            slots += 1

        total_kwh = cheap_kwh + standard_kwh + peak_kwh

        cheap_cost = cheap_kwh * cheap_rate
        standard_cost = standard_kwh * standard_rate
        peak_cost = peak_kwh * peak_rate
        total_cost = cheap_cost + standard_cost + peak_cost

        latest_slot = max(slots - 1, 0)
        latest_hour = latest_slot // 2
        latest_minute = (latest_slot % 2) * 30

        return {
            "date": target_date,
            "tariff_count": tariff_count,
            "total_kwh": round(total_kwh, 3),
            "cheap_kwh": round(cheap_kwh, 3),
            "standard_kwh": round(standard_kwh, 3),
            "peak_kwh": round(peak_kwh, 3),
            "cheap_cost": round(cheap_cost, 2),
            "standard_cost": round(standard_cost, 2),
            "peak_cost": round(peak_cost, 2),
            "total_cost": round(total_cost, 2),
            "slots": slots,
            "latest_slot_local": f"{target_date} {latest_hour:02d}:{latest_minute:02d}",
        }