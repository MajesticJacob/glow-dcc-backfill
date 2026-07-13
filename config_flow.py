from __future__ import annotations

from aiohttp import ClientError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GlowDccApiClient, GlowDccApiError, GlowDccAuthError
from .const import (
    DOMAIN,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_RESOURCE_ID,
    CONF_TARIFF_COUNT,
    CONF_API_RATE,
    CONF_CHEAP_RATE,
    CONF_STANDARD_RATE,
    CONF_PEAK_RATE,
    CONF_CHEAP_START,
    CONF_CHEAP_END,
    CONF_PEAK_START,
    CONF_PEAK_END,
    TARIFF_COUNT_SINGLE,
    TARIFF_COUNT_TWO,
    TARIFF_COUNT_THREE,
    DEFAULT_TARIFF_COUNT,
    DEFAULT_CHEAP_START,
    DEFAULT_CHEAP_END,
    DEFAULT_PEAK_START,
    DEFAULT_PEAK_END,
    DEFAULT_STANDARD_RATE,
)


def login_schema() -> vol.Schema:
    """Return Bright login schema."""
    return vol.Schema(
        {
            vol.Required(CONF_EMAIL): str,
            vol.Required(CONF_PASSWORD): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.PASSWORD,
                )
            ),
        }
    )


def tariff_count_schema(existing: dict | None = None) -> vol.Schema:
    """Ask how many tariff rates the user has each day."""
    existing = existing or {}

    return vol.Schema(
        {
            vol.Required(
                CONF_TARIFF_COUNT,
                default=existing.get(CONF_TARIFF_COUNT, DEFAULT_TARIFF_COUNT),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {
                            "value": TARIFF_COUNT_SINGLE,
                            "label": "1 rate per day - flat tariff",
                        },
                        {
                            "value": TARIFF_COUNT_TWO,
                            "label": "2 rates per day - day/night or Economy 7",
                        },
                        {
                            "value": TARIFF_COUNT_THREE,
                            "label": "3 rates per day - cheap/standard/peak",
                        },
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


def tariff_details_schema(
    tariff_count: str,
    existing: dict | None = None,
    api_rate: float | None = None,
) -> vol.Schema:
    """Return tariff detail schema based on number of rates."""
    existing = existing or {}

    default_rate = api_rate
    if default_rate is None:
        default_rate = existing.get(CONF_STANDARD_RATE, DEFAULT_STANDARD_RATE)

    fields = {}

    if tariff_count == TARIFF_COUNT_SINGLE:
        fields[
            vol.Required(
                CONF_STANDARD_RATE,
                default=existing.get(CONF_STANDARD_RATE, default_rate),
            )
        ] = float

    elif tariff_count == TARIFF_COUNT_TWO:
        fields[
            vol.Required(
                CONF_STANDARD_RATE,
                default=existing.get(CONF_STANDARD_RATE, default_rate),
            )
        ] = float
        fields[
            vol.Required(
                CONF_CHEAP_RATE,
                default=existing.get(CONF_CHEAP_RATE, default_rate),
            )
        ] = float
        fields[
            vol.Required(
                CONF_CHEAP_START,
                default=existing.get(CONF_CHEAP_START, DEFAULT_CHEAP_START),
            )
        ] = str
        fields[
            vol.Required(
                CONF_CHEAP_END,
                default=existing.get(CONF_CHEAP_END, DEFAULT_CHEAP_END),
            )
        ] = str

    else:
        fields[
            vol.Required(
                CONF_STANDARD_RATE,
                default=existing.get(CONF_STANDARD_RATE, default_rate),
            )
        ] = float
        fields[
            vol.Required(
                CONF_CHEAP_RATE,
                default=existing.get(CONF_CHEAP_RATE, default_rate),
            )
        ] = float
        fields[
            vol.Required(
                CONF_CHEAP_START,
                default=existing.get(CONF_CHEAP_START, DEFAULT_CHEAP_START),
            )
        ] = str
        fields[
            vol.Required(
                CONF_CHEAP_END,
                default=existing.get(CONF_CHEAP_END, DEFAULT_CHEAP_END),
            )
        ] = str
        fields[
            vol.Required(
                CONF_PEAK_RATE,
                default=existing.get(CONF_PEAK_RATE, default_rate),
            )
        ] = float
        fields[
            vol.Required(
                CONF_PEAK_START,
                default=existing.get(CONF_PEAK_START, DEFAULT_PEAK_START),
            )
        ] = str
        fields[
            vol.Required(
                CONF_PEAK_END,
                default=existing.get(CONF_PEAK_END, DEFAULT_PEAK_END),
            )
        ] = str

    return vol.Schema(fields)


def resource_label(resource: dict) -> str:
    """Build a readable resource label."""
    location = resource.get("virtual_entity_name") or "Unknown location"
    name = resource.get("name") or resource.get("description") or "Electricity consumption"
    unit = resource.get("base_unit") or "kWh"
    resource_id = resource.get("resource_id") or "unknown"

    return f"{location} - {name} ({unit}) - {resource_id[:8]}"


def build_options(
    tariff_count: str,
    user_input: dict,
    api_rate: float | None,
) -> dict:
    """Build stored tariff options."""
    standard_rate = float(user_input.get(CONF_STANDARD_RATE, api_rate or DEFAULT_STANDARD_RATE))
    cheap_rate = float(user_input.get(CONF_CHEAP_RATE, 0))
    peak_rate = float(user_input.get(CONF_PEAK_RATE, 0))

    return {
        CONF_TARIFF_COUNT: tariff_count,
        CONF_API_RATE: api_rate,
        CONF_STANDARD_RATE: standard_rate,
        CONF_CHEAP_RATE: cheap_rate,
        CONF_PEAK_RATE: peak_rate,
        CONF_CHEAP_START: user_input.get(CONF_CHEAP_START, DEFAULT_CHEAP_START),
        CONF_CHEAP_END: user_input.get(CONF_CHEAP_END, DEFAULT_CHEAP_END),
        CONF_PEAK_START: user_input.get(CONF_PEAK_START, DEFAULT_PEAK_START),
        CONF_PEAK_END: user_input.get(CONF_PEAK_END, DEFAULT_PEAK_END),
    }


class GlowDccBackfillConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Glow DCC Backfill."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._email: str | None = None
        self._password: str | None = None
        self._resources: list[dict] = []
        self._resource_id: str | None = None
        self._resource_title: str = "Glow DCC Backfill"
        self._api_rate: float | None = None
        self._tariff_count: str = DEFAULT_TARIFF_COUNT

    @staticmethod
    def async_get_options_flow(config_entry):
        """Create the options flow."""
        return GlowDccBackfillOptionsFlow(config_entry)

    def _client(self) -> GlowDccApiClient:
        """Create API client."""
        return GlowDccApiClient(
            session=async_get_clientsession(self.hass),
            email=self._email or "",
            password=self._password or "",
            timezone=self.hass.config.time_zone,
            resource_id=self._resource_id,
        )

    async def _load_api_rate(self) -> None:
        """Best-effort load of current unit rate from Glowmarkt."""
        self._api_rate = None

        if not self._resource_id:
            return

        try:
            self._api_rate = await self._client().async_get_current_unit_rate(
                self._resource_id
            )
        except Exception:
            self._api_rate = None

    async def async_step_user(self, user_input=None):
        """Handle Bright login and resource discovery."""
        errors = {}

        if user_input is not None:
            self._email = user_input[CONF_EMAIL]
            self._password = user_input[CONF_PASSWORD]

            try:
                self._resources = (
                    await self._client().async_list_electricity_consumption_resources()
                )
            except GlowDccAuthError:
                errors["base"] = "invalid_auth"
            except (GlowDccApiError, ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                if not self._resources:
                    errors["base"] = "no_resources"
                elif len(self._resources) == 1:
                    resource = self._resources[0]
                    self._resource_id = resource[CONF_RESOURCE_ID]
                    self._resource_title = resource_label(resource)
                    await self._load_api_rate()
                    return await self.async_step_tariff_count()
                else:
                    return await self.async_step_resource()

        return self.async_show_form(
            step_id="user",
            data_schema=login_schema(),
            errors=errors,
        )

    async def async_step_resource(self, user_input=None):
        """Allow the user to choose an electricity consumption resource."""
        if user_input is not None:
            self._resource_id = user_input[CONF_RESOURCE_ID]

            for resource in self._resources:
                if resource.get(CONF_RESOURCE_ID) == self._resource_id:
                    self._resource_title = resource_label(resource)
                    break

            await self._load_api_rate()
            return await self.async_step_tariff_count()

        options = [
            {
                "value": resource[CONF_RESOURCE_ID],
                "label": resource_label(resource),
            }
            for resource in self._resources
            if resource.get(CONF_RESOURCE_ID)
        ]

        schema = vol.Schema(
            {
                vol.Required(CONF_RESOURCE_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="resource",
            data_schema=schema,
            errors={},
        )

    async def async_step_tariff_count(self, user_input=None):
        """Ask how many daily rates the user has."""
        if user_input is not None:
            self._tariff_count = user_input[CONF_TARIFF_COUNT]
            return await self.async_step_tariff_details()

        return self.async_show_form(
            step_id="tariff_count",
            data_schema=tariff_count_schema(),
            errors={},
        )

    async def async_step_tariff_details(self, user_input=None):
        """Collect tariff details."""
        if user_input is not None:
            await self.async_set_unique_id(self._resource_id)
            self._abort_if_unique_id_configured()

            data = {
                CONF_EMAIL: self._email,
                CONF_PASSWORD: self._password,
                CONF_RESOURCE_ID: self._resource_id,
            }

            options = build_options(
                tariff_count=self._tariff_count,
                user_input=user_input,
                api_rate=self._api_rate,
            )

            return self.async_create_entry(
                title=self._resource_title,
                data=data,
                options=options,
            )

        return self.async_show_form(
            step_id="tariff_details",
            data_schema=tariff_details_schema(
                tariff_count=self._tariff_count,
                api_rate=self._api_rate,
            ),
            errors={},
        )


class GlowDccBackfillOptionsFlow(config_entries.OptionsFlow):
    """Options flow for changing tariff settings."""

    def __init__(self, config_entry):
        self.config_entry = config_entry
        self._tariff_count = config_entry.options.get(
            CONF_TARIFF_COUNT,
            DEFAULT_TARIFF_COUNT,
        )

    async def async_step_init(self, user_input=None):
        """Ask how many daily rates to use."""
        if user_input is not None:
            self._tariff_count = user_input[CONF_TARIFF_COUNT]
            return await self.async_step_tariff_details()

        return self.async_show_form(
            step_id="init",
            data_schema=tariff_count_schema(dict(self.config_entry.options)),
            errors={},
        )

    async def async_step_tariff_details(self, user_input=None):
        """Manage tariff options."""
        existing = dict(self.config_entry.options)
        api_rate = existing.get(CONF_API_RATE)

        if user_input is not None:
            return self.async_create_entry(
                title="",
                data=build_options(
                    tariff_count=self._tariff_count,
                    user_input=user_input,
                    api_rate=api_rate,
                ),
            )

        return self.async_show_form(
            step_id="tariff_details",
            data_schema=tariff_details_schema(
                tariff_count=self._tariff_count,
                existing=existing,
                api_rate=api_rate,
            ),
            errors={},
        )