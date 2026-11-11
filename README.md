# EndOfTheLine-HA blueprints

Home Assistant blueprints, each tested in a real Home Assistant instance before release.

| Blueprint | What it does | Import |
| --- | --- | --- |
| [Irrigation zone flow check](#irrigation-zone-flow-check) | Uses pump power as a flow meter: catches sprinkler valves that do not open, broken heads and clogged zones | [Import](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FEndOfTheLine-HA%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Firrigation_zone_flow_check.yaml) |

To import by hand, go to **Settings > Automations & scenes > Blueprints > Import blueprint** and paste the
blueprint's file URL from this repository.

## Irrigation zone flow check

If your sprinklers are fed by a well or booster pump and you can read the pump's power in Home Assistant
(an energy monitor on its circuit, a smart plug or relay with power metering, or the drive's own
integration), the pump is already a rough flow meter. More water through the zone means more work for the
pump. This blueprint uses that to check every zone run:

1. **Valve check.** When a zone switch turns on, it waits for the pump to start drawing power. If the pump
   never picks up, the valve probably did not open: a broken wire, a failed solenoid or a dead relay
   channel. You get an alert, and the run stops there.
2. **Flow check.** For zones with an expected flow, it then reads pump power twice, a sample interval
   apart, averages the two readings and converts the average to flow. If the zone is running well above
   normal (often a broken head or pipe) or well below it (clogged nozzles or filter, or a valve that only
   partly opened), you get an alert.

Nothing here controls your irrigation. The blueprint only watches and reports. It works with any switch
that opens a zone, whatever controller is behind it.

### What you need

- A switch entity for each zone (`switch.*`) that is on while the zone runs.
- A power sensor for the pump, in watts, with the `power` device class.
- Optional: a time-weighted average of that power, for pumps whose power swings. A **Statistics** helper
  on the pump power sensor with the "Average (step)" characteristic and a max age of about 90 seconds
  works well. If you leave this empty, the instant power is sampled instead.

Variable-speed (constant-pressure) pumps work best, because their power follows flow closely. A
fixed-speed centrifugal pump still draws more power at higher flow, but the change is smaller, so check
your own numbers before relying on the flow alerts. The valve check works with either.

### Calibrating

The conversion is a straight line: **flow = (power - baseline power) / power per flow unit**.

1. Run two zones whose flow you know (from a water meter over a timed run, or the nozzle charts) and note
   the steady pump power for each.
2. **Power per flow unit** is the difference in power divided by the difference in flow.
3. **Baseline power** is the first zone's power minus its flow times the power per flow unit.
4. Check a third zone against the result, then fill in **Expected flow per zone** for every zone you want
   flow-checked, for example:

   ```yaml
   switch.front_lawn: 12.5
   switch.side_beds: 6
   ```

   Zones left out get the valve check only.

Example: 14 GPM reads 1900 W and 6 GPM reads 1100 W. Power per flow unit is (1900 - 1100) / (14 - 6) = 100 W,
and baseline power is 1900 - 14 x 100 = 500 W. These are made-up numbers to show the arithmetic. Baseline
power and power per flow unit have no defaults, so the automation will not save until you enter your own.
The flow unit is just a label, so liters per minute work the same way.

### Settings

| Setting | Default | Notes |
| --- | --- | --- |
| Zone switches | | The zones to watch. |
| Expected flow per zone | empty | Entity ID to normal flow. Zones not listed get only the valve check. |
| Pump power | | Instant power, used for the valve check. |
| Averaged pump power | empty | Used for the flow samples when set. |
| Pump running above | 650 W | Power that shows the pump is pumping. Set it above the pump's idle draw. |
| Baseline power | required | From calibration. |
| Power per flow unit | required | From calibration. |
| Flow unit | GPM | Used in messages. |
| Wait before checking | 20 s | Time after the zone turns on before watching the pump. |
| Time allowed for the pump to start | 70 s | After this, a pump that has not started counts as a valve that did not open. |
| Time between flow samples | 90 s | Wait before each of the two samples, so the flow check finishes about three minutes into a run. |
| Tolerance | 30 % | Allowed difference from the expected flow. |
| Minimum tolerance | 3 | Smallest allowed difference, in your flow unit. Keeps small zones, where a variable-speed pump hunts, from false alarms. |
| Only check flow when | none | Optional conditions for the flow check, for example that the pump drive is not reporting a fault. The valve check always runs. |
| Alert actions | persistent notification | What to do when a check fails. |

If a zone turns off before a check finishes, that run ends quietly.

### Alerts

The default alert is a persistent notification, one per zone, replaced by the next alert for the same
zone. To send it somewhere else, set your own **Alert actions**. These variables are available:

| Variable | Value |
| --- | --- |
| `alert_type` | `valve_not_open`, `flow_high` or `flow_low` |
| `title`, `message` | Ready-made text |
| `zone`, `zone_name` | The zone's entity ID and friendly name |
| `measured_flow`, `expected_flow`, `flow_unit` | The estimate, the expected value and the unit (`measured_flow` is 0 for `valve_not_open`) |

For example, a phone notification:

```yaml
- action: notify.mobile_app_your_phone
  data:
    title: "{{ title }}"
    message: "{{ message }}"
```

### Limits

The flow figure is an estimate from pump power, not a measurement. Pressure tank cycling, other water use
while a zone runs, and a pump that is still settling all move the number. Treat an alert as a reason to go
and look, and widen the tolerance for zones that alert when nothing is wrong. Requires Home Assistant
2024.10 or later.

## How these are tested

Each blueprint has tests that load it into a real Home Assistant instance with plain test states standing
in for the zones and the pump, then run it through normal, failing and edge-case scenarios. The tests run
on every push.

```bash
pip install homeassistant pytest pytest-asyncio ruff
ruff check .
pytest
```

## License

MIT. See [LICENSE](LICENSE).
