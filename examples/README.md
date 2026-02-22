# Examples

Working implementations for Section 11 integrations.

## Available Methods

| Folder | Description | Status |
|--------|-------------|--------|
| [json-auto-sync](json-auto-sync/) | Automated GitHub Actions sync (every 15 min) | ✅ Ready |
| [json-manual](json-manual/) | Manual export from Mac/PC | ✅ Ready |
| [reports](reports/) | Pre/post workout report templates | ✅ Ready |

---

## Quick Start

### Option A: Automated Sync (Recommended)

Best for: Always-fresh data, zero maintenance after setup.

→ [json-auto-sync/SETUP.md](json-auto-sync/SETUP.md)

### Option B: Manual Export

Best for: One-off exports, different time ranges, no GitHub needed, most privacy.

→ [json-manual/SETUP.md](json-manual/SETUP.md)

---

## Shared Files

Both methods use the same `sync.py` script and produce these files:

| File | Purpose | Auto-created |
|------|---------|--------------|
| `latest.json` | Current 7-day training data for AI consumption | Yes |
| `history.json` | Longitudinal data — daily (90d), weekly (180d), monthly (3y) | Yes |
| `ftp_history.json` | FTP tracking for Benchmark Index | Yes |
| `archive/` | Timestamped snapshots (auto-sync only) | Yes |

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
├── READ_THIS_FIRST      → AI instructions + quick stats
├── metadata             → Timestamps, version
├── alerts               → Graduated severity flags (info → alarm)
├── summary              → Activity breakdown by type
├── current_status
│   ├── fitness          → CTL, ATL, TSB, ramp_rate
│   ├── thresholds       → FTP, eFTP, LTHR, W', P-max, VO2max
│   └── current_metrics  → Weight, RHR, HRV, sleep_quality, sleep_hours
├── derived_metrics      → Section 11 calculated values (see below)
│   ├── capability       → Durability trend + TID drift (7d vs 28d)
├── recent_activities    → Detailed activity data with zones
├── wellness_data        → Daily HRV, RHR, sleep, fatigue
├── planned_workouts     → Upcoming scheduled sessions
└── weekly_summary       → Aggregated totals

history.json
├── data_range           → Earliest/latest dates, total months
├── ftp_timeline         → Indoor/outdoor FTP change history
├── data_gaps            → Detected gaps in training data
├── summaries            → Period aggregates (90d, 180d, 1y, 2y, 3y)
├── daily_90d            → Day-by-day detail (last 90 days)
├── weekly_180d          → Week-by-week (last 180 days)
└── monthly_1y/2y/3y     → Month-by-month (up to 3 years)
```

### Derived Metrics

Pre-calculated values for Section 11 compliance — AI should use these, not calculate its own:

| Metric | Description |
|--------|-------------|
| `acwr` | Acute:Chronic Workload Ratio (0.8–1.3 optimal) |
| `recovery_index` | HRV/RHR composite (>1.0 = good recovery) |
| `monotony` / `strain` | Training variability (Foster) |
| `grey_zone_percentage` | Z3 time % — minimize in polarized training |
| `quality_intensity_percentage` | Z4+ time % — target ~20% |
| `polarisation_index` | Easy time ratio — target ~0.80 |
| `consistency_index` | Plan adherence (completed/planned) |
| `phase_detected` | Auto-detected: Base, Build, Peak, Recovery, Taper |
| `benchmark_indoor` / `benchmark_outdoor` | 8-week FTP progression |
| `seiler_tid_7d` / `seiler_tid_28d` | Seiler TID classification (Polarized/Pyramidal/Threshold/HIT/Base) |
| `capability.durability` | Aggregate decoupling 7d/28d mean + trend (improving/stable/declining) |
| `capability.tid_comparison` | TID drift detection (consistent/shifting/acute_depolarization) |

---

## Report Templates

The [reports/](reports/) folder contains Section 11-compliant templates:

| Template | Use case |
|----------|----------|
| `PRE_WORKOUT_TEMPLATE.md` | Briefing before a session |
| `POST_WORKOUT_TEMPLATE.md` | Analysis after a session |
| `*_EXAMPLES.md` | Anonymized examples showing normal and threshold-breach scenarios |

Use these to standardize AI coaching output across platforms.
