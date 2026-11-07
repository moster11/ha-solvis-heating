# Solvis Heating for Home Assistant

Reads the values of a Solvis heating system (SolvisControl SC-2) through the XML interface of the **SolvisRemote**.

Fork of [Lurchi70/ha-solvis-heating](https://github.com/Lurchi70/ha-solvis-heating) (0.0.x), substantially reworked as of 1.0.0. Tested with a SolvisMax 6 (gas, solar thermal, warm water station) and SolvisRemote.

## What 1.0.0 changes compared to 0.0.x

**Fixes**
- The options flow crashed since HA 2025.12 and had no effect before that (the code only read the initial configuration).
- Failed polls silently returned empty data, so all entities briefly switched to `unknown`, causing false state changes and triggers. Single failures are now bridged; entities only become `unavailable` after 3 consecutive failures.
- Unconnected sensors (raw value 250.0 °C) and unavailable counters (65535) are reported as `unknown` instead of as a measurement.
- Solar flow/return difference as temperature delta (`temperature_delta`) instead of an absolute temperature in K.
- Flow rates with proper unit (L/min, L/h) and device class; the `customize.yaml` workaround is no longer needed.
- The oven and east/west options overwrote burner stage 2 and heating circuit 3 pump respectively.

**Removed**
- `burner_capacity` and `burner_consumption`: these were runtime in whole hours × a fixed 27 kW and therefore not a usable consumption value. Use a real gas meter for gas consumption.
- Dependency on `sc2xmlreader`: the decoder now lives in the integration (`parser.py`).

**New**
- Async polling via Home Assistant's HTTP session, default interval 30 s (configurable 10–300 s).
- Working options (components, interval), reconfiguration (host, credentials) and re-authentication when the password is rejected.
- German and English entity names.
- Additional values, disabled by default: controller time, sensors S14–S16, room sensors 1–3, analog outputs 1–4.
- Device info with the controller's system type and system number, diagnostics download including raw data.

## Installation (HACS)

1. HACS → ⋮ → **Custom repositories** → `https://github.com/moster11/ha-solvis-heating`, type **Integration**.
2. Download **Solvis Heating** and restart Home Assistant.
3. **Settings → Devices & services → Add integration → Solvis Heating.**

### Switching from Lurchi70/ha-solvis-heating

Existing entries are migrated automatically on first start. Entity IDs, custom names, areas and dashboards are kept.

1. Remove the old version in HACS. Do **not** restart yet.
2. Add this fork as above and download it.
3. Restart Home Assistant.
4. If present, delete the `customize` entries for `sensor.solvis_remote_volume_stream_*` from `configuration.yaml`.

The migration removes the two burner estimates, takes over the component selection and changes the old default interval of 10 s to 30 s.

## Entities

| Key | Channel | Content |
|---|---|---|
| `temperature_buffer_top` | S1 | Buffer top |
| `temperature_warm_water_station` | S2 | Warm water |
| `temperature_buffer_reference` | S3 | Buffer reference |
| `temperature_buffer_heating_top` | S4 | Heating buffer top |
| `temperature_solar_flow` / `_return` | S5 / S6 | Solar flow / return |
| `solar_pressure` | S7 | Solar pressure (only with pressure sensor) |
| `temperature_solar_panel` | S8 | Collector |
| `temperature_buffer_heating_bottom` | S9 | Heating buffer bottom |
| `temperature_outside` | S10 | Outside temperature |
| `temperature_circulation` | S11 | Circulation |
| `temperature_heating_circuit_1_flow` / `2_flow` | S12 / S13 | Heating circuit 1 / 2 flow |
| `temperature_sensor_s14` / `s15` / `s16` | S14–S16 | Unassigned sensors (disabled) |
| `temperature_solar_panel2` / `temperature_oven` | S16 | Collector 2 (east/west) / oven |
| `volume_stream_solar` | S17 | Solar flow rate (L/h) |
| `volume_stream_warm_water` | S18 | Warm water flow rate (L/min) |
| `temperature_room_1..3` | RF1–3 | Room sensors (disabled) |
| `analog_output_1..4` | AO1–4 | Analog outputs, raw value (disabled) |
| `runtime_burner`, `total_burner_start`, `total_burner_2nd_start` | Z1–Z3 | Burner runtime / starts |
| `runtime_solar_pump` | Z4 | Solar pump runtime |
| `solar_yield`, `solar_power` | SE, SL | Solar yield (kWh) / power (kW) |
| `temperature_solar_diff_flow_return` | S5−S6 | Solar flow/return difference (K) |
| `controller_time`, `last_update` | – | Controller time (disabled) / last successful poll |

Switching outputs as binary sensors: A1 solar pump, A2 warm water station pump, A3/A4/A6 heating circuit 1/2/3 pump, A5 circulation pump, A6/A7 solar valves (east/west), A8–A11 heating circuit 1/2 mixer, A12 burner, A13 burner stage 2 or oven pump, A14 output A14.

### Solar yield in the Energy dashboard

Home Assistant has no category for solar thermal. `solar_yield` can be added as a **gas** source.

## Limitations

- Read-only: the XML interface does not allow control. Control would require Modbus (SC-2 firmware MA205 or later), which this integration does not support.
- 15 status bytes in the payload are not decoded yet. The diagnostics download contains the raw data.

## Development

```bash
pip install -r requirements_test.txt
pytest
```

## License

MIT. Original code and data format © 2023 Lurchi70.
