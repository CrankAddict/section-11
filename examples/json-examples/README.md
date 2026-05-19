# Example JSON Output

Example output from `sync.py` v3.86 for a fictional cyclist in a Build phase. Use these to understand the data schema before running your own sync.

**These are invented data** — realistic values for a ~12h/week multi-sport athlete (cycling + rowing + walks), CTL ~65, FTP 260/270 (indoor/outdoor). Not anonymized real data.

## Files

| File | Description |
|------|-------------|
| `latest.json` | Current 7-day snapshot — activities, wellness, fitness metrics, readiness decision, derived Section 11 values |
| `history.json` | Longitudinal data — daily (90d), weekly (180d), monthly (up to 3y) |
| `intervals.json` | Per-interval segment data for recent structured sessions |
| `routes.json` | Route/terrain data — climbs, descents, course character, polyline for events with GPX/TCX attachments |
| `ftp_history.json` | FTP change tracking for Benchmark Index calculation |

## Schema Version

These example files were generated from sync.py v3.86 / Section 11 v11.17. Key fields added to the schema since these examples were generated:

- `readiness_decision` — pre-computed go/modify/skip recommendation with signal breakdown
- `workout_summary_stats` — planned-vs-actual matching statistics
- `race_calendar` — upcoming races and taper/race-week alerts
- `has_intervals` — boolean flag indicating structured interval segments exist in intervals.json
- `has_dfa` — boolean flag indicating AlphaHRV DFA a1 data exists in intervals.json (independent from has_intervals)
- `dfa_summary` — compact DFA a1 rollup attached when has_dfa is true and data quality is sufficient (omitted otherwise)
- `efficiency_factor`, `hrrc` — per-activity capability metrics
- `description` — activity description passthrough
- `chat_notes` — athlete notes extracted from activity description (conditional)
- `wellness_field_scales` — 1-4 scale legend in READ_THIS_FIRST
- Expanded wellness fields (subjective state, vitals, body composition, nutrition, lifestyle, cycle)
- `zone_basis` on all TID/Seiler blocks
- `feel_count`, `avg_rpe`, `rpe_count` in weekly history rows
- `primary_sport`, `primary_sport_tss`, `sport_tss_breakdown` on weekly history rows
- `sport_type` on planned workouts
- `current_week_hard_days_completed`, `current_week_hard_days_total` in `phase_detection.basis.stream_2`
- `athlete_profile` — stable identity block (DOB, age, height, sex, location, timezone, platform tenure)
- `athlete_notes` — raw string passthrough of athlete's Intervals.icu notes
- `avg_temp_unit`, `wind_speed_unit`, `avg_speed_unit`, `max_speed_unit` — per-activity unit labels
- `terrain_summary` — per-activity terrain analysis (climbs, descents, course character, grade distribution) on outdoor activities; same base schema as routes.json with activity-specific additions, no polyline (raw streams available on demand via pull.py)
- `terrain_status` — set on outdoor activities when terrain data is unavailable: `"no_gps"`, `"no_elevation"`, or `"failed"` (terminal states; transient fetch errors retry on next sync without writing a status)
- `weather_summary` — per-activity weather block populated from Intervals' Open-Meteo data when `has_weather` is true; stable keys with explicit `units` block (wind/temp/rain) so values can be in any account-configured unit
- `weather_status` — `"unavailable"` when Intervals hasn't computed weather for the activity; re-evaluated each sync (never copied forward)

For the full field reference, see [SECTION_11.md](../../SECTION_11.md) (Derived Metrics table).
