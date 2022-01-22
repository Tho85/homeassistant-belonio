"""Platform for Belonio sensor"""


from datetime import timedelta
import logging
import re

import async_timeout

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    ATTR_BARCODE_URL,
    ATTR_GIFTCARD,
    ATTR_GIFTCARDS,
    ATTR_ORIGINAL_AMOUNT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensor for pass config entry."""
    belonio = hass.data[DOMAIN][config_entry.entry_id]

    async def async_update_data():
        """Fetch data from Belonio"""
        await belonio.fetch_giftcards()
        await belonio.fetch_most_recent_giftcard()

        return { "all": belonio.giftcards, "recent": belonio.most_recent_giftcard }

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=timedelta(hours=1),
    )

    await coordinator.async_config_entry_first_refresh()

    new_devices = []
    new_devices.append(BelonioCountSensor(coordinator, f"{config_entry.title} Giftcard count", belonio))
    new_devices.append(BelonioAmountAvailableSensor(coordinator, f"{config_entry.title} Giftcard available amount", belonio))
    new_devices.append(BelonioMostRecentSensor(coordinator, f"{config_entry.title} Most recent giftcard", belonio))

    async_add_entities(new_devices)


class BelonioSensor(CoordinatorEntity, SensorEntity):
    """Base sensor for number of available giftcards."""

    def __init__(self, coordinator, name, belonio):
        """Initialize sensor."""
        super().__init__(coordinator)
        self._belonio = belonio
        self._attr_name = name

class BelonioCountSensor(BelonioSensor):
    @property
    def native_value(self):
        """Return the state of the sensor."""
        level = len(self.coordinator.data["all"])

        return level

    @property
    def extra_state_attributes(self):
        """Return giftcard details"""
        return { ATTR_GIFTCARDS: self.coordinator.data["all"] }

    @property
    def icon(self):
        return "mdi:wallet-giftcard"

class BelonioAmountAvailableSensor(BelonioSensor):
    @property
    def native_value(self):
        """Return the state of the sensor."""
        total = 0.0
        for giftcard in self.coordinator.data["all"]:
            total = total + float(giftcard["remainingAmount"]["amount"])

        return total

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return CURRENCY_EURO

    @property
    def icon(self):
        return "mdi:piggy-bank"

class BelonioMostRecentSensor(BelonioSensor):
    @property
    def native_value(self):
        """Return the state of the sensor."""
        return float(self.coordinator.data["recent"]["remainingAmount"]["amount"])

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return CURRENCY_EURO

    @property
    def _recent_giftcard(self):
        """Return all giftcards"""
        return self.coordinator.data["recent"]

    @property
    def _barcode_url(self):
        """Return giftcard barcode"""
        return re.sub(r'&rt=1$', "&rt=7", self._recent_giftcard["properties"]["eVoucherLink"])

    @property
    def extra_state_attributes(self):
        """Return giftcard details"""
        return {
            ATTR_GIFTCARD: self._recent_giftcard,
            ATTR_BARCODE_URL: self._barcode_url,
            ATTR_ORIGINAL_AMOUNT: float(self.coordinator.data["recent"]["amount"]["amount"]),
        }

    @property
    def icon(self):
        return "mdi:cash-register"
