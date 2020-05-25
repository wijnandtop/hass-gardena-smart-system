"""Support for Gardena mower."""

import logging
from datetime import timedelta

from homeassistant.core import callback
from homeassistant.components.vacuum import (
    StateVacuumEntity,
    SUPPORT_BATTERY,
    SUPPORT_RETURN_HOME,
    SUPPORT_STATE,
    SUPPORT_STOP,
    SUPPORT_START,
    STATE_PAUSED,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_RETURNING,
    STATE_ERROR,
    ATTR_BATTERY_LEVEL,
)

from .const import (
    ATTR_ACTIVITY,
    ATTR_BATTERY_STATE,
    ATTR_NAME,
    ATTR_OPERATING_HOURS,
    ATTR_RF_LINK_LEVEL,
    ATTR_RF_LINK_STATE,
    ATTR_SERIAL,
    CONF_MOWER_DURATION,
    DEFAULT_MOWER_DURATION,
    DOMAIN,
    GARDENA_LOCATION,
)
from .sensor import GardenaSensor


_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)

SUPPORT_GARDENA = (
    SUPPORT_BATTERY | SUPPORT_RETURN_HOME | SUPPORT_STOP | SUPPORT_START | SUPPORT_STATE
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Gardena smart mower system."""
    entities = []
    for mower in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type("MOWER"):
        entities.append(GardenaSmartMower(hass, mower, config_entry.options))

    _LOGGER.debug("Adding mower as vacuums: %s", entities)
    async_add_entities(entities, True)


class GardenaSmartMower(StateVacuumEntity):
    """Representation of a Gardena Connected Mower."""

    def __init__(self, hass, mower, options):
        """Initialize the Gardena Connected Mower."""
        self._device = mower
        self._options = options
        self._name = "{}".format(self._device.name)
        self._unique_id = f"{self._device.serial}-mower"
        self._state = None
        self._error_message = ""

    async def async_added_to_hass(self):
        """Subscribe to events."""
        self._device.add_callback(self.update_callback)

    @property
    def should_poll(self) -> bool:
        """No polling needed for a vacuum."""
        return False

    def update_callback(self, device):
        """Call update for Home Assistant when the device is updated."""
        self.schedule_update_ha_state(True)

    async def async_update(self):
        """Update the states of Gardena devices."""
        _LOGGER.debug("Running Gardena update")
        # Managing state
        state = self._device.state
        _LOGGER.debug("Mower has state %s", state)
        if state in ["WARNING", "ERROR", "UNAVAILABLE"]:
            _LOGGER.debug("Mower has an error")
            self._state = STATE_ERROR
            self._error_message = self._device.last_error_code
        else:
            _LOGGER.debug("Getting mower state")
            activity = self._device.activity
            _LOGGER.debug("Mower has activity %s", activity)
            if activity == "PAUSED":
                self._state = STATE_PAUSED
            elif activity in [
                "OK_CUTTING",
                "OK_CUTTING_TIMER_OVERRIDDEN",
                "OK_LEAVING",
            ]:
                self._state = STATE_CLEANING
            elif activity == "OK_SEARCHING":
                self._state = STATE_RETURNING
            elif activity in [
                "OK_CHARGING",
                "PARKED_TIMER",
                "PARKED_PARK_SELECTED",
                "PARKED_AUTOTIMER",
            ]:
                self._state = STATE_DOCKED
            elif activity == "NONE":
                self._state = None
                _LOGGER.debug("Mower has no activity")

    @property
    def name(self):
        """Return the name of the device."""
        return self._device.name

    @property
    def supported_features(self):
        """Flag lawn mower robot features that are supported."""
        return SUPPORT_GARDENA

    @property
    def battery_level(self):
        """Return the battery level of the lawn mower."""
        return self._device.battery_level

    @property
    def state(self):
        """Return the status of the lawn mower."""
        return self._state

    @property
    def available(self):
        """Return True if the device is available."""
        return self._device.state != "UNAVAILABLE"

    def error(self):
        """Return the error message."""
        if self._state == STATE_ERROR:
            return self._error_message
        return ""

    @property
    def device_state_attributes(self):
        """Return the state attributes of the lawn mower."""
        return {
            ATTR_ACTIVITY: self._device.activity,
            ATTR_BATTERY_LEVEL: self._device.battery_level,
            ATTR_BATTERY_STATE: self._device.battery_state,
            ATTR_RF_LINK_LEVEL: self._device.rf_link_level,
            ATTR_RF_LINK_STATE: self._device.rf_link_state,
            ATTR_OPERATING_HOURS: self._device.operating_hours,
        }

    def start(self):
        """Start the mower."""
        self.turn_on()

    @property
    def option_mower_duration(self) -> int:
        return self._options.get(CONF_MOWER_DURATION, DEFAULT_MOWER_DURATION)

    def turn_on(self):
        """Start cleaning or resume mowing."""
        duration = self.option_mower_duration * 60
        self._device.start_seconds_to_override(duration)

    def turn_off(self):
        """Stop mowing."""
        self._device.park_until_next_task()

    def return_to_base(self, **kwargs):
        """Set the lawn mower to return to the dock."""
        self.turn_off()

    def stop(self, **kwargs):
        """Stop the lawn mower."""
        self.turn_off()

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_info(self):
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._device.serial)
            },
            "name": self._device.name,
            "manufacturer": "Gardena",
            "model": self._device.model_type,
        }
