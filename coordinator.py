from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GlowDccApiClient
from .const import (
    DOMAIN,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_RESOURCE_ID,
    CONF_TARIFF_COUNT,
    CONF_CHEAP_RATE,
    CONF_STANDARD_RATE,
    CONF_PEAK_RATE,
    CONF_CHEAP_START,
    CONF_CHEAP_END,
    CONF_PEAK_START,
    CONF_PEAK_END,
    DEFAULT_TARIFF_COUNT,
    DEFAULT_CHEAP_START,
    DEFAULT_CHEAP_END,
    DEFAULT_PEAK_START,
    DEFAULT_PEAK_END,
    DEFAULT_STANDARD_RATE,
)

_LOGGER = logging.getLogger(__name__)


class GlowDccBackfillCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator for Glow DCC Backfill."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry

        session = async_get_clientsession(hass)

        self.client = GlowDccApiClient(
            session=session,
            email=entry.data[CONF_EMAIL],
            password=entry.data[CONF_PASSWORD],
            timezone=hass.config.time_zone,
            resource_id=entry.data[CONF_RESOURCE_ID],
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=1),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from Glowmarkt."""
        options = self.entry.options

        try:
            return await self.client.async_get_yesterday(
                tariff_count=options.get(CONF_TARIFF_COUNT, DEFAULT_TARIFF_COUNT),
                cheap_rate=float(options.get(CONF_CHEAP_RATE, 0)),
                standard_rate=float(
                    options.get(CONF_STANDARD_RATE, DEFAULT_STANDARD_RATE)
                ),
                peak_rate=float(options.get(CONF_PEAK_RATE, 0)),
                cheap_start=options.get(CONF_CHEAP_START, DEFAULT_CHEAP_START),
                cheap_end=options.get(CONF_CHEAP_END, DEFAULT_CHEAP_END),
                peak_start=options.get(CONF_PEAK_START, DEFAULT_PEAK_START),
                peak_end=options.get(CONF_PEAK_END, DEFAULT_PEAK_END),
            )
        except Exception as err:
            raise UpdateFailed(f"Error fetching Glow DCC data: {err}") from err