"""Behavior of the irrigation zone flow check blueprint in a real Home Assistant."""

from __future__ import annotations

import asyncio

from homeassistant.core import Event, HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import NAMESPACE

BLUEPRINT = f"{NAMESPACE}/irrigation_zone_flow_check.yaml"
ZONE = "switch.front_lawn"
OTHER = "switch.side_beds"
POWER = "sensor.pump_power"
MEAN = "sensor.pump_power_mean"
EVENT = "test_flow_check_alert"

# The README's example calibration: 500 W baseline and 100 W per unit, so 1750 W is 12.5 GPM.
BASELINE_W = 500
PER_UNIT_W = 100
NORMAL_W = "1750"


def automation_config(**inputs) -> dict:
    base = {
        "zones": [ZONE, OTHER],
        "expected_flow": {ZONE: 12.5},
        "pump_power": POWER,
        "baseline_power": BASELINE_W,
        "power_per_flow_unit": PER_UNIT_W,
        "start_delay": 0,
        "open_timeout": 1,
        "sample_interval": 1,
        "alert_actions": [
            {
                "event": EVENT,
                "event_data": {
                    "alert_type": "{{ alert_type }}",
                    "title": "{{ title }}",
                    "message": "{{ message }}",
                    "zone": "{{ zone }}",
                    "zone_name": "{{ zone_name }}",
                    "measured_flow": "{{ measured_flow }}",
                    "expected_flow": "{{ expected_flow }}",
                    "flow_unit": "{{ flow_unit }}",
                },
            }
        ],
    }
    base.update(inputs)
    return {
        "alias": "Zone flow check",
        "use_blueprint": {"path": BLUEPRINT, "input": base},
    }


async def setup(hass: HomeAssistant, power: str = "300", **inputs) -> list[Event]:
    hass.states.async_set(ZONE, "off", {"friendly_name": "Front lawn"})
    hass.states.async_set(OTHER, "off", {"friendly_name": "Side beds"})
    hass.states.async_set(POWER, power, {"unit_of_measurement": "W", "device_class": "power"})
    assert await async_setup_component(hass, "automation", {"automation": [automation_config(**inputs)]})
    await hass.async_block_till_done()
    assert hass.states.get("automation.zone_flow_check").state == "on"
    alerts: list[Event] = []
    hass.bus.async_listen(EVENT, alerts.append)
    return alerts


async def run_for(hass: HomeAssistant, seconds: float) -> None:
    await asyncio.sleep(seconds)
    await hass.async_block_till_done()


async def test_valve_that_never_opens_is_reported(hass):
    alerts = await setup(hass)
    hass.states.async_set(ZONE, "on", {"friendly_name": "Front lawn"})
    await run_for(hass, 2)
    assert len(alerts) == 1
    data = alerts[0].data
    assert data["alert_type"] == "valve_not_open"
    assert data["zone"] == ZONE
    assert data["zone_name"] == "Front lawn"
    assert data["title"] == "Sprinkler valve did not open"
    assert "Front lawn" in data["message"]


async def test_normal_flow_raises_no_alert(hass):
    alerts = await setup(hass, power=NORMAL_W)
    hass.states.async_set(ZONE, "on", {"friendly_name": "Front lawn"})
    await run_for(hass, 3.5)
    assert alerts == []


async def test_high_flow_is_reported(hass):
    alerts = await setup(hass, power="3000")
    hass.states.async_set(ZONE, "on", {"friendly_name": "Front lawn"})
    await run_for(hass, 3.5)
    assert [a.data["alert_type"] for a in alerts] == ["flow_high"]
    data = alerts[0].data
    assert float(data["measured_flow"]) == 25.0
    assert float(data["expected_flow"]) == 12.5
    assert data["flow_unit"] == "GPM"
    assert "broken head or pipe" in data["message"]


async def test_low_flow_is_reported(hass):
    alerts = await setup(hass, power="700")
    hass.states.async_set(ZONE, "on", {"friendly_name": "Front lawn"})
    await run_for(hass, 3.5)
    assert [a.data["alert_type"] for a in alerts] == ["flow_low"]
    assert float(alerts[0].data["measured_flow"]) == 2.0


async def test_difference_inside_the_percent_band_is_quiet(hass):
    # 12.5 expected; 30 percent is 3.75, so 15.5 (2050 W) is inside the band.
    alerts = await setup(hass, power="2050")
    hass.states.async_set(ZONE, "on", {"friendly_name": "Front lawn"})
    await run_for(hass, 3.5)
    assert alerts == []


async def test_minimum_tolerance_protects_small_zones(hass):
    # 5 expected; 30 percent is only 1.5, but the 3 unit minimum keeps 7.5 (1250 W) quiet.
    alerts = await setup(hass, power="1250", expected_flow={ZONE: 5})
    hass.states.async_set(ZONE, "on", {"friendly_name": "Front lawn"})
    await run_for(hass, 3.5)
    assert alerts == []


async def test_zone_without_expected_flow_gets_only_the_valve_check(hass):
    alerts = await setup(hass, power="3000")
    hass.states.async_set(OTHER, "on", {"friendly_name": "Side beds"})
    await run_for(hass, 3.5)
    assert alerts == []


async def test_zone_without_expected_flow_still_reports_a_closed_valve(hass):
    alerts = await setup(hass)
    hass.states.async_set(OTHER, "on", {"friendly_name": "Side beds"})
    await run_for(hass, 2)
    assert [a.data["alert_type"] for a in alerts] == ["valve_not_open"]


async def test_zone_turned_off_before_sampling_raises_no_alert(hass):
    alerts = await setup(hass, power="3000")
    hass.states.async_set(ZONE, "on", {"friendly_name": "Front lawn"})
    # Plain sleep: async_block_till_done would wait for the whole run to finish first.
    await asyncio.sleep(0.5)
    hass.states.async_set(ZONE, "off", {"friendly_name": "Front lawn"})
    await run_for(hass, 3)
    assert alerts == []


async def test_flow_conditions_can_skip_the_flow_check(hass):
    hass.states.async_set("sensor.drive_state", "fault_recovery")
    alerts = await setup(
        hass,
        power="3000",
        flow_conditions=[{"condition": "state", "entity_id": "sensor.drive_state", "state": "running"}],
    )
    hass.states.async_set(ZONE, "on", {"friendly_name": "Front lawn"})
    await run_for(hass, 3.5)
    assert alerts == []


async def test_averaged_power_is_used_for_flow_when_given(hass):
    # Instant power is high (pump hunting); the averaged sensor shows normal flow.
    hass.states.async_set(MEAN, NORMAL_W, {"unit_of_measurement": "W", "device_class": "power"})
    alerts = await setup(hass, power="3000", pump_power_mean=MEAN)
    hass.states.async_set(ZONE, "on", {"friendly_name": "Front lawn"})
    await run_for(hass, 3.5)
    assert alerts == []


async def test_custom_conversion_and_unit(hass):
    # 2 W per L/min above a 200 W baseline: 260 W is 30 L/min against 60 expected.
    alerts = await setup(
        hass,
        power="260",
        expected_flow={ZONE: 60},
        running_power=250,
        baseline_power=200,
        power_per_flow_unit=2,
        flow_unit="L/min",
    )
    hass.states.async_set(ZONE, "on", {"friendly_name": "Front lawn"})
    await run_for(hass, 3.5)
    assert [a.data["alert_type"] for a in alerts] == ["flow_low"]
    assert float(alerts[0].data["measured_flow"]) == 30.0
    assert "L/min" in alerts[0].data["message"]


async def test_default_alert_creates_a_persistent_notification(hass):
    assert await async_setup_component(hass, "persistent_notification", {})
    hass.states.async_set(ZONE, "off", {"friendly_name": "Front lawn"})
    hass.states.async_set(POWER, "300", {"unit_of_measurement": "W", "device_class": "power"})
    config = automation_config()
    del config["use_blueprint"]["input"]["alert_actions"]
    assert await async_setup_component(hass, "automation", {"automation": [config]})
    await hass.async_block_till_done()
    created = []
    hass.bus.async_listen("call_service", lambda e: created.append(e.data) if e.data.get("service") == "create" else None)
    hass.states.async_set(ZONE, "on", {"friendly_name": "Front lawn"})
    await run_for(hass, 2)
    assert created and created[0]["domain"] == "persistent_notification"
    assert created[0]["service_data"]["notification_id"] == f"irrigation_flow_check_{ZONE}"


async def test_calibration_inputs_are_required(hass):
    hass.states.async_set(ZONE, "off", {"friendly_name": "Front lawn"})
    hass.states.async_set(POWER, "3000", {"unit_of_measurement": "W", "device_class": "power"})
    config = automation_config()
    del config["use_blueprint"]["input"]["baseline_power"]
    del config["use_blueprint"]["input"]["power_per_flow_unit"]
    await async_setup_component(hass, "automation", {"automation": [config]})
    await hass.async_block_till_done()
    state = hass.states.get("automation.zone_flow_check")
    assert state is None or state.state == "unavailable"
    alerts: list[Event] = []
    hass.bus.async_listen(EVENT, alerts.append)
    hass.states.async_set(ZONE, "on", {"friendly_name": "Front lawn"})
    await run_for(hass, 2)
    assert alerts == []
