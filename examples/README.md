# Examples

Working implementations for Section 11 integrations.

## Available Methods

| Folder | Description | Status |
|--------|-------------|--------|
| [SETUP_ASSISTANT.md](../SETUP_ASSISTANT.md) | Interactive AI-guided setup — paste into any AI chat | ✅ Ready |
| [json-auto-sync](json-auto-sync/) | Automated GitHub Actions sync (every 15 min) | ✅ Ready |
| [json-local-sync](json-local-sync/) | Automated local sync for agentic platforms (no GitHub) | ✅ Ready |
| [json-on-demand](json-on-demand/) | On-demand sync from phone or browser — no local Python | ✅ Ready |
| [json-manual](json-manual/) | Manual export from Mac/PC | ✅ Ready |
| [reports](reports/) | Pre/post/weekly/block/season report templates | ✅ Ready |
| [agentic](agentic/) | Write planned workouts to Intervals.icu calendar (code execution required) | ✅ Ready |
| [workout-library](workout-library/) | Structured workout templates for AI prescription | ✅ Ready |
| [json-examples](json-examples/) | Example JSON output / current schema reference | ✅ Ready |

---

## Quick Start

### Option A: Automated Sync (Recommended for web chat)

Best for: Always-fresh data via GitHub, zero maintenance after setup.

→ [json-auto-sync/SETUP.md](json-auto-sync/SETUP.md)

### Option B: Manual Export

Best for: One-off exports, different time ranges, no GitHub needed.

→ [json-manual/SETUP.md](json-manual/SETUP.md)

### Option C: Local Automated Sync

Best for: Agentic platforms (OpenClaw, Claude Code, Cowork, etc.) running on the same machine as your data. Always-fresh data, no GitHub needed, maximum privacy.

→ [json-local-sync/SETUP.md](json-local-sync/SETUP.md)

### Option D: On-Demand Sync

Best for: Phone or browser users who want fresh data without a schedule or local Python. Trigger a sync from your repo's README, download the results.

→ [json-on-demand/SETUP.md](json-on-demand/SETUP.md)

---

## Shared Files

Both methods use the same `sync.py` script and produce these files:

| File | Purpose | Auto-created |
|------|---------|--------------|
| `latest.json` | Current 7-day training data for AI consumption | Yes |
| `history.json` | Longitudinal data — daily (90d), weekly (180d), monthly (3y) | Yes |
| `intervals.json` | Per-interval segment data for recent structured sessions | Yes |
| `routes.json` | Route/terrain data for events with GPX/TCX attachments | When attachments exist |
| `ftp_history.json` | FTP tracking for Benchmark Index | Yes |
| `archive/` | Timestamped snapshots (auto-sync only) | Yes |

See [json-examples/](json-examples/) for example output showing the full current schema.

```bash
# Manual local export
python sync.py --output latest.json

# Push to GitHub
python sync.py

# Different time range
python sync.py --days 90 --output 90days.json
```

See individual SETUP.md files for detailed instructions.

---

## Data Output

All methods produce the same JSON structure compatible with Section 11 protocol:

```
latest.json
├── READ_THIS_FIRST      → AI instructions + quick stats + wellness_field_scales legend
├── metadata             → Timestamps, version
├── alerts               → Graduated severity flags (info → alarm)
├── readiness_decision   → Pre-computed go/modify/skip with signal breakdown
├── summary              → Activity breakdown by type
├── current_status
│   ├── fitness          → CTL, ATL, TSB, ramp_rate
│   ├── thresholds       → FTP, eFTP, LTHR, W', P-max, VO2max (per-sport)
│   └── current_metrics  → Weight, RHR, HRV, sleep, subjective state, vitals, body comp
├── derived_metrics      → Section 11 calculated values (see below)
│   ├── capability       → Durability, EF, HRRc trends + TID drift (7d vs 28d)
│   └── phase_detection  → Dual-stream phase detection with confidence
├── recent_activities    → Detailed activity data with zones, EF, HRRc, has_intervals, has_dfa, dfa_summary, effort_response, terrain_summary/weather_summary (outdoor only)
├── wellness_data        → Daily HRV, RHR, sleep, subjective state, vitals, nutrition, lifestyle
├── planned_workouts     → Upcoming scheduled sessions with workout_summary
├── workout_summary_stats → Planned-vs-actual matching statistics
├── weekly_summary       → Aggregated totals
└── race_calendar        → Upcoming races, taper/race-week alerts

history.json
├── data_range           → Earliest/latest dates, total months
├── ftp_timeline         → Indoor/outdoor FTP change history
├── data_gaps            → Detected gaps in training data
├── summaries            → Period aggregates (90d, 180d, 1y, 2y, 3y)
├── daily_90d            → Day-by-day detail (last 90 days)
├── weekly_180d          → Week-by-week (last 180 days)
└── monthly_1y/2y/3y     → Month-by-month (up to 3 years)

intervals.json (on-demand — load when analyzing activities with has_intervals: true or has_dfa: true)
├── generated_at         → Timestamp
├── version              → sync.py version
└── activities[]         → Per-activity interval segments
    ├── activity_id      → Matches id in latest.json recent_activities
    ├── interval_summary → Group summary (e.g., "4x 9m56s 259w")
    └── intervals[]      → WORK + RECOVERY segments with power, HR, cadence, zone, decoupling

routes.json (on-demand — load when planned events have has_terrain: true)
├── generated_at         → Timestamp
├── sync_version         → sync.py version
├── script_hash          → Cache invalidation hash
└── events[]             → Per-event terrain analysis
    ├── event_id/name/date/category
    ├── attachment_id    → GPX/TCX file identifier
    └── terrain_summary  → Distance, elevation, course character, polyline
        ├── climbs[]     → Cat 4–HC with position, gradient, coords
        └── descents[]   → Recovery windows with position, gradient, coords
```

> **Note on terrain data location:** `routes.json` holds **planned-route** terrain (events with GPX/TCX attachments). **Completed-activity** terrain — what was actually ridden — lives embedded on each outdoor activity in `latest.json`'s `recent_activities[]` as `terrain_summary` and `weather_summary`. Same base schema, different time direction. See SECTION_11.md "Completed-Activity Terrain & Weather" for interpretation rules.

### Derived Metrics

Pre-calculated values for Section 11 compliance — AI should use these, not calculate its own:

| Metric | Description |
|--------|-------------|
| `acwr` | Acute:Chronic Workload Ratio (0.8–1.3 optimal) |
| `recovery_index` | HRV/RHR composite (>1.0 = good recovery) |
| `monotony` / `strain` | Training variability (Foster) |
| `grey_zone_percentage` | Z3 time % — minimize in polarized training |
| `quality_intensity_percentage` | Z4+ time % — target ~20% |
| `easy_time_ratio` | Easy time ratio — target ~0.80 |
| `consistency_index` | Plan adherence (completed/planned) |
| `phase_detected` | Auto-detected: Build, Base, Peak, Taper, Deload, Recovery, Overreached, null |
| `phase_detection` | Full phase detection object: phase, confidence, reason_codes, basis (dual-stream), phase_duration_weeks |
| `benchmark_indoor` / `benchmark_outdoor` | 8-week FTP progression |
| `seiler_tid_7d` / `seiler_tid_28d` | Seiler TID classification (Polarized/Pyramidal/Threshold/HIT/Base) |
| `capability.durability` | Aggregate decoupling 7d/28d mean + trend (improving/stable/declining) |
| `capability.tid_comparison` | TID drift detection (consistent/shifting/acute_depolarization) |
| `readiness_decision` | Pre-computed go/modify/skip with priority ladder (P0–P3) and signal breakdown |
| `capability.efficiency_factor` | Aerobic efficiency (power÷HR normalized) 7d/28d with trend |
| `capability.hrrc` | Heart rate recovery 7d/28d aggregate trend (improving/stable/declining) |

---

## Report Templates

The [reports/](reports/) folder contains Section 11-compliant templates:

| Template | Use case |
|----------|----------|
| `PRE_WORKOUT_REPORT_TEMPLATE.md` | Briefing before a session |
| `POST_WORKOUT_REPORT_TEMPLATE.md` | Analysis after a session |
| `WEEKLY_REPORT_TEMPLATE.md` | End-of-week summary |
| `BLOCK_REPORT_TEMPLATE.md` | End-of-block phase assessment |
| `SEASON_REPORT_TEMPLATE.md` | On-demand annual-arc trajectory + YoY |
| `*_EXAMPLES.md` | Anonymized examples showing normal and threshold-breach scenarios |

Use these to standardize AI coaching output across platforms.