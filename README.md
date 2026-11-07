# Solvis Heating für Home Assistant

Liest die Werte einer Solvis-Heizung (SolvisControl SC-2) über die XML-Schnittstelle der **SolvisRemote** aus.

Fork von [Lurchi70/ha-solvis-heating](https://github.com/Lurchi70/ha-solvis-heating) (0.0.x), ab 1.0.0 grundlegend überarbeitet. Getestet mit SolvisMax 6 (Gas, Solarthermie, Warmwasserstation) und SolvisRemote.

## Was 1.0.0 gegenüber 0.0.x ändert

**Behobene Fehler**
- Der Optionen-Dialog stürzte seit HA 2025.12 ab und war auch vorher wirkungslos (der Code las nur die Erstkonfiguration).
- Fehlgeschlagene Abrufe lieferten still leere Daten. Alle Entitäten sprangen kurz auf `unknown`, was falsche Zustandswechsel und Trigger erzeugte. Jetzt werden einzelne Aussetzer überbrückt; erst nach 3 Fehlschlägen in Folge werden die Entitäten `unavailable`.
- Nicht angeschlossene Fühler (Rohwert 250,0 °C) und nicht vorhandene Zähler (65535) erscheinen als `unknown` statt als Messwert.
- Solar-Spreizung als Temperaturdifferenz (`temperature_delta`) statt als Absoluttemperatur in K.
- Durchflüsse mit korrekter Einheit (L/min, L/h) und Geräteklasse. Der `customize.yaml`-Workaround entfällt.
- Ofen- und Ost-West-Option überschrieben Brenner Stufe 2 bzw. Pumpe Heizkreis 3.

**Entfernt**
- `burner_capacity` und `burner_consumption`: Diese Werte waren Laufzeit in ganzen Stunden × fixe 27 kW und damit keine brauchbare Verbrauchsangabe. Für Gasverbrauch einen echten Gaszähler verwenden.
- Abhängigkeit `sc2xmlreader`: Der Decoder steckt jetzt in der Integration (`parser.py`).

**Neu**
- Abruf asynchron über die HTTP-Session von Home Assistant, Standardintervall 30 s (einstellbar 10–300 s).
- Funktionierende Optionen (Komponenten, Intervall), Neukonfiguration (Host, Zugangsdaten), Neuanmeldung bei abgelehntem Passwort.
- Deutsche und englische Entitätsnamen.
- Zusätzliche Werte, standardmäßig deaktiviert: Reglerzeit, Fühler S14–S16, Raumfühler 1–3, Analogausgänge 1–4.
- Geräteinfo mit Anlagentyp und Systemnummer des Reglers, Diagnose-Download inkl. Rohdaten.

## Installation (HACS)

1. HACS → ⋮ → **Benutzerdefinierte Repositories** → `https://github.com/moster11/ha-solvis-heating`, Typ **Integration**.
2. **Solvis Heating** herunterladen und Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Solvis Heating.**

### Umstieg von Lurchi70/ha-solvis-heating

Bestehende Einträge werden beim ersten Start automatisch migriert. Entity-IDs, eigene Namen, Bereiche und Dashboards bleiben erhalten.

1. In HACS die alte Version entfernen. Dabei **nicht** neu starten.
2. Diesen Fork wie oben hinzufügen und herunterladen.
3. Home Assistant neu starten.
4. Falls vorhanden, die `customize`-Einträge für `sensor.solvis_remote_volume_stream_*` aus der `configuration.yaml` löschen.

Die Migration entfernt die beiden Brenner-Schätzwerte, übernimmt die Komponenten-Auswahl und stellt das alte Standardintervall von 10 s auf 30 s um.

## Entitäten

| Schlüssel | Kanal | Inhalt |
|---|---|---|
| `temperature_buffer_top` | S1 | Speicher oben |
| `temperature_warm_water_station` | S2 | Warmwasser |
| `temperature_buffer_reference` | S3 | Speicherreferenz |
| `temperature_buffer_heating_top` | S4 | Heizungspuffer oben |
| `temperature_solar_flow` / `_return` | S5 / S6 | Solar Vorlauf / Rücklauf |
| `solar_pressure` | S7 | Solardruck (nur mit Drucksensor) |
| `temperature_solar_panel` | S8 | Kollektor |
| `temperature_buffer_heating_bottom` | S9 | Heizungspuffer unten |
| `temperature_outside` | S10 | Außentemperatur |
| `temperature_circulation` | S11 | Zirkulation |
| `temperature_heating_circuit_1_flow` / `2_flow` | S12 / S13 | Vorlauf Heizkreis 1 / 2 |
| `temperature_sensor_s14` / `s15` / `s16` | S14–S16 | freie Fühler (deaktiviert) |
| `temperature_solar_panel2` / `temperature_oven` | S16 | Kollektor 2 (Ost-West) / Ofen |
| `volume_stream_solar` | S17 | Durchfluss Solar (L/h) |
| `volume_stream_warm_water` | S18 | Durchfluss Warmwasser (L/min) |
| `temperature_room_1..3` | RF1–3 | Raumfühler (deaktiviert) |
| `analog_output_1..4` | AO1–4 | Analogausgänge, Rohwert (deaktiviert) |
| `runtime_burner`, `total_burner_start`, `total_burner_2nd_start` | Z1–Z3 | Laufzeit / Starts Brenner |
| `runtime_solar_pump` | Z4 | Laufzeit Solarpumpe |
| `solar_yield`, `solar_power` | SE, SL | Solarertrag (kWh) / -leistung (kW) |
| `temperature_solar_diff_flow_return` | S5−S6 | Solar Spreizung (K) |
| `controller_time`, `last_update` | – | Reglerzeit (deaktiviert) / letzter erfolgreicher Abruf |

Schaltausgänge als Binärsensoren: A1 Solarpumpe, A2 Pumpe Warmwasserstation, A3/A4/A6 Pumpe Heizkreis 1/2/3, A5 Zirkulationspumpe, A6/A7 Solarventile (Ost-West), A8–A11 Mischer Heizkreis 1/2, A12 Brenner, A13 Brenner Stufe 2 bzw. Ofenpumpe, A14 Ausgang A14.

### Solarertrag im Energie-Dashboard

Home Assistant hat keine Kategorie für Solarthermie. `solar_yield` lässt sich als **Gas**-Quelle eintragen.

## Grenzen

- Nur lesend: Die XML-Schnittstelle erlaubt keine Steuerung. Steuerung ginge nur per Modbus (ab SC-2-Firmware MA205), das unterstützt diese Integration nicht.
- 15 Statusbytes im Datensatz sind noch nicht entschlüsselt. Der Diagnose-Download enthält die Rohdaten.

## Entwicklung

```bash
pip install -r requirements_test.txt
pytest
```

## Lizenz

MIT. Ursprünglicher Code und Datenformat © 2023 Lurchi70.
