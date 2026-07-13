from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GlowDccBackfillCoordinator


@dataclass(frozen=True, kw_only=True)
class GlowDccSensorEntityDescription(SensorEntityDescription):
    """Description for a Glow DCC sensor."""

    value_fn: Callable[[dict], Any]


SENSORS: tuple[GlowDccSensorEntityDescription, ...] = (
    GlowDccSensorEntityDescription(
        key="yesterday_cost",
        name="Yesterday Cost",
        icon="mdi:currency-gbp",
        native_unit_of_measurement="GBP",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda data: data.get("total_cost"),
    ),
    GlowDccSensorEntityDescription(
        key="yesterday_total_kwh",
        name="Yesterday Total kWh",
        icon="mdi:home-lightning-bolt",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda data: data.get("total_kwh"),
    ),
    GlowDccSensorEntityDescription(
        key="yesterday_cheap_kwh",
        name="Yesterday Cheap kWh",
        icon="mdi:counter",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda data: data.get("cheap_kwh"),
    ),
    GlowDccSensorEntityDescription(
        key="yesterday_standard_kwh",
        name="Yesterday Standard kWh",
        icon="mdi:counter",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda data: data.get("standard_kwh"),
    ),
    GlowDccSensorEntityDescription(
        key="yesterday_peak_kwh",
        name="Yesterday Peak kWh",
        icon="mdi:counter",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda data: data.get("peak_kwh"),
    ),
    GlowDccSensorEntityDescription(
        key="yesterday_cheap_cost",
        name="Yesterday Cheap Cost",
        icon="mdi:currency-gbp",
        native_unit_of_measurement="GBP",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda data: data.get("cheap_cost"),
    ),
    GlowDccSensorEntityDescription(
        key="yesterday_standard_cost",
        name="Yesterday Standard Cost",
        icon="mdi:currency-gbp",
        native_unit_of_measurement="GBP",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda data: data.get("standard_cost"),
    ),
    GlowDccSensorEntityDescription(
        key="yesterday_peak_cost",
        name="Yesterday Peak Cost",
        icon="mdi:currency-gbp",
        native_unit_of_measurement="GBP",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda data: data.get("peak_cost"),
    ),
    GlowDccSensorEntityDescription(
        key="yesterday_slots",
        name="Yesterday Slots",
        icon="mdi:table-clock",
        value_fn=lambda data: data.get("slots"),
    ),
    GlowDccSensorEntityDescription(
        key="yesterday_latest_slot",
        name="Yesterday Latest Slot",
        icon="mdi:clock-check-outline",
        value_fn=lambda data: data.get("latest_slot_local"),
    ),
    GlowDccSensorEntityDescription(
        key="yesterday_date",
        name="Yesterday Date",
        icon="mdi:calendar",
        value_fn=lambda data: data.get("date"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Glow DCC Backfill sensors."""
    coordinator: GlowDccBackfillCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        GlowDccBackfillSensor(coordinator, entry, description)
        for description in SENSORS
    )


class GlowDccBackfillSensor(CoordinatorEntity[GlowDccBackfillCoordinator], SensorEntity):
    """Glow DCC Backfill sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GlowDccBackfillCoordinator,
        entry: ConfigEntry,
        description: GlowDccSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)

        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Glow DCC Backfill",
            "manufacturer": "Community",
            "model": "DCC backfill",
        }

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if not self.coordinator.data:
            return None

        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        if not self.coordinator.data:
            return {}

        return {
            "source": "Glowmarkt/Bright DCC",
            "date": self.coordinator.data.get("date"),
            "slots": self.coordinator.data.get("slots"),
            "latest_slot_local": self.coordinator.data.get("latest_slot_local"),
        }