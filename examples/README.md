# Examples

Working implementations and reference documentation for Section 11 integrations.

## Available Methods

| Folder | Description | Status |
|--------|-------------|--------|
| [SETUP_ASSISTANT.md](../SETUP_ASSISTANT.md) | Interactive AI-guided setup: paste into any AI chat | ✅ Ready |
| [json-auto-sync](json-auto-sync/) | Automated GitHub Actions sync (every 30 min) | ✅ Ready |
| [json-local-sync](json-local-sync/) | Automated local sync, read via runtime filesystem or cloud connector (no GitHub) | ✅ Ready |
| [json-on-demand](json-on-demand/) | On-demand sync from phone or browser (no local Python) | ✅ Ready |
| [json-manual](json-manual/) | Manual export from Mac/PC | ✅ Ready |
| [reports](reports/) | Pre/post/weekly/block/season/weather report templates | ✅ Ready |
| [agentic](agentic/) | Write planned workouts to Intervals.icu calendar (code execution required) | ✅ Ready |
| [agentic/fit-file-and-merger](agentic/fit-file-and-merger/) | Reusable multi-source FIT fusion, identity, verification, recovery and duplicate-cleanup reference | 📖 Reference |
| [workout-library](workout-library/) | Structured workout templates for AI prescription | ✅ Ready |
| [json-examples](json-examples/) | Fictional `.example.json` schema references, never athlete data | ✅ Ready |

---

## Quick Start

### Option A: Automated Sync (Recommended for web chat)

Best for: Scheduled data refresh via GitHub, with occasional manual sync.py updates.

→ [json-auto-sync/SETUP.md](json-auto-sync/SETUP.md)

### Option B: Manual Export

Best for: One-off exports, different time ranges, no GitHub needed.

→ [json-manual/SETUP.md](json-manual/SETUP.md)

### Option C: Local Automated Sync

Best for: Agentic platforms (OpenClaw, Claude Code, Cowork, Hermes, etc.) whose runtime can reach your data directory; where it cannot, the AI reads a cloud-synced copy via connector. Scheduled data refresh, no GitHub needed. See [Privacy & Security](../README.md#privacy--security).

→ [json-local-sync/SETUP.md](json-local-sync/SETUP.md)

### Option D: On-Demand Sync

Best for: Phone or browser users who want fresh data without a schedule or local Python. Trigger a sync from your repo's README, download the results.

→ [json-on-demand/SETUP.md](json-on-demand/SETUP.md)

---

## Shared Files

All four methods use the same `sync.py` script and produce these files:

| File | Purpose | Auto-created |
|------|---------|--------------|
| `latest.json` | Current 7-day training data for AI consumption | Yes |
| `history.json` | Longitudinal data: daily (90d), weekly (180d), monthly (3y) | Yes |
| `intervals.json` | Per-interval segment data for recent structured sessions | Yes |
| `routes.json` | Route/terrain data for events with GPX/TCX attachments | Every successful sync (`events` may be `[]`) |
| `saved_workouts.json` | Read-only mirror of the athlete's Intervals.icu saved workouts | Every sync (refreshed on its own 6h throttle) |
| `ftp_history.json` | FTP tracking for Benchmark Index | Yes |
| `archive/` | Daily UTC snapshots of `latest.json`, overwritten by later successful runs that day (GitHub workflow only, scheduled or Sync Now) | Yes |
| `route_eta_history.json` | Rolling outdoor ETA calibration retained between runs | Repository/local; excluded from download artifact |
| `maps/weather/` | Up to four ordered route-weather PNG pages per ride, six rides (24 pages), for AI chat display | Repository/local; excluded from download artifact |

Read `latest.json.data_overview` first for companion presence, relative locations and route/weather/map status. Resolve paths against the latest file's source; match filenames for folderless Manual uploads. Local/Manual retain the export folder; GitHub/On-demand use the shared sync-declared JSON/PNG publication list. Read and show matching PNG pages in their listed order, only after actually reading each image, and otherwise use text, with no extra Manual step.

See [json-examples/](json-examples/) for fictional example output of these files. They end in `.example.json`, are schema references only, and are never athlete data.

```bash
# Manual local export
python sync.py --output latest.json

# Push to GitHub
python sync.py

# Different time range
python sync.py --days 90 --output 90days.json
```

See individual SETUP.md files for detailed instructions.

### Requests and private state

Local sync keeps a one-minute timer while `check_interval_minutes` in `.sync_config.json` chooses checks every 1, 2, 5 or 10 minutes (default 1). One minute fits within the limit in the measured offline scenarios, not as a guarantee for every athlete. sync.py starts from your choice and can choose a slower step or pause when allowance requires it. A normal local run makes 4 Intervals.icu requests; first runs and refreshes cost more. The provider limits are 8,000 per API key per UTC day and 2,500 per 15 minutes. sync reserves 1,000 for other tools, leaving at most 7,000 daily; a lower reported limit wins. It counts only its own and push.py's requests in shared state, so choose a slower interval if other tools use the key. GitHub and On-demand ignore this setting and have no daily allowance controller or step-down. Their updated workflow can reuse slow sources for a quiet 4-request tick instead of about 31; refreshes and misses cost more. See [counts, refresh schedules and warnings](json-local-sync/SETUP.md#automate-the-refresh).

Private request accounting and source responses live in `<data folder>/state/`. Local and Manual keep them between runs, and whole-folder cloud sync uploads state too. A whole-folder connector can technically read it; `data_overview.state_note` and `READ_THIS_FIRST.state_note` explicitly tell AI tools to ignore it. GitHub and On-demand create state fresh on each runner but never keep, commit or upload it through the supplied workflows, so the AI does not receive it through those paths. Read `source_freshness` for status. See [locations, cleanup and SECTION11_STATE_DIR](json-local-sync/SETUP.md#private-sync-state).

We recommend one setup per user. Stop the old timer or workflow before changing the sync path or moving machines, to protect Intervals.icu. The count is per data folder, API key and athlete, with no coordination across folders.

---

## Data Output

All methods produce the same JSON structure compatible with Section 11 protocol:

```
latest.json
├── READ_THIS_FIRST      → AI instructions + quick stats + wellness_field_scales legend
├── metadata             → Timestamps, version
├── source_freshness     → Source status/age, local request budget, effective schedule and warnings
├── alerts               → Graduated severity flags (info → alarm)
├── readiness_decision   → Pre-computed go/modify/skip with signal breakdown
├── summary              → Activity breakdown by type
├── current_status
│   ├── fitness          → CTL, ATL, TSB, ramp_rate
│   ├── thresholds       → FTP, eFTP, LTHR, W', P-max, VO2max (per-sport)
│   └── current_metrics  → Weight, RHR, HRV, sleep, subjective state, vitals, body comp
├── sport_fun_facts      → Optional period-selected running/swimming/Nordic/rowing facts; cycling remains in fun_facts
├── derived_metrics      → Section 11 calculated values (see below)
│   ├── capability       → Durability (cycling), EF, HRRc trends + main-sport TID drift and per-sport curve deltas
│   └── phase_detection  → Dual-stream phase detection with confidence
├── recent_activities    → Detailed activity data with zones, EF, HRRc, has_intervals, has_dfa, dfa_summary, effort_response, has_structure, interval_data (plan_match/compliance/icu_detected), terrain_summary/weather_summary (outdoor only)
├── wellness_data        → Daily HRV, RHR, sleep, subjective state, vitals, nutrition, lifestyle
├── planned_workouts     → Upcoming scheduled sessions with workout_summary
├── workout_summary_stats → Planned-summary rendering statistics (including flat lists), not execution matching
├── weekly_summary       → Aggregated totals
└── race_calendar        → Upcoming races, taper/race-week alerts

history.json
├── data_range           → Earliest/latest dates, total months
├── ftp_timeline         → Indoor/outdoor FTP change history
├── data_gaps            → Detected gaps in training data
├── summaries            → Period aggregates (90d, 180d, 1y, 2y, 3y)
├── daily_90d            → Day-by-day detail (last 90 days)
├── sport_fun_facts      → Optional completed-week Season facts for selected running/swimming/Nordic/rowing
├── weekly_180d          → Week-by-week (last 180 days)
└── monthly_1y/2y/3y     → Month-by-month (up to 3 years)

intervals.json (on-demand: load when analyzing activities with has_intervals: true, has_dfa: true or has_structure: true)
├── generated_at         → Timestamp
├── schema_version       → intervals.json contract version (integer)
├── version              → sync.py version
├── fetch_state{}        → INTERNAL retry/fetch bookkeeping; not a consumer contract
└── activities[]         → Per-activity interval segments
    ├── activity_id      → Matches id in latest.json recent_activities
    ├── session_structure → Plan-aware evidence for completion and atomic compliance; fallback is descriptive
    ├── interval_summary → Intervals.icu detected groups (e.g., "4x 9m56s 259w"), descriptive cross-check only
    ├── zone_basis       → What `zone` refers to: power | hr | pace (omitted if unresolved)
    └── intervals[]      → WORK + RECOVERY segments with power, HR, cadence, zone, timing

routes.json (on-demand: load when planned events have has_terrain: true)
├── generated_at         → Timestamp
├── sync_version         → sync.py version
├── script_hash          → Cache invalidation hash
└── events[]             → Per-event terrain analysis
    ├── event_id/name/date/category
    ├── attachment_id    → GPX/TCX file identifier
    └── terrain_summary  → Distance, elevation, course character, polyline
        ├── climbs[]     → Cat 4–HC with position, gradient, coords
        └── descents[]   → Recovery windows with position, gradient, coords

saved_workouts.json (on-demand: load when selecting, reusing, or discussing a saved workout)
├── generated_at         → Timestamp
├── schema_version       → saved_workouts.json contract version (integer)
├── version              → sync.py version
├── script_hash          → Producer identity hash
├── target_resolution    → "as_stored"; targets exactly as Intervals.icu holds them
├── refresh{}            → status (ok/stale/unavailable), consistency, last_success_at,
│                          last_content_change_at, refresh_interval_secs
├── counts{}             → folders, workouts (null when status is unavailable)
├── fetch_state{}        → INTERNAL throttle/retry bookkeeping; not a consumer contract
├── folders[]            → id, type, name, visibility, can_edit, read_only_workouts,
│                          upstream_num_workouts, num_workouts, workout_ids[]
└── workouts[]           → Complete saved workout definitions
    ├── id/name/type/sub_type/indoor/description/tags
    ├── moving_time, icu_training_load, icu_intensity, target, targets
    ├── folder_id/folder_name → canonical membership (null when unfiled)
    └── workout_doc      → Full structure as received; targets may be relative or absolute
```

> `latest.json` carries compact completed-step `interval_data.plan_match` through 28 days. `has_structure` points to detailed `session_structure` in `intervals.json` within 14-day retention; after expiry only the last summary is carried forward. Detailed thirds/WORK efforts appear only without usable plan windows. Read method/status and issues; plan match is not compliance. See the protocol's Completed Session Structure contract. Flat planned lists have summaries; sync does not emit inferred roles. Coaching interpretation follows SECTION_11's Main work rule using prescription structure, durations and targets, with name or description as context only and optional workout step text. See [Which interval data to use](../SECTION_11.md#which-interval-data-to-use).

> **Note on the two libraries:** `saved_workouts.json` mirrors the athlete's own saved workouts in Intervals.icu. It is **not** the [Workout Reference Library](workout-library/), which is the normative catalogue of session templates Section 11 designs plans from. Full description: [Saved Workouts Mirror](json-examples/README.md#saved-workouts-mirror).

> **Note on terrain data location:** `routes.json` holds **planned-route** terrain (events with GPX/TCX attachments). **Completed-activity** terrain (what was actually ridden) lives embedded on each outdoor activity in `latest.json`'s `recent_activities[]` as `terrain_summary` and `weather_summary`. Same base schema, different time direction. See SECTION_11.md "Completed-Activity Terrain & Weather" for interpretation rules.

### Derived Metrics

Pre-calculated values for Section 11 compliance: AI should use these, not calculate its own:

| Metric | Description |
|--------|-------------|
| `acwr` | Acute:Chronic Workload Ratio (0.8–1.3 optimal) |
| `recovery_index` | HRV/RHR composite (>1.0 = good recovery) |
| `monotony` / `strain` | Legacy all-sport training variability (Foster); reporting alarms use monotony_main_sports / strain_main_sports |
| `grey_zone_percentage` | Z3 time %: minimize in polarized training |
| `quality_intensity_percentage` | Z4+ time %: target ~20% |
| `easy_time_ratio` | Easy time ratio: target ~0.80 |
| `consistency_index` | Planned-date match ratio (matched dates / planned dates), not execution adherence |
| `phase_detected` | Auto-detected: Build, Base, Peak, Taper, Deload, Recovery, Overreached, null |
| `phase_detection` | Full phase detection object: phase, confidence, reason_codes, basis (dual-stream), phase_duration_weeks |
| `benchmark_indoor` / `benchmark_outdoor` | 8-week FTP progression |
| `report_intensity_7d` / `report_intensity_28d` | Period-local main sports, separate power/HR mapping buckets and weeks/sessions coverage. Legacy primary/all-sport fields retain their meanings. See [Report intensity source](../SECTION_11.md#report-intensity-source) |
| `capability.durability` | Cycling decoupling 7d/28d mean + trend (improving/stable/declining) |
| `capability.report_intensity_comparison` | Same sport/basis/mapping observed-session drift with coverage read from both ready blocks; partial/incompatible evidence has null drift. Legacy tid_comparison_primary and tid_comparison remain unchanged |
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
| `7_DAY_REPORT_TEMPLATE.md` | Rolling seven-date summary, on any day |
| `28_DAY_REPORT_TEMPLATE.md` | Rolling 28-day progression from four supplied chunks |
| `SEASON_REPORT_TEMPLATE.md` | Completed calendar weeks and calendar-matched YoY |
| `WEATHER_REPORT_TEMPLATE.md` | On-request five-day planned-route forecast/outlook |
| `*_EXAMPLES.md` | Anonymized examples showing normal and threshold-breach scenarios |

Use these to standardize AI coaching output across platforms.

## Checking source copies

If the AI asks for accessible data or invents values, check five layers: loaded project instructions, file access, source freshness, delivered-copy freshness and the AI's read in this response. Fetch/parse failures, context-window overflow, platform/runtime updates that drop instructions, stale imports/uploads, duplicate files and answers from memory can all produce these symptoms. Re-read the applicable [web](../PROJECT_INSTRUCTIONS_WEB.md) or [agentic](../PROJECT_INSTRUCTIONS_AGENTIC.md) contract; a fresh conversation can help when old context persists.

Ask which configured paths were tried and what failed. For filesystem access, check the actual working/data directory because the runtime may override its configuration. For a connector, check access in this project/chat to the specific repository or folder, not just account connection. For uploads, check that the needed files are attached here. For URL fetch, enable browsing and check the public raw path's username, repository, branch (normally `main`) and root filename against the configured source. A private raw URL without authentication returns 404, as can a wrong path.

After replacing a file, compare these markers with the source:

| Source | Marker |
|---|---|
| `SECTION_11.md` | `Protocol Version` |
| Root `latest.json`, not `archive/` | `export_freshness.generated_at` (legacy fallback: `metadata.last_updated`) |
| Official `DOSSIER.md`, if used | Authority, Official dossier location, Dossier revision and Last reviewed |
| Trend questions | `latest.json.history.age_days` and the relevant `history.json` |
| Interval or route detail | `generated_at` in `intervals.json` or `routes.json`, plus the detail's own status/freshness |
| Saved workouts | `saved_workouts.json.refresh.status` and `refresh.last_success_at` |

Matching markers support a file-read check; they do not prove every fact was read correctly. Ask whether more than one copy is reachable. Resolve conflicting official copies before use.

Use `export_freshness.generated_at` and a trusted current time, falling back to `metadata.last_updated`. Both are UTC (Z); only older exports without an offset need the sync machine's known timezone. If time or timezone is unknown, say age cannot be verified when relevant. Mention a missed `expected_update_by` once when relevant and look for a newer copy. Without a known deadline, expect under 12 hours and mention snapshot age at 12-24 hours when relevant; beyond 24 hours, request refresh for advice needing current data even during a permitted pause, and continue qualified coaching. Companions have separate schedules: history becomes due after more than 28 whole days or a script change, with scheduling/retry gates described in [GitHub troubleshooting](json-auto-sync/SETUP.md#historyjson-not-generated); saved workouts have their own throttle and retained-snapshot status. A newly written companion does not prove a fresh provider forecast or new route analysis.

For ordinary coaching, use export age and relevant `latest.json.source_freshness.warnings`, not a per-source freshness audit. Only `source_stale` is a source-data notice; other codes explain sync operation. Valid caches can stay usable as acquisition ages grow. Native availability, coverage and date rules still apply. See [Source freshness](json-examples/README.md#source-freshness).

If the source is current but the delivered copy is old, replace frozen uploads, refresh/re-import as the connector requires, and let cloud-drive synchronization finish first. Claude GitHub needs Sync now; Gemini imports must be repeated; ChatGPT retrieves permitted content on demand where available. Use [Platform Setup](../README.md#platform-setup) and its vendor links for other cases. Raw GitHub content can remain cached for a few minutes after a commit. Wait, then read again.

Every training metric must come from a current-response read. Compare the markers again after rereading; start a fresh conversation only if the AI still uses old copies. A fresh protocol download contains no private athlete data. Supply your own current JSON, task-required companions and optional official dossier. Never substitute the fictional `.example.json` files.
