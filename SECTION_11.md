# Section 11 — AI Coach Protocol

**Protocol Version:** 11.13  
**Last Updated:** 2026-03-05
**License:** [MIT](https://opensource.org/licenses/MIT)

### Changelog

**v11.13 — Readiness Decision (AAS Formalization):**
- Pre-computed `readiness_decision` replaces implicit go/modify/skip synthesis
- Priority ladder: P0 (safety stop) → P1 (acute overload) → P2 (accumulated fatigue) → P3 (green light)
- 7 signals evaluated: HRV, RHR, Sleep, TSB, ACWR, Feel, RI — each with green/amber/red/unavailable status
- Phase modifiers: Build loosens thresholds (3 amber), Taper/Race week tighten (1 amber), all others default (2 amber)
- Structured modification output: trigger categories + adjustment directions (intensity/volume/cap_zone)
- Wires into existing alerts (P0/P1 read tier-1 alarms, no duplication)
- AAS row removed from threshold table — replaced by `readiness_decision` reference
- sync.py v3.72: `_compute_readiness_decision()`, `_get_phase_modifiers()`, `_build_modification()`

**v11.12 — HRRc Integration + Phase Transition Narrative:**
- HRRc (heart rate recovery) added to activity output and capability namespace (7d/28d aggregate trend)
- HRRc: largest 60s HR drop (bpm) after exceeding threshold HR for >1 min. API field `icu_hrr`. Display only
- Trend: 7d mean vs 28d mean, >10% = meaningful. Min 1 session/7d, 3 sessions/28d
- Phase transition narrative guidance added to weekly/block report templates
- Phase timeline added to block report template
- References: Fecchio et al. (2019) HRR reproducibility; Lamberts et al. (2024) cyclist HRR reliability; Buchheit (2006)

**v11.11 — Phase Detection v2 (Dual-Stream Architecture):**
- Phase detection rewritten from single-point snapshot to dual-stream architecture
- Stream 1 (retrospective): 4-week lookback from `weekly_180d` — CTL slope, ACWR trend, hard-day density, monotony
- Stream 2 (prospective): planned workouts + race calendar — planned TSS delta, race proximity, plan coverage
- 8 phase states: Build, Base, Peak, Taper, **Deload** (new), Recovery, Overreached, null
- Classification priority: Overreached → Taper → Peak → Deload → Build/Base (scored) → Recovery → null
- Confidence model (high/medium/low) based on signal strength, data quality, stream agreement
- Hysteresis: bias toward previous phase when scores are close, prevents phase flapping
- Reason codes for full auditability (e.g., `RACE_IMMINENT_VOLUME_REDUCING`, `PLAN_GAP_NEXT_WEEK`)
- `phase_detection` output object with basis, confidence, reason_codes; backward-compat `phase_detected`/`phase_triggers` preserved
- Overreached fix: requires current-week ACWR >1.5 (not historical max); monotony threshold raised 2.0→2.5
- Weekly tier enriched: `acwr`, `monotony` (5+ day guard), `intensity_basis_breakdown`, `phase_detected` per row
- Old `_detect_phase` function removed

**v11.10 — Hard Day HR Zone Fallback:**
- Hard day counter now falls back to HR zones (`icu_hr_zone_times`) when power zones unavailable
- Running, SkiErg, rowing sessions were invisible to phase detection — fixed
- Conservative 2-rung HR ladder (Z4+ ≥ 10min, Z5+ ≥ 5min) per Seiler 3-zone model; power ladder unchanged
- Shared `_get_activity_zones()` and `_classify_hard_day()` helpers across all call sites
- Daily tier rows now include `intensity_basis` field (power/hr/mixed/null)
- `is_hard_day` returns `null` when no zone data exists (not `false`)
- `hard_days_this_week` field type updated to `number/null`
- Workout Reference hard session definition (§3.1) updated with both ladders

**v11.9 — Efficiency Factor Tracking:**
- Added Efficiency Factor (EF = NP ÷ Avg HR, Coggan) to Validated Optional Metrics
- EF pulled from Intervals.icu API (`icu_efficiency_factor`), aggregated 7d/28d in capability namespace
- Qualifying filters: cycling, VI ≤ 1.05, ≥ 20min, power+HR data
- Trend detection: improving/stable/declining (±0.03 threshold)
- Report templates updated: per-session in post-workout, aggregate in weekly/block/pre-workout

**v11.8 — Per-Sport Threshold Schema:**
- Added Per-Sport Threshold Schema defining `thresholds.sports` as a map keyed by sport family
- Thresholds (LTHR, max HR, FTP, threshold pace) are now sport-isolated; cross-sport application is forbidden
- Field semantics: `ftp` = primary threshold power for sport, `ftp_indoor` = indoor variant (if applicable)
- Sentinel rules: `threshold_pace = 0` normalizes to null; null pace requires null `pace_units`
- Fallback rule: missing sport family → skip threshold-dependent checks, flag explicitly
- Deterministic collision resolution for duplicate sport family mappings
- FTP Governance clarified as cycling-specific; Benchmark Index uses `thresholds.sports.cycling.ftp`
- Zone Distribution now requires sport-matched threshold lookup
- Validation Checklist item 1 updated for sport-family lookup
- Global estimates (`eftp`, `w_prime`, `w_prime_kj`, `p_max`, `vo2max`) remain at top level

**v11.7** — Workout Reference Library integration (26 templates, v0.5.0), selection rules, sequencing enforcement, WU/CD mandates, audit traceability via `session_template` field  
**v11.6** — Race-Week Protocol (D-7 to D-0), three-layer race awareness (calendar → taper onset → race week), event-type modifiers, go/no-go checklist, RACE_A/B/C priority detection via Intervals.icu  
**v11.5** — Capability Metrics, Seiler TID classification (Treff PI, 5-class, 7→3 zone mapping), dual-timeframe TID drift detection, aggregate durability (7d/28d mean decoupling)  
**v11.4** — Graduated alerts, history.json, confidence scoring, monotony deload context  
**v11.3** — Output format guidelines, report templates, communication style  
**v11.2** — Phase detection, load management hierarchy, zone distribution, durability sub-metrics, W′ balance  
**v11.1** — Reordered 11B/11C for logical flow  
**v11.0** — Foundation: modular split (11A/11B/11C), unified terminology

---

## Overview

This protocol defines how AI-based coaching systems should reason, query, and provide guidance within an athlete's endurance training ecosystem — ensuring alignment with scientific principles, dossier-defined parameters, and long-term objectives.

It enables AI systems to interpret, update, and guide an athlete's plan even without automated API access, maintaining evidence-based and deterministic logic.

---

### Dossier Architecture Note

Section 11 operates as a **self-contained AI protocol**. All metric definitions, validation ranges, evaluation hierarchies, and decision logic are defined within this document. The athlete's training dossier (DOSSIER.md) is a separate document containing athlete-specific data, goals, and configuration.

| Content Type | Location | Rationale |
|-------------|----------|-----------|
| Phase Detection Triggers | Section 11 (11A) | AI-specific classification logic |
| Validated Endurance Ranges | Section 11 (11A, subsection 7) | Audit thresholds within AI protocol |
| Load Management Metrics | Section 11 (11A, subsection 9) | AI decision logic |
| Periodisation Metrics | Section 11 (11A, subsection 9) | AI coaching logic |
| Durability Sub-Metrics | Section 11 (11A, subsection 9) | AI diagnostic logic |
| W′ Balance Metrics | Section 11 (11A, subsection 9) | AI optional metrics |
| Plan Adherence Monitoring | Section 11 (11A) | AI compliance tracking |
| Specificity Volume Tracking | Section 11 (11A) | AI event-prep logic |
| Benchmark Index | Section 11 (11A, FTP Governance) | AI longitudinal tracking |
| Zone Distribution Metrics | Section 11 (11A, subsection 9) | AI intensity monitoring |
| Seiler TID Classification | Section 11 (11A, Zone Distribution) | AI TID classification and drift detection |
| Aggregate Durability | Section 11 (11A, subsection 9) | AI durability trend tracking |
| Capability Metrics | Section 11 (11A, subsection 9) | AI capability-layer analysis (durability + TID comparison) |
| Validation Metadata | Section 11 (11C) | AI audit schema |

AI systems should reference the athlete dossier for athlete-specific values (FTP, zones, goals, schedule) and this protocol for all coaching logic, thresholds, and decision rules.

---

## 11 A. AI Coach Protocol (For LLM-Based Coaching Systems)

### Purpose

This protocol defines how an AI model should interact with an athlete's training data, apply validated endurance science, and make determinate, auditable recommendations — even without automated data sync from platforms like Intervals.icu, Garmin Connect, or Concept2 Logbook.

If the AI instance does not retain prior context (e.g., new chat or session), it must first reload the dossier, confirm current FTP, HRV, RHR, and phase before providing advice.

#### Data Mirror Integration

If the AI or LLM system is not directly or indirectly connected to the Intervals.icu API, it may reference an athlete-provided data mirror. There are three access methods — use the first available:

1. **Local files** — data directory on the same filesystem (agentic platforms)
2. **GitHub connector** — the athlete's data repo connected via the platform's native GitHub integration. The AI reads `latest.json`, `history.json`, and any other committed files (e.g., `DOSSIER.md`, `SECTION_11.md`) directly through the connector. No URLs needed. Connectors are read-only — they cannot trigger GitHub Actions or execute scripts.
3. **URL fetch** — raw GitHub URLs as defined in the athlete dossier

**Example endpoint format (URL fetch):**
```
https://raw.githubusercontent.com/[username]/[repo]/main/latest.json
```

**Example archive format:**
```
https://github.com/[username]/[repo]/tree/main/archive
```

**Example history format:**
```
https://raw.githubusercontent.com/[username]/[repo]/main/history.json
```

> **Note:** The actual URLs for your data mirror are defined in your athlete dossier. When using URL fetch, the AI must fetch from the dossier-specified endpoint. When using a GitHub connector, the AI reads directly from the connected repo.

This file represents a synchronized snapshot of current Intervals.icu metrics and activity summaries, structured for deterministic AI parsing and audit compliance.

The JSON data — whether accessed via local files, GitHub connector, or URL fetch — is considered a **Tier-1 verified mirror** of Intervals.icu and inherits its trust priority in the Data Integrity Hierarchy. All metric sourcing and computation must reference it deterministically, without modification or estimation.

If the data appears stale or outdated, the AI must explicitly request a data refresh before providing recommendations or generating analyses.

#### Per-Sport Threshold Schema

`current_status.thresholds` is the authoritative source for all threshold settings. Thresholds MUST be applied **per sport family**; cross-sport threshold application is not permitted.

**Structure:**

`current_status.thresholds` contains:
- **Athlete-level capability estimates** (not sport-specific): `eftp`, `w_prime`, `w_prime_kj`, `p_max`, `vo2max` — these remain at the top level and may be null
- **Per-sport-family settings** under `thresholds.sports`, a map keyed by sport family

**Canonical form:**

```json
"thresholds": {
  "eftp": null,
  "w_prime": null,
  "w_prime_kj": null,
  "p_max": null,
  "vo2max": 51.0,
  "sports": {
    "cycling": {
      "lthr": 164,
      "max_hr": 181,
      "threshold_pace": null,
      "pace_units": null,
      "ftp": 250,
      "ftp_indoor": null
    },
    "run": {
      "lthr": 174,
      "max_hr": 189,
      "threshold_pace": 4.1841006,
      "pace_units": "MINS_KM",
      "ftp": 375,
      "ftp_indoor": null
    }
  }
}
```

**Sport families** are stable, low-cardinality modality identifiers used for threshold isolation: `cycling`, `run`, `swim`, `rowing`, `ski`, `walk`, `strength`, `other`. These map from Intervals.icu activity types via the `SPORT_FAMILIES` constant in sync.py.

**Field semantics:**

| Field | Description |
|-------|-------------|
| `lthr` | Lactate threshold HR (bpm) for this sport; null if not configured |
| `max_hr` | Maximum HR (bpm) for this sport; null if not configured |
| `ftp` | Primary threshold power (watts) for this sport — cycling FTP, running rFTPw, rowing erg threshold, etc. |
| `ftp_indoor` | Indoor-specific threshold power (watts) if applicable — primarily cycling trainer FTP; null for most sports |
| `threshold_pace` | Threshold pace in meters/second (m/s); null if not set |
| `pace_units` | Display units enum (e.g., `MINS_KM`, `MINS_MILE`, `SECS_100M`); only meaningful when `threshold_pace` is non-null |

**Sentinel normalization rules:**
- If `threshold_pace` is `0`, `0.0`, or null → normalize to `null`
- If `threshold_pace` is null → `pace_units` MUST be null

**Sport-family lookup rule:**

When evaluating an activity or session:

1. Determine its sport family via `SPORT_FAMILIES` mapping
2. Look up `thresholds.sports[family]`
3. Use only that entry's values for all zone/threshold-dependent logic (zone boundaries, LT1/LT2 references, intensity classification, workout target conversions)

If no entry exists for that family: skip all threshold-dependent checks and explicitly flag `"No thresholds configured for [family]"`.

**Deterministic collision resolution:**

If multiple Intervals.icu sport settings map to the same family:

1. Prefer the entry with the highest count of populated (non-null) fields across `{ftp, ftp_indoor, lthr, max_hr, threshold_pace}`
2. If tied, select by activity type name (alphabetical) for deterministic stability
3. Record in audit metadata which entry was selected

#### History Data Mirror (history.json)

In addition to the real-time `latest.json` mirror, athletes may provide a `history.json` file containing longitudinal training data with tiered granularity:

- **90-day tier:** Daily resolution (date, hours, TSS, CTL/ATL/TSB, HRV, RHR, zone distribution, weight)
- **180-day tier:** Weekly aggregates (hours, TSS, CTL/ATL/TSB, zones, hard days, longest ride)
- **1/2/3-year tiers:** Monthly aggregates (hours, TSS, CTL range, zones, phase, data completeness)
- **FTP timeline:** Every FTP change with date and type (indoor/outdoor)
- **Data gaps:** Periods with missing or low data, flagged factually without inference

`history.json` is auto-generated by sync.py when missing or stale (>28 days), pulling fresh from the Intervals.icu API.

#### Data Source Usage Hierarchy

| Source | Purpose | When to Use |
|--------|---------|-------------|
| `latest.json` | Current state — readiness, load, go/modify/skip decisions | **Always primary.** All immediate coaching decisions use this. |
| `history.json` | Longitudinal context — trends, seasonal patterns, phase transitions | **Context only.** Reference when questions require historical depth. |

**Rules:**
1. `latest.json` is always primary. All immediate coaching decisions (readiness, load prescription, go/modify/skip) use `latest.json`.
2. `history.json` is context, never override. It informs interpretation but never overrides current readiness signals.
3. Reference `history.json` for: trend questions, seasonal pattern matching, phase transition decisions, FTP/Benchmark interpretation, and when data confidence is limited.
4. Do NOT reference `history.json` for: daily pre/post workout reports (unless investigating), simple go/modify/skip decisions where readiness is clear, or any time `latest.json` provides a definitive answer on its own.

---

### Core Evidence-Based Foundations

All AI analyses, interpretations, and recommendations must be grounded in validated, peer-reviewed endurance science frameworks:

| **Framework / Source**                                      | **Application Area**                                                                                                          |
| ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
|   Seiler’s 80/20 Polarized Training                         | Aerobic durability, balance of high/low intensity, and load control      				                                      |
|   San Millán’s Zone 2 Model                                 | Mitochondrial efficiency and metabolic health                          					                                      |
|   Friel’s Age-Adjusted Microcycle Model                     | Sustainable progression and fatigue management                         					                                      |
|   Banister’s TRIMP Impulse–Response Model                   | Load quantification and performance adaptation tracking                                                                       |
|   Foster’s Monotony & Strain Indices                        | Overuse detection and load variation optimization                                                                             |
|   Issurin’s Block Periodization Model (2008)                | Structured progression using accumulation → realization → taper blocks                                                        |
|   Gabbett’s Acute:Chronic Workload Ratio (2016)             | Load progression and injury-risk management (optimal ACWR 0.8–1.3)                                                            |
|   Péronnet & Thibault Endurance Modeling                    | Long-term power–duration curve development                                                                                    |
|   Cunningham & Faulkner Durability Metrics                  | Resistance to fatigue and drift thresholds                                                                                    |
|   Coggan’s Power–Duration and Efficiency Model              | Aerobic efficiency tracking, power curve modeling, and fatigue decay analysis                                                 |
|   Noakes’ Central Governor Model                            | Neural fatigue and perceptual regulation of performance; modern application via HRV × RPE for motivational readiness tracking |                                                    
|   Mujika’s Tapering Model                                   | Pre-event load reduction, adaptation optimization, and peaking strategies                                                     |
|   Sandbakk–Holmberg Integration Framework                   | Adaptive feedback synthesis across endurance, recovery, and environmental load                                                |
|   Sandbakk–Holberg Adaptive Action Score (AAS)              | Original inspiration for readiness synthesis. Replaced by deterministic `readiness_decision` (P0–P3 priority ladder) in v11.13 |
|   Randonneur Performance System (RPS) - Intervals.ICU forum | KPI-driven durability and adaptive feedback architecture for endurance progression                                            |
|   Friel’s Training Stress Framework                         | Plan adherence, TSS-based progression, and sustainable load control                                                           |
|   Skiba’s Critical Power Model                              | Fatigue decay and endurance performance prediction using CP–W′ curve                                                          |
|   Péronnet & Thibault (1989)                                | Long-term power-duration endurance curve validation (used for FTP trend smoothing)                                            |
|   Treff et al. (2019)                                       | Polarization Index formula for quantitative TID classification: PI = log10((Z1/Z2) × Z3 × 100)                               |
|   Maunder et al. (2021)                                     | Defined "durability" as resistance to deterioration in physiological profiling during prolonged exercise                       |
|   Rothschild & Maunder (2025)                               | Validated HR and power decoupling as field-based durability predictors in endurance athletes                                  |
|   Smyth (2022)                                              | Cardiac drift analysis across 82,303 marathon performances; validated decoupling as durability marker at scale                |

---

### Rolling Phase Logic

Training follows the **URF v5.1 Rolling Phase Model**, which classifies weekly load and recovery trends into evolving blocks — **Base → Build → Peak → Taper → Recovery** — derived directly from the interaction of these scientific models:

- **Banister (1975):** Fitness–fatigue impulse–response system for CTL/ATL/TSB dynamics
- **Seiler (2010, 2019):** Polarized intensity and adaptation rhythm
- **Issurin (2008):** Block periodization (accumulation → realization → taper)
- **Gabbett (2016):** Acute:Chronic workload ratio for safe progression

Each week's data (TSS, CTL, ATL, TSB, RI) is analyzed for trend and slope:

| **Metric**                | **Purpose**                              |
|---------------------------|------------------------------------------|
| ΔTSS % (Ramp Rate)        | Week-to-week load change                 |
| CTL / ATL Slope           | Long- and short-term stress trajectories |
| TSB                       | Readiness and recovery balance           |
| ACWR (0.8–1.3)            | Safe workload progression                |
| Recovery Index (RI ≥ 0.8) | Fatigue–recovery equilibrium             |

This produces a rolling phase block structure that adapts dynamically, ensuring progression and recovery follow real-world readiness rather than fixed calendar blocks.
The system continuously reflects the athlete’s true state — evolving naturally through accumulation, stabilization, and adaptation phases.

---

### Phase Detection Criteria

Phase detection uses a **dual-stream architecture** combining retrospective training history with prospective calendar data. This replaces single-point snapshot classification and eliminates common mislabels (e.g., deload weeks classified as taper/recovery).

**Stream 1 (Retrospective):** Rolling 4-week lookback from `weekly_180d` rows — CTL slope, ACWR trend, hard-day density, monotony trend.

**Stream 2 (Prospective):** Next 7–14 days of planned workouts + race calendar — planned TSS delta, hard sessions planned, race proximity, plan coverage (current/next ISO week).

**Phase States:**

| **Phase** | **Classification Logic** | **Key Thresholds** |
|-----------|------------------------|--------------------|
| Overreached | Safety gate — triggers immediately when detected | Current-week ACWR >1.5, or elevated monotony (>2.5) + ACWR >1.3 + rising trend |
| Taper | Race-anchored — requires race in calendar | Race (A/B priority) within 14 days + volume reducing (planned TSS ≤80% of recent avg) |
| Peak | Race approaching, fitness at cycle high | Race within 21 days + CTL within 5% of lookback max + volume NOT yet reducing + positive CTL slope |
| Deload | Calendar-driven load reduction within Build block | Build history (rising CTL + ≥1.5 hard days/week over 3+ weeks) + planned TSS ≤80% + no hard sessions planned. Confirmed if next week load resumes (≥80%). Medium confidence if next-week plan is empty. |
| Build | Scored — CTL rising + sustained hard days | CTL slope >1.0, hard-day avg ≥1.5, ACWR rising/stable. Planned week continues pattern (hard sessions ≥2). |
| Base | Scored — CTL stable + low hard days | CTL slope −1.0 to +1.0, hard-day avg ≤1.5, ACWR stable. |
| Recovery | Residual — declining load, no structured pattern | Declining CTL + <0.5 hard days/week + no Build history + no race proximity |
| null | Insufficient or conflicting data | <3 weeks lookback, Build/Base scores tied, streams conflict |

**Classification Priority Order:** Overreached → Taper → Peak → Deload → Build/Base (scored) → Recovery → null.

**Build/Base Scoring:** When neither safety gates nor calendar-anchored phases apply, Build and Base are scored from CTL slope, hard-day density, ACWR trend, and planned session intensity. The phase with a margin ≥2 wins. Margins <2 apply hysteresis (bias toward previous phase). Tied scores with no previous phase → null.

**Confidence Model:**

| **Confidence** | **Conditions** |
|---------------|---------------|
| high | Strong signal (margin ≥3), good data quality, streams agree |
| medium | Moderate signal (margin ≥2) or good data quality but weaker signal |
| low | Weak signal, poor data quality (<3 weeks), conflicting streams, or null phase |

Confidence is downgraded by: poor data quality (HR-only majority in lookback), empty plan coverage (no planned workouts), partial-week data.

**Hysteresis:** If the previous phase is among the top-2 candidates and not contradicted by data, it is preferred. This prevents phase flapping between similar states (e.g., Build ↔ Base at the margin).

**Deload→Build Transition:** When `previous_phase` is Deload, the classifier uses planned workout content (hard sessions planned) rather than TSS delta, because the trailing 3-week average includes the deload week and produces unreliable ratios.

**Reason Codes:** Every classification includes machine-readable reason codes for auditability (e.g., `RACE_IMMINENT_VOLUME_REDUCING`, `BUILD_HISTORY_REDUCED_LOAD_REBOUND_CONFIRMED`, `PLAN_GAP_NEXT_WEEK`, `INSUFFICIENT_LOOKBACK`).

**Output Structure:** See `phase_detection` in Field Definitions below.

---

### Zone Distribution & Polarisation Metrics

To ensure accurate intensity structure tracking across power and heart-rate data, the protocol aligns with **URF v5.1's Zone Distribution and Polarization Model**.

This system applies Seiler's 3-zone endurance framework (Z1 = < LT1, Z2 = LT1–LT2, Z3 = > LT2) to all recorded sessions and computes both power- and HR-based polarization indices. Zone boundaries and LT1/LT2 proxies MUST be derived from the sport-matched threshold entry (`thresholds.sports[family]`). Cycling sessions use cycling LTHR/FTP; running sessions use running LTHR/threshold pace. Cross-sport threshold application is not permitted.

|**Metric**                        | **Formula / Model**                     | **Source / Theory**                            | **Purpose / Interpretation**                                     |
| ---------------------------------| --------------------------------------- | ---------------------------------------------- | ---------------------------------------------------------------- |
| Polarization (Power-based)       | (Z1 + Z3) / (2 × Z2)                    | Seiler & Kjerland (2006); Seiler (2010, 2019)  | Balances easy vs. moderate vs. hard; higher = more polarized     |   				 
| Polarization Index (Normalized)  | (Z1 + Z2) / (Z1 + Z2 + Z3)              | Stöggl & Sperlich (2015)                       | Quantifies aerobic share; 0.7–0.8 = optimal aerobic distribution |   
| Polarization Fused (HR + Power)  | (Z1 + Z3) / (2 × Z2) across HR + Power  | Seiler (2019)                                  | Validates intensity pattern when combining HR and power sources  |  
| Polarization Combined (All-Sport)| (Z1 + Z2) / Total zone time (HR + Power)| Foster et al. (2001); Seiler & Tønnessen (2009)| Global endurance load structure; ≥ 0.8 = strongly polarized      |
| Training Monotony Index          | Mean Load / SD(Load)                    | Foster (1998)                             | Evaluates load variation; high values = risk of uniformity or overuse |

**Simple Polarisation Index** (used in `derived_metrics.polarisation_index`):
- Formula: `(Z1 + Z2) / Total zone time` — a 0–1 ratio of easy time
- Target: ≥0.80 for polarized training
- This is a quick sanity check for 80/20 compliance

**Seiler & Kjerland Interpretation** (theoretical reference — not used for TID classification):
- Polarization ratio > 1.0 → Polarized distribution
- Polarization ratio ≈ 0.7–0.9 → Pyramidal distribution
- Polarization ratio < 0.6 → Threshold-heavy distribution

For quantitative TID classification, the protocol uses the **Treff Polarization Index** described below.

By combining HR- and power-based zone data, the athlete's intensity structure remains accurately tracked across all disciplines, ensuring consistency between indoor and outdoor sessions.

---

#### Seiler TID Classification System

The data mirror provides a complete **Training Intensity Distribution (TID)** classification using the Treff et al. (2019) Polarization Index and a 5-class system based on Seiler's 3-zone model.

**Zone Mapping (7-Zone → Seiler 3-Zone):**

| 7-Zone Model | Seiler Zone | Classification | Notes                                                     |
|--------------|-------------|----------------|-----------------------------------------------------------|
| Z1–Z2        | Zone 1      | Easy           | Below LT1/VT1 (<2mM lactate)                              |
| Z3           | Zone 2      | Grey Zone      | Between LT1 and LT2 — minimize in polarized training      |
| Z4–Z7        | Zone 3      | Hard/Quality   | Above LT2/VT2 (>4mM lactate)                              |

**Treff Polarization Index (PI):**

```
PI = log10((Z1 / Z2) × Z3 × 100)
```

Where Z1, Z2, Z3 are fractional time in each Seiler zone (0–1).

**Computation Rules:**
- Only compute when Z1 > Z3 > Z2 and Z3 ≥ 0.01 (polarized structure required)
- If Z2 = 0 but structure is polarized: substitute Z2 = 0.01 (avoids division by zero)
- Otherwise: return null (PI is not meaningful for non-polarized distributions)

**5-Class TID Classifier** (explicit priority order, evaluated top-to-bottom):

| Priority | Classification   | Condition                                      |
|----------|------------------|-------------------------------------------------|
| 1        | Base             | Z3 < 0.01 and Z1 is largest zone               |
| 2        | Polarized        | Z1 > Z3 > Z2 and PI > 2.0                      |
| 3        | Pyramidal        | Z1 > Z2 > Z3                                   |
| 4        | Threshold        | Z2 is largest zone                              |
| 5        | High Intensity   | Z3 is largest zone                              |

If no condition matches (e.g., polarized structure but PI ≤ 2.0), classify as Pyramidal.

**Dual Calculation:** TID is computed twice — for all sports combined and for the primary sport only (like monotony). This catches cases where multi-sport training inflates easy time.

**Dual-Timeframe TID (7d vs 28d):**

The data mirror provides both 7-day (acute) and 28-day (chronic) Seiler TID classifications:
- `seiler_tid_7d` / `seiler_tid_7d_primary` — current week's distribution
- `seiler_tid_28d` / `seiler_tid_28d_primary` — 28-day chronic distribution

The `capability.tid_comparison` object compares these windows to detect distribution drift:

| Drift Category          | Condition                                        | Severity |
|-------------------------|--------------------------------------------------|----------|
| consistent              | 7d and 28d classification match                  | —        |
| shifting                | 7d and 28d classification differ                 | warning  |
| acute_depolarization    | 7d PI < 2.0 AND 28d PI ≥ 2.0                    | warning  |

`pi_delta` (7d PI minus 28d PI) quantifies the magnitude — positive means more polarized acutely.

**AI Response Logic:**
- `consistent` → No mention needed in reports
- `shifting` → Note in weekly report; investigate if sustained >2 weeks
- `acute_depolarization` → Flag in pre-workout and weekly reports; likely indicates fatigue shifting distribution toward grey zone
- TID drift is a **Tier 3 diagnostic** — it informs coaching context, not go/no-go decisions

---

### Behavioral & Analytical Rules for AI Coaches

#### 1. Deterministic Guidance (No Virtual Math)

All numeric references (FTP, HRV, RHR, TSS, CTL, ATL, HR zones) must use the athlete's provided or most recently logged values — no estimation, interpolation, or virtual math is permitted.

If the AI does not have a current value, it must request it from the user explicitly.

**Tolerances:**
- Power: ±1% for rounding (not inference)
- Heart Rate: ±1 bpm for rounding (not inference)
- HRV / RHR: No tolerance (use exact recent values)

**FTP Governance:**
- FTP references in this protocol use sport-family lookup: `thresholds.sports[family].ftp` for the relevant sport. Other sport families must not inherit cycling FTP.
- FTP is governed by modeled MLSS via Intervals.icu; passive updates reflect validated endurance trends (no discrete FTP testing required)
- FTP tests are optional — one or two per year may be performed for validation or benchmarking
- AI systems must not infer or overwrite FTP unless validated by modeled data or explicit athlete confirmation

**Benchmark Index (Longitudinal FTP Validation):**

To track FTP progression without requiring discrete tests, AI systems may compute:

```
Benchmark Index = (FTP_current ÷ FTP_prior) − 1
```

Where:
- `FTP_current` = Current modeled cycling FTP from Intervals.icu (`thresholds.sports.cycling.ftp`)
- `FTP_prior` = Cycling FTP value from 8–12 weeks prior (captures 1–1.5 training cycles)

**Interpretation:**
| **Benchmark Index** | **Status**  | **Recommended Action**                                      |
|---------------------|------------ |-------------------------------------------------------------|
| +2% to +5%          | Progressive | Continue current programming                                |
| 0% to +2%           | Maintenance | Acceptable if in recovery or maintenance phase              |
| −2% to 0%           | Plateau     | Review training stimulus and recovery                       |
| < −2%               | Regression  | Investigate recovery, illness, overtraining, or life stress |

**⚠️ Seasonal Context Adjustment:**

Benchmark Index interpretation must account for seasonal training phases. Expected FTP fluctuations vary across the annual cycle:

| **Season / Phase**           | **Expected Benchmark Index** | **Notes**                                           |
|------------------------------|------------------------------|-----------------------------------------------------|
| Off-season (post-goal event) | −5% to −2%                   | Expected regression during recovery; not concerning |
| Early Base (winter)          | −2% to +1%                   | Maintenance or slow rebuild; normal                 |
| Late Base / Build (spring)   | +2% to +5%                   | Progressive gains expected                          |
| Peak / Race Season (summer)  | +1% to +3%                   | Gains taper as fitness plateaus near peak           |
| Transition (autumn)          | −3% to 0%                    | Controlled detraining; expected                     |

**Interpretation Rules:**
- A −3% Benchmark Index in January (post off-season) is **normal** and should not trigger alarm
- A −3% Benchmark Index in July (mid-season) **warrants investigation**
- AI systems should cross-reference current phase (from Phase Detection Criteria) before flagging regression
- If Benchmark Index is negative but within seasonal expectations, note as "expected seasonal variance" rather than "regression"

**Governance Rules:**
- Benchmark Index should be evaluated no more frequently than every 4 weeks
- Negative trends persisting >8 weeks *outside expected seasonal context* warrant programme review
- AI must not use Benchmark Index to override athlete-confirmed FTP values

**Computational Consistency:**
- All computations must maintain deterministic consistency
- Variance across total or aggregated metrics must not exceed ±1% across datasets
- No smoothing, load interpolation, or virtual recomputation of totals is allowed — only event-based (workout-level) summations are valid
- Weekly roll-ups must reconcile with logged data totals within ±1% tolerance

---

### AI Self-Validation Checklist

Before providing recommendations, AI systems must verify:

| #  | **Check**                        | **Deterministic Rules/Requirement**.                                                                                                                   |
|----|----------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0  | **Data Source Fetch**            | Load JSON from data source FIRST (local files → GitHub connector → URL fetch). If all methods fail or data unavailable, STOP and request manual data input.                                              |
| 1  | FTP Source Verification          | Confirm FTP/LT2 is explicitly athlete-provided or from API/JSON mirror via sport-family lookup (`thresholds.sports[family]`). Do not infer, recalculate, or cross-apply thresholds across sport families. |
| 2  | Data Consistency Check           | Verify weekly training hours and load totals match the “READ_THIS_FIRST → quick_stats” dataset. Confirm totals within ±1% tolerance of logged data     |             
| 3  | No Virtual Math Policy           | Ensure all computed metrics originate from raw or mirrored data. No interpolation, smoothing, or estimation permitted.                                 |
| 4  | Tolerance Compliance             | Recommendations must remain within: ±3 W power, ±1 bpm HR, ±1% dataset variance.                                                                       |
| 5  | Missing-Data Handling            | If a metric is unavailable or outdated, explicitly request it from athlete. Never assume or project unseen values.                                     |
| 6  | Temporal Data Validation         | Verify "last_updated" timestamp is <24 hours old. If data is >48 hours, request a refresh. Flag if athlete context (illness, travel) contradicts data. |               
| 6b | UTC Time Synchronization         | Confirm dataset and system clocks align to UTC. Flag if offset >60 min or timestamps appear ahead of query time.                                       |
| 7  | Multi-Metric Conflict Resolution | If HRV/RHR ≠ Feel/RPE, prioritize athlete-provided readiness. Note discrepancy, request clarification. Never override illness/fatigue with “good” TSB. |
| 8  | Recommendation Auditability      | Cite specific data points used. Include reasoning chain. State confidence: "High" (all data) / "Medium" (1–2 gaps) / "Low" (>2 gaps).                  |
| 9  | Rolling Phase Alignment          | Identify current phase from TSB trend and ramp rate. Recommendations must align with phase logic. Flag contradictions.                                 |
| 10 | Protocol Version & Framework Citations | State Section 11 version. Cite frameworks when applying logic (e.g., "Per Seiler 80/20 model..."). Include framework version (e.g., “URF v5.1”)  |                                        

---


### Plan Adherence Monitoring

AI systems should track prescription compliance to validate coaching effectiveness:

**Consistency Index Calculation:**
```
Consistency Index = Sessions Completed ÷ Sessions Planned (rolling 7-day window)
```

**Compliance Thresholds:**
| **Consistency Index** | **Status**    | **AI Response**                                           |
|-----------------------|---------------|-----------------------------------------------------------|
| ≥0.9                  | Compliant     | Continue current prescription                             |
| 0.7–0.89              | Partial       | Flag missed sessions; assess barriers                     |
| <0.7                  | Non-compliant | Review prescription feasibility; adjust load or frequency |

**Validation Rules:**
- Planned sessions are defined by the athlete's calendar or AI-prescribed plan
- Rest days count as "completed" if no workout was prescribed
- Partial session completion (e.g., cut short) counts as 0.5 for calculation purposes
- AI must not penalise recovery adjustments made in response to readiness signals

---

### Intervals.icu Execution Tolerance (Indoor Variance Handling)

When comparing planned versus executed power targets, indoor workouts typically exhibit a consistent offset of approximately −2 to −3 W due to calibration variance, drivetrain loss, temperature, and real-time power averaging.

This minor deviation falls within deterministic tolerance and does not constitute underperformance.

AI systems must evaluate compliance within **±3 W or ±1%** of the prescribed target for each structured interval and total session.

**Example:** A target of 258 W resulting in 255–256 W average is considered fully compliant.

---

### Interval Contextualization Rule

AI systems must interpret interval power targets within their specific work segments — not as expectations for the entire session average.

Structured workouts (e.g., 4 × 10 min @ 258–261 W) include warm-up, recovery, and transition phases that naturally reduce overall session averages.
Performance evaluation must therefore be phase-aware and based on interval-level intent rather than total-session output.

**Compliance validation should include:**
- Comparing each interval's mean power to its prescribed target (±3 W or ±1%)
- Confirming session-level NP and TSS align with expected aggregate values
- Avoiding misclassification of sessions as "underperformed" solely due to lower total averages

---

### 2. Explicit Data Requests

Before querying the athlete manually, the AI should first verify whether the metric is already present or up-to-date in the API or JSON data mirror.

If unavailable, request:

| **Metric Needed** | **Ask For**                                                                 |
|-------------------|-----------------------------------------------------------------------------|
| FTP / LT2 Power   | "What's your current FTP or LT2 from Intervals.icu?"                        |
| HRV / RHR         | "What's your latest HRV and resting heart rate?"                            |
| CTL / ATL / Form  | "Can you share your current fitness, fatigue, and form from Intervals.icu?" |
| Sleep / Readiness | "How was your last night's sleep and morning readiness?"                    |
| Recent Workouts   | "Can you provide your last 7 days of training summaries or key sessions?"   |

AI should also prompt for *subjective recovery markers*: recent RPE, mood, sleep quality, fatigue, soreness, or stress level. 
Reference alongside objective metrics when evaluating readiness, recovery, or adaptations.

---

### 3. Context Integrity

All advice must respect current dossier targets and progression logic. No training adjustments should violate:
- Weekly volume tolerance
- Polarisation ratio (80/20 intensity)
- Planned block phasing

---

### 4. Temporal Awareness

If a conversation occurs outside planned training blocks (e.g., holidays, deloads, illness), AI must re-anchor guidance to current health and readiness first before referencing long-term progression targets.

---

### 5. Communication Style

AI systems must adopt a professional coach tone — concise, precise, and data-driven. Avoid speculation, filler, or motivational hype.

When uncertain, the AI must ask, not assume.

**Post-Workout Report Structure:**

Reports use a structured line-by-line format per session, not bullet-point summaries. Each report follows this flow:

1. **Data timestamp:** `Data (last_updated UTC: [timestamp])`
2. **One-line summary:** What was completed, key observation
3. **Session block(s)** (one per activity, line-by-line):
   - Activity type & name
   - Start time
   - Duration (actual vs planned)
   - Distance (cycling/running only)
   - Power: Avg / NP
   - Power zones (% breakdown)
   - Grey Zone (Z3): X%
   - Quality (Z4+): X%
   - HR: Avg / Max
   - HR zones (% breakdown)
   - Cadence (avg)
   - Decoupling (with assessment label)
   - Variability Index (with assessment label)
   - Calories (kcal)
   - Carbs used (g)
   - TSS (actual vs planned)
   Omit fields only if data unavailable for that activity type.
4. **Weekly totals block:** Polarization, Durability (7d/28d + trend), TID 28d (+ drift), TSB, CTL, ATL, Ramp rate, ACWR, Hours, TSS
5. **Overall:** Coach note (2–4 sentences — compliance, key quality observations, load context, recovery note if applicable)

See **Output Format Guidelines** for full field reference, assessment labels, and report templates.

**Do NOT:**
- Use single-paragraph responses for workout reviews
- Use bullet-point lists for session data (use structured line-by-line format)
- Ask follow-up questions when data is complete and metrics are good
- Omit weekly totals (polarization, durability, TID 28d, TSB, CTL, ATL, ACWR, hours, TSS)
- Cite "per Section 11" or "according to the protocol"

Elaborate only when thresholds are breached or athlete requests deeper analysis.

---

### 6. Recommendation Formatting

Present actionable guidance in concise, prioritized lists (3–5 items maximum).

Each recommendation must be specific, measurable, and data-linked:
- "Maintain ≥70% Z1–Z2 time this week."
- "If RI < 0.7 for 3 days, shift next 3 sessions to recovery emphasis."
- “FTP reassessments are not scheduled.”

Avoid narrative advice or motivational filler.

---

### 7. Data Audit and Validation

Before issuing any performance analysis or training adjustment, validate key data totals with the athlete.

If figures appear inconsistent or incomplete, request confirmation before proceeding.

When validating datasets, cross-check computed fatigue and load ratios against validated endurance ranges:
**Validated Endurance Ranges:**

| **Metric**                   | **Valid Range**                                    | **Flag (Early Warning)**           | **Alarm (Action Needed)**           | **Notes**                                                           |
|------------------------------|----------------------------------------------------|------------------------------------|-------------------------------------|---------------------------------------------------------------------|
| ACWR                         | 0.8–1.3                                            | At 0.8 / 1.3 (edges of optimal)   | At 0.75 / 1.35 (outside optimal)   | Persistence: >1.3 or <0.8 for 3+ days → alarm                     |
| Monotony                     | < 2.5                                              | At 2.3                             | At 2.5                              | See Monotony Deload Context below                                   |
| Strain                       | < 3500                                             | —                                  | > 3500                              | Cumulative stress                                                   |
| Recovery Index (RI)          | ≥ 0.8 good / 0.6–0.79 moderate / < 0.6 deload      | < 0.7 for > 1 day                 | < 0.7 for 3 days → deload review; < 0.6 → immediate deload | Readiness indicator                                |
| HRV                          | Within personal baseline                           | ↓ > 20% vs baseline               | Persists > 2 days                   | Use 7-day rolling baseline                                          |
| RHR                          | Within personal baseline                           | ↑ ≥ 5 bpm vs baseline             | Persists > 2 days                   | Use 7-day rolling baseline                                          |
| Fatigue Trend                | −0.2 to +0.2                                       | —                                  | —                                   | ΔATL − ΔCTL (stable range)                                          |
| Polarisation Ratio           | 0.75–0.9                                           | —                                  | —                                   | ~80/20 distribution                                                 |
| Durability Index (DI)        | ≥ 0.9                                              | —                                  | —                                   | Avg Power last hour ÷ first hour                                    |
| Readiness Decision         | Pre-computed go/modify/skip (P0–P3 ladder)         | —                                  | —                                   | See Readiness Decision section. sync.py v3.72+          |
| Load Ratio                   | < 3500                                             | —                                  | —                                   | Monotony × Mean Load — cumulative stress indicator                  |
| Stress Tolerance             | 3–6 sustainable / <3 low buffer / >6 high capacity | —                                  | —                                   | (Strain ÷ Monotony) ÷ 100 — load absorption capacity                |
| Load-Recovery Ratio          | <2.5 normal / ≥2.5 alert                           | —                                  | —                                   | 7-day Load ÷ RI — **secondary** overreach detector (see note below) |
| Grey Zone Percentage         | <5% normal / >8% elevated                          | —                                  | —                                   | Grey zone time as % of total — prevents tempo creep                 |
| Quality Intensity Percentage | See intensity distribution guidance                | —                                  | —                                   | Quality intensity (threshold+) as % of total                        |
| Hard Days per Week           | 2–3 typical / 1 (base/recovery) / 0 (deload)       | —                                  | —                                   | For high-volume athletes (10+ hrs/week)                             |
| Consistency Index            | ≥0.9 consistent / <0.8 non-compliant               | —                                  | —                                   | Sessions Completed ÷ Sessions Planned                               |
| Aggregate Durability (7d)    | <3% good / 3–5% moderate / >5% declining           | 7d mean > 28d mean by >2%         | 28d mean > 5% sustained             | Mean decoupling from steady-state sessions (VI ≤ 1.05, ≥ 90min)    |
| HRRc Trend                   | stable (within ±10% of 28d mean)                   | declining (7d >10% below 28d)     | —                                   | Largest 60s HR drop after threshold. Min 1/7d, 3/28d. Display only  |
| TID Drift                    | consistent (7d = 28d)                              | shifting (7d ≠ 28d classification) | acute_depolarization (7d PI <2, 28d PI ≥2) | Seiler TID comparison between 7d and 28d windows           |

**Monotony Deload Context:**  
Monotony may be mathematically elevated during and 2–3 days after a deload week due to uniform low-load sessions in the 7-day rolling window. This is a structural artifact, not an overuse signal. When trailing 7-day TSS is ≥20% below the 28-day weekly average, monotony alerts should include context indicating the elevation is expected and will normalize as the window rolls forward. AI systems must not prescribe load changes based on deload-context monotony alone.

**⚠️ Load-Recovery Ratio Hierarchy Note:**  
Load-Recovery Ratio is a **secondary** overreach detector. It should only be evaluated *after* Recovery Index (RI) has been validated as the primary readiness marker. The decision hierarchy is:

1. **Primary:** Recovery Index (RI) — physiological readiness
2. **Secondary:** Load-Recovery Ratio — load vs. recovery capacity
3. **Tertiary:** Subjective markers (Feel, RPE) — athlete-reported state

If RI indicates good readiness (≥0.8) but Load-Recovery Ratio is elevated (≥2.5), flag for monitoring but do not auto-trigger deload unless RI also declines.


If any values breach limits, shift guidance toward load modulation or recovery emphasis.

---

### Data Integrity Hierarchy (Trust Order)

If multiple data sources conflict:

1. **Intervals.icu API** → Primary source for power, HRV, CTL/ATL, readiness metrics
2. **Intervals.icu JSON Mirror** → Verified Tier-1 mirror source (local files, GitHub connector, or URL fetch — all carry the same trust level)
3. **Garmin Connect** → Backup for HR, sleep, RHR
4. **Athlete-provided data** → Valid if recent (<7 days) and stated explicitly
5. **Dossier Baselines** → Fallback reference

---

### 8. Readiness & Recovery Thresholds

Monitor and respond to:

| **Trigger**   | **Response**                      |
|---------------|-----------------------------------|
| HRV ↓ > 20%   | Easy day or deload consideration  |
| RHR ↑ ≥ 5 bpm | Flag potential fatigue or illness |
| Feel ≥ 4/5    | Adjust volume 30–40% for 3–4 days |

**Recovery Index Formula:**
```
RI = (HRV_today / HRV_baseline) ÷ (RHR_today / RHR_baseline)
```

**Interpretation:**
- RI ≥ 0.8 = Good readiness
- RI 0.6–0.79 = Moderate fatigue
- RI < 0.6 = Deload required

**RI Trend Monitoring:**
- 7-day mean should remain ≥ 0.8 for progression weeks
- If RI < 0.7 for > 1 day → flag for monitoring (early warning)
- If RI < 0.7 for > 3 consecutive days → trigger block-level deload or load-modulation review
- If RI < 0.6 → immediate deload required regardless of duration

AI systems must only consider caloric-reduction or weight-optimization phases during readiness-positive windows (DI ≥ 0.95, HR drift ≤ 3 %, RI ≥ 0.8), referencing Section 8 — Weight Adjustment Control.

---

### Readiness Decision (v11.13)

`sync.py` v3.72+ pre-computes a deterministic `readiness_decision` object using a priority ladder. AI coaches read this as the baseline go/modify/skip recommendation. The AI writes the coaching note and can override with explicit explanation, but the default decision is auditable and reproducible across LLMs.

**Priority Ladder (first match wins):**

| Priority | Condition | Result |
|----------|-----------|--------|
| **P0 — Safety stop** | RI < 0.6, OR any tier-1 alarm active | **Skip** (non-negotiable) |
| **P1 — Acute overload** | ACWR > 1.5, OR (TSB < -30 + HRV ↓>10%), OR (RI < 0.7 + tier-1 alert persisting ≥2 days) | **Skip** |
| **P1 — Acute overload (modify)** | ACWR > 1.3, OR (TSB < -25 + HRV ↓>10%) | **Modify** |
| **P2 — Accumulated fatigue** | Red signal count ≥ 2, OR (1 red in tightened phase), OR amber count ≥ phase threshold | **Modify** (or Skip if 2+ red) |
| **P3 — Green light** | None of the above | **Go** |

**Signal Classification:**

| Signal | Green | Amber | Red |
|--------|-------|-------|-----|
| HRV | Within ±10% of 7d baseline | ↓ 10–20% | ↓ >20% |
| RHR | At or below baseline | ↑ 3–4 bpm | ↑ ≥5 bpm |
| Sleep | ≥ 7h AND quality ≤ 2 | 5–7h OR quality 3 | < 5h OR quality 4 |
| TSB | > phase threshold (default -15) | Between threshold and -30 | < -30 |
| ACWR | 0.8–1.3 | <0.8 or 1.3–1.5 | > 1.5 |
| Feel | ≤ 3 (1=Strong, 5=Weak) | 4 | 5 |
| RI | ≥ 0.8 | 0.6–0.79 | < 0.6 |

Missing signals are classified as `unavailable` and excluded from amber/red counts.

**Phase Modifiers (shift P2 thresholds):**

| Phase | Amber threshold | TSB amber shift | Red tightened | Rationale |
|-------|----------------|-----------------|---------------|-----------|
| Build | 3 | -20 | No | Fatigue accumulation is the goal |
| Taper | 1 | -15 | Yes | Protecting race freshness |
| Race week | 1 | -15 | Yes | Race freshness paramount |
| Recovery / Deload | 2 (default) | -15 | No | Already resting — single amber is noise |
| Overreached | 2 (default) | -15 | No | Already compromised — default threshold sufficient |
| Base / Peak / null | 2 (default) | -15 | No | Standard operation |

**Structured Modification Output:**

When recommendation is `modify`, the output includes trigger categories and adjustment directions as data. The AI writes the coaching language.

| Trigger pattern | Intensity | Volume | Cap zone |
|----------------|-----------|---------|----------|
| Sleep-only | preserve | reduce | — |
| Autonomic (HRV/RHR/RI) | reduce | preserve | — |
| TSB-only | preserve | reduce | — |
| ACWR-driven | reduce | reduce | Z2 |
| Combined (2+) | reduce | reduce | — |
| Feel-only | reduce | preserve | — |

**Race week interaction:** Readiness can escalate (Go → Modify → Skip) during race week but cannot loosen race protocol targets. When `race_week_defers: true`, modification guidance defers to the race-week protocol's day-by-day targets. The race protocol sets the ceiling; readiness can only push it down.

**JSON output location:** Top-level `readiness_decision` object in `latest.json`, alongside `alerts` and `derived_metrics`.

---

### TSB Interpretation

**General Guidance:**
- TSB −10 to −30: **Typically normal** — reflects training load exceeding recent baseline
- TSB < −30: Monitor closely; check for compounding fatigue signals
- TSB > +10: Extended recovery surplus; may indicate under-training or planned taper

**Negative TSB is expected when:**
- Training consistently (any phase)
- Returning from off-season, illness, or holiday
- Intentionally building load

**Recovery recommendations based on TSB alone are NOT warranted** unless accompanied by:
- HRV ↓ > 20%
- RHR ↑ ≥ 5 bpm
- Feel ≥ 4/5
- Performance decline

A negative TSB is the mechanism of adaptation, not a warning signal.

---

### Success & Progression Triggers

In addition to recovery-based deload conditions, AI systems must detect readiness for safe workload, intensity, or interval progression ("green-light" criteria).

#### Readiness Thresholds (All Must Be Met)

| **Metric**            | **Threshold**                           |
|-----------------------|-----------------------------------------|
| Durability Index (DI) | ≥ 0.97 for ≥ 3 long rides (≥ 2 h)       |
| HR Drift              | < 3% during aerobic durability sessions |
| Recovery Index (RI)   | ≥ 0.85 (7-day rolling mean)             |
| ACWR                  | Within 0.8–1.3                          |
| Monotony              | < 2.5                                   |
| Feel                  | ≤ 3/5 (no systemic fatigue)             |

---

### Event-Specific Volume Tracking (Peak Phase Only)

During peak and pre-competition phases, AI systems should validate event-specific volume allocation using the Specificity Volume Ratio:

**Specificity Volume Ratio Calculation:**
```
Specificity Volume Ratio = Race-specific Training Hours ÷ Total Training Hours (rolling 14–21 days)
```

**Race-Specific Definition by Event Type:**

The definition of "race-specific" training varies by event type. AI systems should reference **Section 3 (Training Schedule & Framework)** for athlete-specific event definitions, or apply the following defaults:

| **Event Type**           | **Race-Specific Definition**                             | **Duration Tolerance**    | **Rationale**                                                           |
|--------------------------|----------------------------------------------------------|---------------------------|-------------------------------------------------------------------------|
| Gran Fondo / Randonneur  | Sessions matching target event duration and pacing       | ±15%                      | Duration-critical; pacing and fueling are primary limiters              |
| Road Race (mass start)   | Sessions with race-specific power variability and surges | ±20%                      | Tactical demands vary; power profile more important than exact duration |
| Time Trial               | Sessions at target TT intensity and duration             | ±10%                      | Highly duration- and intensity-specific                                 |
| Criterium / Track        | High-intensity intervals matching race power demands     | N/A (power-profile based) | Duration less relevant; power repeatability is key                      |
| Ultra-Endurance (200km+) | Long rides ≥70% of event duration at target pacing       | ±10%                      | Duration, pacing, and fueling are critical                              |
| Hill Climb               | Efforts matching target climb duration and gradient      | ±15%                      | Power-to-weight at specific duration                                    |

**Volume Allocation Targets:**
| **Phase** | **Specificity Volume Ratio** | **Specificity Score (existing)** |
|-----------|------------------------------|----------------------------------|
| Base      | 0.2–0.4                      | N/A (general fitness focus)      |
| Build     | 0.4–0.6                      | ≥0.70                            |
| Peak      | 0.7–0.9                      | ≥0.85                            |

**AI Response Logic:**
- If Specificity Volume Ratio <0.5 within 3 weeks of goal event → Flag insufficient event-specific volume
- If Specificity Score ≥0.85 but Specificity Volume Ratio <0.6 → Quality good but volume insufficient; increase race-specific session frequency
- If Specificity Volume Ratio >0.9 for >2 weeks → Risk of monotony; validate variety while maintaining specificity

**Note:** For events not listed above, AI should prompt athlete to define race-specific criteria or reference Section 3 event profile.

---

### Progression Pathways

Apply One at a Time — Some phases may run concurrently with readiness validation.

**Concurrency Rules:**
- *Progression Pathways 1 and 2* may progress simultaneously if recovery stability is confirmed (RI ≥ 0.8, HRV within 10 %, no negative fatigue trend).  
- *Progression Pathways 2 and 3* may overlap when readiness is high (RI ≥ 0.85, HRV stable, no recent load spikes).  
- *Progression Pathways 1 and 3* must not overlap — avoid combining long-endurance load with metabolic or environmental stressors.  
- Only one progression variable per category may be modified per week.

#### *1 Endurance Progression (Z1–Z2 Durability Work)

**Phase A — Duration Extension:**
- Extend long endurance rides by 5–10% until target duration achieved
- Maintain HR drift < 5% and RI ≥ 0.8 during extension

**Phase B — Power Transition (Duration Reached):**
- Once target duration sustained with DI ≥ 0.97, maintain duration but increase aerobic/tempo targets by +2–3% (≤ 5 W typical)
- Confirm HR drift < 5% and RI ≥ 0.8 for two consecutive sessions before further increase

#### *2 Structured Interval Progression (VO₂max / Sweet Spot Days)

**Readiness Check (All Required):**
- RI ≥ 0.8 and stable (no downward trend >3 days)
- HRV within 10% of baseline
- Prior interval compliance ≥ 95% (actual NP vs. target NP ±3 W)

**VO₂max Sessions:**
- Prioritize power progression, not duration
- Increase target power by +2–3% (≤ +5 W) once full set compliance maintained with consistent recovery (HR rise between reps < 10 bpm)
- Extend total sets only when power targets sustainable and RI ≥ 0.85 for ≥ 3 consecutive workouts
- Cap total weekly VO₂max time at ≤ 45 min

**Sweet Spot Sessions:**
- Progress by increasing target power +2–3% after two consecutive weeks of stable HR recovery (< 10 bpm drift between intervals)
- Maintain total session time unless HR drift or RPE indicates clear under-load

#### *3 Metabolic & Environmental Progression (Optional Advanced Phase)

Once duration and interval stability confirmed, controlled metabolic or thermoregulatory stressors may be introduced:
- Higher carbohydrate intake (CHO/h) for fueling efficiency validation
- Heat exposure or altitude simulation for environmental resilience
- Fasted-state Z2 validation for enhanced metabolic flexibility

**Rules:**
- Only one progression variable may be modified per week
- Exposures must not exceed one per 7–10 days
- Additional exposures require RI ≥ 0.85 and HRV within 10% of baseline

---

### Regression Rule (Safety Check)

This rule applies exclusively to structured interval sessions (Sweet Spot, Threshold, VO₂max, Anaerobic, Neuromuscular work) — not to general endurance, recovery, or metabolic progression blocks.

It governs acute, session-level performance safety, ensuring localized overreach is corrected before systemic fatigue develops.

**Triggers:**
- Intra-session HR recovery worsens by >15 bpm between intervals
- RPE rises ≥2 points at constant power

**Response:**
- Classify as acute overreach.  
- For minor deviations (isolated fatigue signals or transient HR drift), insert **1–2 days of Z1-only training** to restore autonomic stability.  
- If fatigue persists after 2 days (HR recovery >15 bpm or RPE +2), revert next interval session to prior week’s load or reduce volume 30–40% for 3–4 days.
- Maintain normal Z2 endurance unless global readiness metrics also indicate systemic fatigue (RI < 0.7 for >3 days, HRV ↓ > 20%)

---

### Recovery Metrics Integration (HRV / RHR / Sleep / Feel)

**Purpose:** Provide a deterministic readiness validation layer linking daily recovery data to training adaptation.

**Key Variables:**
- HRV (ms): 7-day rolling baseline comparison
- RHR (bpm): 7-day rolling baseline comparison
- Sleep Quality (1–4): Subjective quality rating (inverted scale: 1=Great, 4=Poor) — manual entry or auto-derived from device sleep score
- Feel (1–5): Manual subjective entry (1=Strong, 2=Good, 3=Normal, 4=Poor, 5=Weak)

**Decision Logic:**
- HRV ↓ > 20% vs baseline → Active recovery / easy spin
- RHR ↑ ≥ 5 bpm vs baseline → Fatigue / illness flag
- Sleep Quality = 4 → Reduce next-session intensity by 1 zone
- Feel ≥ 4 → Treat as low readiness; monitor for compounding fatigue  
- Feel ≥ 4 + 1 trigger (HRV, RHR, or Sleep deviation) → Insert 1–2 days of Z1-only training
- 1 trigger persisting ≥2 days → Insert 1–2 days of Z1-only training
- ≥ 2 triggers → Auto-deload (−30–40% volume × 3–4 days)

**Integration:**
Daily metrics synchronised through data hierarchy and mirrored in JSON dataset each morning. AI-coach systems must reference latest values before prescribing or validating any session.

If HRV unavailable, "Feel" substitutes as primary readiness indicator.

---

### Audit and Determinism Notes

- Each progression must include an explicit “trigger met” reference in AI or coaching logs (e.g., RI ≥ 0.85, DI ≥ 0.97) to preserve deterministic audit traceability.
- Power increases should not exceed +3 % per week (≤ +5 W typical); duration extensions may reach 5–10 % when within readiness thresholds  
- Progression logic must remain within validated fatigue safety ranges (ACWR ≤ 1.3, Monotony < 2.5)  
- When any progression variable changes, 7-day RI and TSB must remain within recovery-safe bands before further load increases  

---

### 9. Optional Performance Quality Metrics

When sufficient raw data is available, the AI may compute **secondary endurance quality markers** to evaluate training efficiency, durability, and fatigue resistance.  
These calculations must only occur with **explicit athlete-provided inputs** — not inferred or modeled values.  
Before interpretation, the AI must clearly state each metric’s **purpose**, **formula**, and **validation range**.

If metrics such as **ACWR**, **Strain**, **Monotony**, **FIR**, or **Polarization Ratio** exceed validated thresholds, the AI must flag potential overreaching or under-recovery **before** prescribing further load increases.  
Any training modification requires reconfirming **HRV**, **RHR**, and **subjective recovery status**.

---

#### Validated Optional Metrics

| **Metric**                | **Formula / Method**                                                    | **Target Range**   | **Purpose / Interpretation**                                     |
|---------------------------|-------------------------------------------------------------------------|--------------------|------------------------------------------------------------------|
| HR–Power Decoupling (%)   | [(HR₂nd_half / Power₂nd_half) / (HR₁st_half / Power₁st_half) − 1] × 100 | < 5 %              | Aerobic efficiency metric; <5 % drift = stable HR–power coupling |
| Efficiency Factor (EF)    | NP ÷ Avg HR (Coggan)                                                    | Individual / fitness-dependent | Aerobic efficiency trend; rising EF at same intensity = improving fitness. Compare like-for-like sessions only |
| Durability Index (DI)     | `Avg Power last hour ÷ Avg Power first hour`                            | ≥ 0.95             | Quantifies fatigue resistance during endurance sessions          |
| Fatigue Index Ratio (FIR) | `Best 20 min Power ÷ Best 60 min Power`                                 | 1.10 – 1.15        | Indicates sustainable power profile and fatigue decay            |
| FatOx Trend *(Optional)*  | Derived from HR–Power and substrate data                                | Stable or positive | Tracks metabolic efficiency and substrate adaptation             |
| Specificity Score         | Weighted match to goal event power/duration profile                     | ≥ 0.85             | Validates race-specific readiness (optional metric)              |

---

#### Load Management Metrics

| **Metric**          | **Formula / Method**                    | **Target Range** | **Purpose / Interpretation**                             |
|---------------------|-----------------------------------------|------------------|----------------------------------------------------------|
| Stress Tolerance    | `(Strain ÷ Monotony) ÷ 100`             | 3–6              | Quantifies capacity to absorb additional training load   |
| Load-Recovery Ratio | `7-day Load ÷ Recovery Index`           | <2.5             | **Secondary** overreach detector; complements RI and FIR |
| Consistency Index   | `Sessions Completed ÷ Sessions Planned` | ≥0.9             | Validates plan adherence and prescription compliance     |

**Interpretation Logic:**
- Stress Tolerance <3 → Limited buffer for load increases; prioritize recovery
- Stress Tolerance >6 → High absorption capacity; may tolerate progressive overload
- Load-Recovery Ratio ≥2.5 → Load outpacing recovery capacity; reduce volume or intensity

**⚠️ Metric Hierarchy:**  
These metrics are **secondary** to the primary readiness markers defined in Section 8 (Readiness & Recovery Thresholds). AI systems must evaluate in this order:

1. **Primary readiness:** RI, HRV, RHR, Feel
2. **Secondary load metrics:** Stress Tolerance, Load-Recovery Ratio, Consistency Index
3. **Tertiary diagnostics:** Zone Distribution Metrics, Durability Sub-Metrics, Capability Metrics (Aggregate Durability, TID Drift)

Do not override primary readiness signals with secondary load metrics.

---

#### Zone Distribution Metrics (Seiler's Polarized Model)

In addition to the polarisation ratios defined above in Zone Distribution & Polarisation Metrics, the following diagnostic metrics provide granular intensity distribution analysis aligned with Seiler's research.

**Critical Context:** Seiler's research shows that intensity distribution appears different depending on measurement method:
- **By session count:** ~80% easy sessions, ~20% hard sessions (polarized appearance)
- **By time in zone:** ~90%+ easy time, <10% hard time (pyramidal appearance)

Both measurements are valid but serve different purposes. For **high-volume athletes** (10+ hours/week), **session count or hard days per week** is often more practical than time-in-zone percentage.

| **Metric**                       | **Formula / Method**                    | **Purpose**                                               |
|----------------------------------|-----------------------------------------|-----------------------------------------------------------|
| **Grey Zone Percentage**         | `Z3 Time ÷ Total Time × 100`            | Grey zone (tempo) monitoring — **minimize this**          |
| **Quality Intensity Percentage** | `(Z4+Z5+Z6+Z7) Time ÷ Total Time × 100` | Quality intensity — hard work above threshold             |
| **Polarisation Index**           | `(Z1+Z2) Time ÷ Total Time`             | Easy time ratio — validates 80/20 distribution by time    |
| **Hard Days per Week**           | Count of days with Z4+ work             | Session-based intensity tracking for high-volume athletes |

**Zone Classification (7-Zone to Seiler 3-Zone Mapping):**

| 7-Zone Model | Seiler Zone | Classification | Notes                                                     |
|--------------|-------------|----------------|-----------------------------------------------------------|
| Z1–Z2        | Zone 1      | Easy           | Below LT1/VT1 (<2mM lactate)                              |
| Z3           | Zone 2      | Grey Zone      | Between LT1 and LT2 — "too much pain for too little gain" |
| Z4–Z7        | Zone 3      | Hard/Quality   | Above LT2/VT2 (>4mM lactate)                              |

**Intensity Distribution Targets:**

For athletes training **<10 hours/week** (time-based targets more practical):

| **Phase** | **Grey Zone % Target** | **Quality Intensity % Target** | **Polarisation Index** |
|-----------|------------------------|--------------------------------|------------------------|
| Base      | <5%                    | 10–15%                         | ≥0.85                  |
| Build     | <8%                    | 15–20%                         | ≥0.80                  |
| Peak      | <10%                   | 20–25%                         | ≥0.75                  |
| Recovery  | <3%                    | <5%                            | ≥0.95                  |

For athletes training **≥10 hours/week** (session-based targets more practical):

| **Phase** | **Grey Zone % Target** | **Hard Days/Week** | **Easy Days/Week** | **Rest Days** |
|-----------|------------------------|--------------------|--------------------|---------------|
| Base      | <5%                    | 1                  | 5–6                | 1             |
| Build     | <8%                    | 2                  | 4                  | 1             |
| Peak      | <10%                   | 2–3                | 3–4                | 1             |
| Recovery  | <3%                    | 0                  | 3–4                | 2–3           |

**Why Session Count Matters for High-Volume Athletes:**

When training 15+ hours per week, a 2-hour interval session might only contribute 5–7% of total weekly time in Z4+, despite being a full "hard day." By time-in-zone metrics, this looks insufficient. By session count, 2 hard days out of 6–7 training days (~30%) is appropriate for a build phase.

**Reference:** Seiler's research on elite cross-country skiers showed 77% of training sessions were easy and 23% were hard, while by time 91% was in zones 1–2 and only 9% in zones 3–5.

**AI Response Logic:**
- Grey Zone Percentage >8% for ≥2 consecutive weeks → Flag tempo creep; recommend restructuring
- Quality Intensity Percentage <10% AND Hard Days <2/week during build phase → Flag insufficient intensity stimulus
- Hard Days >3/week for ≥2 consecutive weeks → Flag overintensity risk; check RI and ACWR

**Example Valid Training Week (Build Phase, 15 hours total):**
- Monday: Rest + cross-training (walk, ski erg)
- Tuesday: Z2 endurance (2.5 hours)
- Wednesday: **Hard day** — VO2max intervals (1.5 hours, includes Z4+ work)
- Thursday: Z1–Z2 recovery/endurance (2 hours)
- Friday: Z2 endurance (2.5 hours)
- Saturday: **Hard day** — Threshold intervals (2 hours, includes Z4+ work)
- Sunday: Z2 long ride (4.5 hours)

This yields: ~3% Quality Intensity % by time, but 2 hard days (29% of training days) — both are correct measurements.

---

#### Grey Zone Percentage — Grey Zone Monitoring

To prevent unintended accumulation of tempo/threshold-adjacent intensity during base or recovery phases, monitor:

```
Grey Zone Percentage = Z3 Time ÷ Total Training Time × 100
```

**Phase-Appropriate Targets:**
| **Phase** | **Grey Zone % Target** | **Alert Threshold** |
|-----------|------------------------|---------------------|
| Base      | <5%                    | >8%                 |
| Build     | <8%                    | >12%                |
| Peak      | <10%                   | >15%                |
| Recovery  | <3%                    | >5%                 |

**AI Response Logic:**
- Grey Zone Percentage exceeding alert threshold for ≥2 consecutive weeks → Flag tempo creep
- During base phase, elevated Grey Zone % often indicates insufficient Z1 volume or unstructured "junk miles"
- AI must recommend session restructuring to restore polarisation balance

**Why Z3 is the "Grey Zone":**

Per Seiler's research, training between the aerobic and anaerobic thresholds (tempo/sweetspot) generates:
- More fatigue than Z1–Z2 work
- Less adaptation stimulus than Z4+ work
- "Too much pain for too little gain"

Elite athletes consistently minimize Z3 exposure, favouring clear polarisation between easy (Z1–Z2) and hard (Z4+) sessions.

---

#### Periodisation & Progression Metrics

| **Metric**               | **Formula / Method**                | **Target Range** | **Purpose / Interpretation**                                                           |
|--------------------------|-------------------------------------|------------------|----------------------------------------------------------------------------------------|
| Specificity Volume Ratio | `Race-specific Hours ÷ Total Hours` | 0.7–0.9 (peak)   | Complements Specificity Score by tracking volume allocation toward event-specific work |
| Benchmark Index          | `(FTP_current ÷ FTP_prior) − 1`     | +2–5%            | Tracks longitudinal FTP progression without requiring formal tests                     |

**Interpretation Logic:**
- Specificity Volume Ratio <0.5 during peak phase → Insufficient race-specific volume (cross-check with Specificity Score for quality alignment)
- Benchmark Index negative over 8+ weeks → Investigate recovery, nutrition, or programming

**Note:** Specificity Volume Ratio measures *how much* training time is event-specific, while the existing Specificity Score measures *how well* sessions match target event demands. Both should trend upward during peak phases.

---

#### Durability Sub-Metrics

When Durability Index (DI) drops below 0.95, the following diagnostic metrics help identify the specific durability limitation:

| **Metric**      | **Formula / Method**                                           | **Target Range** | **Purpose / Interpretation**                     |
|-----------------|----------------------------------------------------------------|------------------|--------------------------------------------------|
| Endurance Decay | `(Avg Power Hour 1 − Avg Power Final Hour) ÷ Avg Power Hour 1` | <0.05            | Quantifies power degradation over long sessions  |
| Z2 Stability    | `SD(Z2 Power) ÷ Mean(Z2 Power)` across sessions                | <0.04            | Measures consistency of aerobic pacing execution |

**Diagnostic Logic:**
- High Endurance Decay + Normal HR–Power Decoupling → Muscular fatigue; consider fueling or pacing strategy
- Normal Endurance Decay + High HR–Power Decoupling → Cardiovascular drift; assess hydration, heat, or aerobic base fitness
- High Z2 Stability variance → Inconsistent pacing execution; review session targeting

**Note:** HR–Power Decoupling (existing metric) serves as the cardiac drift diagnostic. Do not duplicate with separate "Aerobic Decay" metric.

#### Aggregate Durability (Capability Metric)

The per-session Durability Sub-Metrics above diagnose *individual session* limitations. The **Aggregate Durability** metric provides a *trend-level* view of aerobic efficiency across multiple sessions, using HR–Power decoupling as the signal.

**Data Source:** The `capability.durability` object in the data mirror provides rolling 7-day and 28-day aggregate decoupling from qualifying steady-state sessions.

**Session Filter (all must be true):**
- HR–Power decoupling value exists (not null)
- Variability Index (VI) exists, > 0, and ≤ 1.05 (steady-state power only)
- Moving time ≥ 5400 seconds (90 minutes)

**Rationale:** Per Maunder et al. (2021) and Rothschild & Maunder (2025), meaningful cardiac drift requires prolonged exercise. The 90-minute floor is the practical field threshold where drift becomes detectable. The VI ≤ 1.05 filter excludes interval sessions where decoupling reflects recovery dynamics, not aerobic drift. Negative decoupling values are included — they indicate HR drifted down relative to power (strong durability or cooling conditions).

**Aggregate Metrics:**

| **Metric**               | **Description**                                           | **Minimum Data** |
|--------------------------|-----------------------------------------------------------|-------------------|
| mean_decoupling_7d       | Mean decoupling from qualifying sessions in last 7 days   | ≥ 2 sessions      |
| mean_decoupling_28d      | Mean decoupling from qualifying sessions in last 28 days  | ≥ 2 sessions      |
| high_drift_count_7d/28d  | Count of qualifying sessions with decoupling > 5%         | —                 |
| trend                    | 7d vs 28d comparison: improving / stable / declining      | Both windows      |

**Trend Logic:**
- `improving`: 7d mean < 28d mean by > 1 percentage point
- `stable`: 7d and 28d means within ±1 percentage point
- `declining`: 7d mean > 28d mean by > 1 percentage point

Trend direction matters more than absolute values — an athlete's baseline decoupling varies with fitness, conditions, and terrain.

**Alert Thresholds:**

| Condition                          | Severity | Action                                            |
|------------------------------------|----------|---------------------------------------------------|
| 28d mean > 5% (sustained)         | alarm    | Aerobic efficiency concern — review volume/recovery |
| 7d mean > 28d mean by > 2%        | warning  | Durability declining — check fatigue and recovery   |
| ≥ 3 sessions with > 5% in 7d      | warning  | Repeated poor durability — investigate root cause   |

**Relationship to Existing Metrics:**

| Metric                   | Relationship                                                                                    |
|--------------------------|-------------------------------------------------------------------------------------------------|
| Durability Index (DI)    | **Complementary.** DI measures power output sustainability. Aggregate Durability measures cardiac efficiency trend. |
| HR–Power Decoupling      | **Aggregates.** Per-session decoupling is the raw input; aggregate durability provides the trend view.              |
| Endurance Decay          | **Different signal.** Endurance Decay = muscular. Aggregate Durability = cardiovascular drift.                     |

---

#### HRRc — Heart Rate Recovery (Capability Metric)

HRRc measures how quickly heart rate recovers after a hard effort — a marker of parasympathetic reactivation quality. Intervals.icu computes HRRc as the largest 60-second HR drop (in bpm) starting from a HR above the athlete's configured threshold, after exceeding that threshold for at least 1 minute. The API field is `icu_hrr`.

**Data Source:** The `capability.hrrc` object in the data mirror provides rolling 7-day and 28-day aggregate HRRc from qualifying sessions.

**Qualifying Sessions:**
- `icu_hrr` is not null and > 0 (self-selects: only fires when threshold HR held >1min and cooldown recorded)
- No duration, VI, or sport-type filter — HRRc self-selects by its own triggering criteria

**Window Minimums:**

| Field               | Description                                                | Min Sessions |
|---------------------|------------------------------------------------------------|--------------|
| mean_hrrc_7d        | Mean HRRc (bpm) from qualifying sessions in last 7 days   | ≥ 1 session  |
| mean_hrrc_28d       | Mean HRRc (bpm) from qualifying sessions in last 28 days  | ≥ 3 sessions |
| trend               | 7d vs 28d comparison: improving / stable / declining       | Both windows |

**Trend Logic:**
- `improving`: 7d mean > 28d mean by > 10%
- `stable`: 7d and 28d means within ±10%
- `declining`: 7d mean < 28d mean by > 10%

The 10% threshold is conservative for a field metric. Lab reliability of HRR60s is high (CV 3–14%, ICC up to 0.99 per Fecchio et al. 2019 systematic review), but field variability is substantially higher due to variable workout type, intensity, recording duration, and recovery posture. The asymmetric window minimums (1 session/7d, 3 sessions/28d) reflect the reality that most athletes generate 1–2 HRRc readings per week — the 28d baseline is where noise dampening matters.

Higher HRRc = faster recovery = better parasympathetic rebound. Trend direction matters more than absolute values — an athlete's baseline HRRc varies with fitness, age, exercise modality, and conditions. Compare like-for-like where possible.

**Scope:** Display only. HRRc is not wired into readiness_decision signals. It complements the existing autonomic/wellness signal chain (resting HRV, resting HR, subjective markers) as an exercise-context recovery quality marker.

**References:**
- Fecchio et al. (2019): Systematic review of HRR reproducibility. HRR60s exhibits high reliability across protocols.
- Lamberts et al. (2024): HRR60s in trained-to-elite cyclists — ICC = 0.97, TEM = 4.3%.
- Buchheit (2006): HRR associated with training loads, not VO2max.
- Tinker (2019): Intervals.icu renamed HRR to HRRc to distinguish from Heart Rate Reserve.

---

#### W′ Balance Metrics *(When Interval Data Available)*

If workout files include W′ balance data (from Intervals.icu or WKO), the following metrics provide anaerobic capacity insights:

| **Metric**             | **Definition**                                        | **Interpretation**                               |
|------------------------|-------------------------------------------------------|--------------------------------------------------|
| Mean W′ Depletion      | Average % of W′ reserve expended per interval session | Higher values indicate greater anaerobic demand  |
| W′ Recovery Rate       | Time to recover 50% of W′ between intervals           | Slower recovery may indicate accumulated fatigue |
| Anaerobic Contribution | % of session TSS derived from W′ expenditure          | Validates interval prescription alignment        |

**Data Source & Requirements:**
- Intervals.icu automatically calculates CP (Critical Power) and W′ from your power curve data
- **However**, accurate modeling requires sufficient maximal efforts across multiple durations (typically 3–20 minutes) within the past 90 days
- If power curve data is sparse or lacks recent maximal efforts, CP/W′ estimates may be unreliable
- AI systems should verify `power_curve_quality` or equivalent confidence indicator before applying W′ metrics
- If CP/W′ data is unavailable or low-confidence, skip W′ metrics and rely on standard TSS-based load analysis

**Usage Notes:**
- These metrics are most relevant for VO₂max, threshold, and anaerobic interval sessions
- Do not apply to Z1–Z2 endurance sessions
- W′ metrics are **Tier 3 (tertiary)** — use for diagnostics, not primary load decisions

---

#### Metric Evaluation Hierarchy

To ensure AI systems evaluate metrics in the correct order:

```
┌─────────────────────────────────────────────────────────────┐
│  TIER 1: PRIMARY READINESS (Evaluate First)                 │
│  ─────────────────────────────────────────                  │
│  • Recovery Index (RI)                                      │
│  • HRV (vs baseline)                                        │
│  • RHR (vs baseline)                                        │
│  • Feel / RPE (subjective)                                  │
│                                                             │
│  → These determine GO / NO-GO for training                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  TIER 2: SECONDARY LOAD METRICS (Evaluate Second)           │
│  ─────────────────────────────────────────────              │
│  • Stress Tolerance                                         │
│  • Load-Recovery Ratio                                      │
│  • Consistency Index                                        │
│  • ACWR, Monotony, Strain                                   │
│                                                             │
│  → These refine load prescription within readiness limits   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  TIER 3: TERTIARY DIAGNOSTICS (Evaluate When Flagged)       │
│  ─────────────────────────────────────────────              │
│  • Grey Zone Percentage (grey zone monitoring)              │
│  • Quality Intensity Percentage / Hard Days                 │
│  • Polarisation Index                                       │
│  • Durability Sub-Metrics (Endurance Decay, Z2 Stability)   │
│  • Specificity Volume Ratio                                 │
│  • Benchmark Index (with seasonal context)                  │
│  • W′ Balance Metrics (when available and high-confidence)  │
│                                                             │
│  → These diagnose specific issues when primary/secondary    │
│    metrics indicate a problem                               │
└─────────────────────────────────────────────────────────────┘
```

**Critical Rule:** Secondary metrics (Tier 2) must never override primary readiness signals (Tier 1). If RI ≥ 0.8 but Load-Recovery Ratio ≥ 2.5, flag for monitoring but do not auto-trigger deload.

---

#### Relationship to Existing Metrics

| New Metric                   | Existing Metric           | Relationship                                                                                                                         |
|------------------------------|---------------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| Load-Recovery Ratio          | Recovery Index (RI)       | **Hierarchical.** RI is primary readiness. Load-Recovery Ratio is secondary load-vs-recovery check.                                  |
| Load-Recovery Ratio          | Fatigue Index Ratio (FIR) | **Different purpose.** FIR measures power sustainability (20min vs 60min). Load-Recovery Ratio measures load vs recovery capacity.   |
| Specificity Volume Ratio     | Specificity Score         | **Complementary.** Volume Ratio tracks *how much* time is event-specific. Score tracks *how well* sessions match event demands.      |
| Endurance Decay              | Durability Index (DI)     | **Diagnostic breakdown.** DI is the primary metric. Endurance Decay provides detail when DI <0.95.                                   |
| Grey Zone Percentage         | Polarisation Index        | **Complementary.** Polarisation Index validates 80/20 by easy time. Grey Zone Percentage specifically flags grey zone creep.         |
| Quality Intensity Percentage | Polarisation Index        | **Complementary.** Quality Intensity Percentage tracks quality intensity. For high-volume athletes, Hard Days per Week is preferred. |
| Stress Tolerance             | Strain                    | **Derived from.** Stress Tolerance = (Strain ÷ Monotony) ÷ 100, providing absorption capacity context.                               |
| Aggregate Durability         | HR–Power Decoupling       | **Aggregates.** Per-session decoupling is the raw input; aggregate durability provides the 7d/28d trend view.                        |
| Aggregate Durability         | Durability Index (DI)     | **Complementary.** DI = power output sustainability. Aggregate Durability = cardiovascular efficiency trend across sessions.          |
| Seiler TID (Treff PI)        | Polarisation Index        | **Different scale.** Simple Polarisation Index = 0–1 easy-time ratio. Treff PI = logarithmic scale with 5-class classification.      |
| TID Drift                    | Seiler TID                | **Temporal comparison.** TID Drift compares 7d vs 28d Seiler TID to detect distribution shifts over time.                            |

---

### Update & Version Guidance

The dossier (DOSSIER.md) and SECTION_11.md is the **single source of truth** for all thresholds, metrics, and structural logic.  
AI systems must **never overwrite base data** — all updates require **explicit athlete confirmation**.  

When new inputs are provided (e.g., FTP test, updated HRV, weight), the AI must assist with **structured version-control** (e.g., `v0.7.5 → v0.7.6`).

---

### Feedback Loop Architecture *(RPS-Style)*

- **Weekly loop** → Review CTL, ATL, TSB, DI, HRV, RHR, aggregate durability trend, TID drift; adjust load accordingly.  
- **Feed-forward** → AI or athlete modifies next week’s volume/intensity based on readiness.  
- **Block loop (3–4 weeks)** → Evaluate durability trend (by-week trajectory), TID at block scale, readiness; determine phase transitions.

> Training progression must reflect **physiological adaptation**, not fixed calendar timing.

---

### AI Interaction Template

If uncertain about data integrity, the AI must default to the following confirmation sequence:

> “To ensure accurate recommendations, please confirm:  
> - Current FTP / LT2  
> - Latest HRV and RHR  
> - Current CTL, ATL, and Form (from Intervals.icu)  
> - Any illness, soreness, or recovery issues this week?”

All recommendations must reference **only verified data**.  
If new metrics are imported from external platforms (e.g., Whoop, Oura, HRV4Training), record the source and timestamp — but retain **Intervals.icu** as the Tier-0 data reference.

---

### Goal Alignment Reference

All AI recommendations must remain aligned with the athlete’s **long-term roadmap** (see *Section 3: Training Schedule & Framework*).  
The dossier’s performance-objective tables define the **authoritative phase structure** and **KPI trajectory** guiding progression and adaptation.

---

### Output Format Guidelines

AI systems should structure athlete reports consistently.  
See https://github.com/CrankAddict/section-11/tree/main/examples/reports for annotated templates and examples.

**Pre-Workout Reports must include:**
- Weather and coach note (if athlete location is available)
- Readiness assessment (HRV, RHR, Sleep vs baselines)
- Load context (TSB, ACWR, Load/Recovery, Monotony if > 2.3)
- Capability snapshot (Durability 7d mean + trend; TID drift if not consistent)
- Today's planned workout with duration and targets (or rest day + next session preview)
- Go/Modify/Skip recommendation with rationale

See `PRE_WORKOUT_TEMPLATE.md` in the examples directory for conditional fields and readiness decision logic.

**Post-Workout Reports must include:**
- One-line session summary
- Completed session metrics (power, HR, zones, decoupling, VI, TSS vs planned)
- Plan compliance assessment
- Weekly running totals (polarization, durability 7d/28d + trend, TID 28d + drift, CTL, ATL, TSB, ACWR, hours, TSS)
- Overall coach note (2-4 sentences: compliance, key quality observations, load context, recovery note)

See `POST_WORKOUT_TEMPLATE.md` in the examples directory for field reference and rounding conventions.

**Brevity Rule:** Brief when metrics are normal. Detailed when thresholds are breached or athlete asks "why."

**Alerts Array:** If an `alerts` array is present in the JSON data mirror, AI systems must evaluate all alerts and respond to any with severity `"warning"` or `"alarm"` before proceeding with standard analysis. Empty alerts array = green light, no mention needed.

**Confidence Scoring:** The data mirror may include `history_confidence` (longitudinal depth) and `data_confidence` (current data completeness) fields. AI systems should use these internally to calibrate recommendation certainty. Do not surface confidence to the athlete unless it materially limits the quality of advice (e.g., phase detection impossible without history).

---

### Race-Week Protocol

**Purpose:** Day-by-day decision framework for the final 7 days before a goal event (D-7 through D-0). This protocol complements the existing Taper phase detection — it does not replace it. The broader 2-week taper is handled by phase detection logic; this protocol governs the final week where day-by-day decisions matter.

**Scientific basis:** Mujika & Padilla (2003), Bosquet et al. (2007), Wang et al. (2023), Altini (HRV during taper), Pyne et al. (2009).

---

#### Three-Layer Race Awareness

The `race_calendar` block in the data mirror provides race awareness at three levels:

**Layer 1 — Race Calendar (D-90+):** Always shows all upcoming races within 90 days, regardless of distance. AI systems should acknowledge upcoming races in general coaching context (e.g., "Your A race is 23 days out, current CTL trajectory looks good for that timeline").

**Layer 2 — Taper Onset Alerts (D-14 to D-8):** When a `RACE_A` event is 8–14 days away, `taper_alert.active = true`. AI systems should:
- Alert the athlete to begin volume reduction (target 41–60% reduction over 2 weeks)
- Emphasise maintaining intensity throughout the taper
- Note that CTL should peak now or within the next few days
- Remind: reduce session duration, not frequency (frequency reduction ≤20%)

**Layer 3 — Race-Week Protocol (D-7 to D-0):** When a `RACE_A` or `RACE_B` event is ≤7 days away, `race_week.active = true`. The full day-by-day decision tree below activates.

**Race priority detection:**
- `RACE_A` within 7 days → Full race-week protocol
- `RACE_B` within 7 days → Race-week protocol with lighter taper (smaller volume reduction acceptable, lower TSB target acceptable)
- `RACE_C` → Excluded. Training races — no taper adjustments

---

#### Day-by-Day Decision Tree

All load targets are relative to the athlete's current CTL. Normal weekly TSS ≈ CTL × 7. Race-week TSS budget: 40–55% of normal weekly TSS.

| Day | Label | Load (% of CTL) | Zones | Purpose |
|-----|-------|-----------------|-------|---------|
| D-7 | Last key session | 75–100% | 3–5 efforts Z4–Z5 (1–3 min) | Fitness confirmation. Verify strong power/HR response. |
| D-6 | Recovery | ≤30% | Z1–Z2 only | Active recovery. |
| D-5 | Moderate endurance | 40–60% | Z1–Z2 + 2–3 race-pace touches | Maintain feel without adding fatigue. |
| D-4 | Easy / rest | 0–40% | Z1–Z2 only | Carb loading begins if applicable. |
| D-3 | Easy / rest | 0–40% | Z1–Z2 only | "Feeling flat" expected — see note below. |
| D-2 | Opener | 30–50% | 3–5 efforts Z4–Z6 (20–60s), high cadence, full recovery | Neuromuscular activation. |
| D-1 | Rest / minimal | 0–20% | Z1 only if active | Final rest, logistics, equipment check. |
| D-0 | Race day | — | — | Go/no-go assessment. |

---

#### Event-Type Modifiers

Event duration is classified from `moving_time` in the race event data. When `moving_time` is not set: `RACE_A` defaults to `long_endurance`, `RACE_B` defaults to `medium`.

| Duration Class | Moving Time | TSB Target | Opener (D-2) | Carb Loading | Rest vs Easy (D-4/D-3) |
|---------------|-------------|------------|---------------|-------------|------------------------|
| Short / intense | < 90 min | +5 to +15 | More intense: 5–6 efforts, include Z5–Z6 | Not required | Full rest acceptable |
| Medium | 90 min – 3 h | +10 to +20 | Standard: 3–5 efforts Z4–Z5 | Recommended | Either |
| Long endurance | > 3 h | +10 to +25 | Lighter: 3–4 efforts Z4 only | Critical (10–12 g·kg⁻¹/day from D-4) | Prefer easy endurance over complete rest |

---

#### Go / No-Go Checklist (D-0)

| Check | Green | Flag (context only) | Red |
|-------|-------|---------------------|-----|
| TSB | Within target range | >10 below target → note, do not recommend DNS | — |
| HRV | Logged for context | Never a decision input | Never a race stopper |
| Sleep | Logged for context | ≤5 h noted for the record | Never a race stopper |
| Illness / injury | None | Minor (cold, soreness) → note, race at athlete's discretion | Fever, acute injury, GI illness → recommend DNS |

**Only illness or injury can recommend DNS.** HRV and sleep are logged for post-race analysis only.

---

#### Mandatory Protocol Guidance

AI systems must include the following guidance when race-week protocol is active. These are not optional — they correct well-documented athlete misconceptions that lead to poor race-week decisions.

**Taper tantrums (D-4 through D-2):**

> During days D-4 through D-2, athletes commonly experience: reduced motivation, heavy legs, mood changes, phantom aches, and self-doubt. This is a normal physiological response to significant volume reduction ("taper tantrums") and is NOT an indication of lost fitness. Do not prescribe additional training in response to these symptoms. Maintain the taper plan.

**Pre-race sleep and HRV:**

> Pre-race sleep disruption is extremely common and does not predict poor performance. Sleep quality is logged for the record but must NEVER be used as a factor in go/no-go decisions. HRV commonly drops during taper — this is associated with increased sympathetic readiness and has been linked to world-class performance (Altini). Race-morning HRV is almost always suppressed due to anticipatory stress. This is normal, not concerning.

**Carb loading (events ≥ 90 min):**

> For events exceeding 90 minutes, a glycogen-loading strategy is recommended starting at D-4: daily carbohydrate intake of 10–12 g·kg⁻¹. No depletion phase is needed — simply increase carbohydrate intake alongside reduced training volume. Athletes should arrive at racing weight at the start of the taper, not the end.

---

#### RACE_B Modifications

When the target event is `RACE_B` rather than `RACE_A`:
- Volume reduction may be smaller (race-week TSS budget 50–65% of normal instead of 40–55%)
- TSB target range is 5 points lower than the event-type default
- The D-7 "last key session" may be a normal training session rather than a race-specific confirmation
- Carb loading is optional for medium-duration B races
- Go/no-go checklist still applies but with lower stakes — athlete discretion prevails

---

#### Edge Cases

**Multiple races in the same window:** If both a `RACE_A` and `RACE_B` fall within 7 days, the protocol targets the `RACE_A`. The `RACE_B` is treated as a training stimulus or secondary event.

**No moving_time set:** When the athlete has not entered an expected duration for the event, default to `long_endurance` for `RACE_A` and `medium` for `RACE_B`. The AI should note the assumption and suggest the athlete update the event in Intervals.icu with expected duration for more precise guidance.

**Travel disruption:** When the athlete reports travel in the days before the race, the recommendation is to reduce training load further than the protocol targets. Travel fatigue compounds taper fatigue — err on the side of more rest.

---

End of Section 11 A. AI Coach Protocol

---

## 11 B. AI Training Plan Protocol

**Purpose:**  
Define deterministic, phase-aligned rules for AI or automated systems that generate or modify training plans, ensuring consistency with the dossier’s endurance framework, physiological safety, and audit traceability.

---

### 1 — Phase Alignment
Identify the current macro-phase (**Base → Build → Peak → Taper → Recovery**) using:
- **TSB trend**, **RI trend**, and **ACWR range (0.8 – 1.3)**  
- Active-phase objectives defined in *Section 3 — Training Schedule & Framework*  

Generated plans must explicitly state the detected phase in their audit header.

---

### 2 — Volume Ceiling Validation
- Weekly training hours may fluctuate ±10 % around the athlete’s validated baseline (~15 h).  
- Expansions beyond this range require **RI ≥ 0.8 for ≥ 7 days** and HRV stability within ±10 % of baseline.  
- Any week exceeding this threshold must flag  
  `"load_variance": true` in the audit metadata.

---

### 3 — Intensity Distribution Control
- Maintain **polarisation ≈ 0.8 (80 / 20)** across the microcycle.  
- **Z3+ (≥ LT2)** time ≤ 20 % of total moving duration.  
- **Z1–Z2** time ≥ 75 % of total duration.  
- Over-threshold accumulation outside these bounds triggers automatic plan validation error.

---

### 4 — Session Composition Rules
- **2 structured sessions/week** (Sweet Spot or VO₂ max)  
- **1 long Z2 durability ride**  
- Remaining sessions = Z1–Z2 recovery or aerobic maintenance  
- Back-to-back high-intensity days prohibited unless **TSB > 0 and RI ≥ 0.85**

---

### 5 — Progression Integration
Only one progression vector may change per week **unless**:
- Pathways 1+2 (Duration + Interval): permitted if RI ≥ 0.8, HRV within 10%, no negative fatigue trend
- Pathways 2+3 (Interval + Environmental): permitted if RI ≥ 0.85, HRV stable, no recent load spikes
- Pathways 1+3 (Duration + Environmental): **never permitted**

---

### 6 — Audit Metadata (Required Header)

Every generated or modified plan must embed machine-readable metadata for audit and reproducibility:

```json
{
  "data_source_fetched": true,
  "json_fetch_status": "success",
  "plan_version": "auto",
  "phase": "Build",
  "week": 3,
  "load_target_TSS": 520,
  "volume_hours": 15.2,
  "polarization_ratio": 0.81,
  "progression_vector": "duration",
  "load_variance": false,
  "validation_protocol": "URF_v5.1",
  "confidence": "high"
}
```

---

Interpretation:
This header documents provenance, deterministic context, and planning logic for downstream validation under Section 11 C — AI Validation Protocol.

### 7 — Compliance & Error Handling

Plans breaching tolerance limits must not publish until validated.

AI systems must output an explicit reason string for rejections, e.g.:
"error": "ACWR > 1.35 — exceeds safe progression threshold"

Human-review override requires athlete confirmation and metadata flag "override": true.

---

### 8 — Workout Reference Interface

When a plan requires a structured session (per Section 4), the AI must select from the **Workout Reference Library** (`examples/workout-library/WORKOUT_REFERENCE.md`).

**Selection rules:**
- Match target adaptation (Sweet Spot, VO₂max, Endurance, etc.) to the session slot identified by the plan.
- Use Section 11 A readiness outputs (TSB, RI, HRV trend, Feel score) to choose the appropriate format variant and intensity level within that adaptation category.
- Apply the Reference Library's session sequencing rules when placing sessions within the microcycle.
- Warm-up and cool-down structures must follow the Reference Library's WU/CD protocols unless the athlete has documented personal preferences.

**Constraints:**
- The AI must not invent session structures absent from the Reference Library.
- If no suitable session template exists for the required adaptation, the AI must flag this as a gap rather than improvise.
- All workout selections must be traceable in the audit metadata (Section 6) via a `"session_template"` field referencing the template's YAML `id` (e.g., `"session_template": "SS-5"`).
- Each template includes machine-readable YAML metadata (`id`, `domain`, `is_hard_session`, `work_minutes`, `est_total_minutes`) for deterministic selection and scheduling.

---

End of Section 11 B. AI Training Plan Protocol

---

## 11 C. AI Validation Protocol

This subsection defines the formal self-validation and audit metadata structure used by AI systems before generating recommendations, ensuring full deterministic compliance and traceability.

### Validation Metadata Schema

```json
{
  "validation_metadata": {
    "data_source_fetched": true,
    "json_fetch_status": "success",
    "protocol_version": "11.11",
    "checklist_passed": [1, 2, 3, 4, 5, 6, "6b", 7, 8, 9, 10],
    "checklist_failed": [],
    "data_timestamp": "2026-01-13T22:32:05Z",
    "data_age_hours": 2.3,
    "athlete_timezone": "UTC+1",
    "utc_aligned": true,
    "system_offset_minutes": 8,
    "timestamp_valid": true,
    "confidence": "high",
    "missing_inputs": [],
    "frameworks_cited": ["Seiler 80/20", "Gabbett ACWR"],
    "recommendation_count": 3,
    "phase_detected": "Build",
    "phase_triggers": [],
    "phase_detection": {
      "phase": "Build",
      "confidence": "medium",
      "reason_codes": [],
      "basis": {
        "stream_1": {
          "ctl_slope": 0.7,
          "acwr_trend": "falling",
          "hard_day_pattern": 1.8,
          "weeks_available": 4
        },
        "stream_2": {
          "planned_tss_delta": 0.93,
          "hard_sessions_planned": 2,
          "race_proximity": null,
          "next_week_load": 1.19,
          "plan_coverage_current_week": 1.2,
          "plan_coverage_next_week": 2.6
        },
        "data_quality": "good",
        "stream_agreement": null
      },
      "previous_phase": "Build",
      "phase_duration_weeks": 4,
      "dossier_declared": null,
      "dossier_agreement": null
    },
    "seasonal_context": "Late Base / Build",
    "consistency_index": 0.92,
    "stress_tolerance": 4.2,
    "grey_zone_percentage": 3.2,
    "quality_intensity_percentage": 2.7,
    "hard_days_this_week": 2,
    "polarisation_index": 0.97,
    "specificity_volume_ratio": 0.58,
    "load_recovery_ratio": 1.8,
    "primary_readiness_status": "RI 0.84 — Good",
    "secondary_load_status": "Load-Recovery Ratio 1.8 — Normal",
    "benchmark_index": 0.03,
    "benchmark_seasonal_expected": true,
    "w_prime_data_available": true,
    "w_prime_confidence": "high",
    "seiler_tid_7d": "Polarized",
    "seiler_tid_28d": "Polarized",
    "tid_drift": "consistent",
    "durability_7d_mean": 2.1,
    "durability_28d_mean": 2.5,
    "durability_trend": "stable",
    "hrrc_7d_mean": 38,
    "hrrc_28d_mean": 36,
    "hrrc_trend": "stable"
  }
}
```

### Field Definitions

| Field                          | Type     | Description                                                                         |
|--------------------------------|----------|-------------------------------------------------------------------------------------|
| `data_source_fetched`          | boolean  | Whether JSON was successfully loaded from data source (local files, connector, or URL) |
| `json_fetch_status`            | string   | "success" / "failed" / "unavailable" — stop and request manual input if not success |
| `protocol_version`             | string   | Section 11 version being followed                                                   |
| `checklist_passed`             | array    | List of checklist items (1–10) that passed validation                               |
| `checklist_failed`             | array    | List of checklist items that failed, with reasons                                   |
| `data_timestamp`               | ISO 8601 | Timestamp of the data being referenced                                              |
| `data_age_hours`               | number   | Hours since data was last updated                                                   |
| `athlete_timezone`             | string   | Athlete's local timezone (e.g., "UTC+1")                                            |
| `utc_aligned`                  | boolean  | Whether dataset timestamps align with UTC                                           |
| `system_offset_minutes`        | number   | Offset between system and data clocks                                               |
| `timestamp_valid`              | boolean  | Whether timestamp passed validation                                                 |
| `confidence`                   | string   | "high" / "medium" / "low" based on data completeness                                |
| `missing_inputs`               | array    | List of metrics that were unavailable                                               |
| `frameworks_cited`             | array    | Scientific frameworks applied in reasoning                                          |
| `recommendation_count`         | number   | Number of actionable recommendations provided                                       |
| `phase_detected`               | string/null | Backward-compat shortcut: current phase (Build/Base/Peak/Taper/Deload/Recovery/Overreached/null). Extracted from `phase_detection.phase`. |
| `phase_triggers`               | array    | Backward-compat shortcut: reason codes from `phase_detection.reason_codes`.         |
| `phase_detection`              | object   | Full phase detection v2 output (see sub-fields below).                              |
| `phase_detection.phase`        | string/null | Classified phase: Build, Base, Peak, Taper, Deload, Recovery, Overreached, or null. |
| `phase_detection.confidence`   | string   | "high" / "medium" / "low" — based on signal strength, data quality, stream agreement. |
| `phase_detection.reason_codes` | array    | Machine-readable classification reasons (e.g., `RACE_IMMINENT_VOLUME_REDUCING`, `BUILD_HISTORY_REDUCED_LOAD_REBOUND_CONFIRMED`, `PLAN_GAP_NEXT_WEEK`, `INSUFFICIENT_LOOKBACK`). |
| `phase_detection.basis.stream_1` | object | Retrospective features: `ctl_slope`, `acwr_trend`, `hard_day_pattern`, `weeks_available`. |
| `phase_detection.basis.stream_2` | object | Prospective features: `planned_tss_delta`, `hard_sessions_planned`, `race_proximity`, `next_week_load`, `plan_coverage_current_week`, `plan_coverage_next_week`. |
| `phase_detection.basis.data_quality` | string | "good" / "mixed" / "poor" — penalized by HR-only intensity basis, short lookback. |
| `phase_detection.basis.stream_agreement` | boolean/null | Whether Stream 1 and Stream 2 suggested the same phase. null if either stream has no opinion. |
| `phase_detection.previous_phase` | string/null | Phase from last weekly_180d row (feeds hysteresis).                              |
| `phase_detection.phase_duration_weeks` | number | Consecutive weeks classified as current phase.                                 |
| `phase_detection.dossier_declared` | string/null | Phase declared in athlete dossier (optional input).                            |
| `phase_detection.dossier_agreement` | boolean/null | Whether detected phase matches dossier declaration.                           |
| `readiness_decision`           | object   | Pre-computed go/modify/skip decision (v3.72+). Top-level, alongside `alerts`. |
| `readiness_decision.recommendation` | string | "go" / "modify" / "skip" — baseline recommendation for pre-workout reports. |
| `readiness_decision.priority`  | number   | 0 (safety stop), 1 (acute overload), 2 (accumulated fatigue), 3 (green light). |
| `readiness_decision.signals`   | object   | Per-signal status objects (hrv, rhr, sleep, tsb, acwr, feel, ri). Each has `status` (green/amber/red/unavailable) and raw values with deltas. |
| `readiness_decision.signal_summary` | object | Pre-counted tallies: `green`, `amber`, `red`, `unavailable`. |
| `readiness_decision.phase_context` | object | `phase`, `phase_week`, `amber_threshold`, `modifier_applied` — shows which phase rule shifted thresholds. |
| `readiness_decision.race_week_defers` | boolean | When true, modification guidance defers to race-week protocol day-by-day targets. |
| `readiness_decision.modification` | object/null | When recommendation is "modify": `triggers` (signal names), `suggested_adjustments` (`intensity`, `volume`, `cap_zone`). Null for "go" and "skip". |
| `readiness_decision.reason`    | string   | Audit-grade factual reason. E.g., "P2 signal count. 2 amber (rhr, sleep) >= threshold 2." Not coaching prose. |
| `readiness_decision.alarm_refs` | array   | Alert metric names that triggered P0/P1. Empty array for P2/P3. |
| `seasonal_context`             | string   | Current position in annual training cycle                                           |
| `consistency_index`            | number   | 7-day plan adherence ratio (0–1)                                                    |
| `stress_tolerance`             | number   | Current load absorption capacity                                                    |
| `grey_zone_percentage`         | number   | Grey zone time as percentage — to minimize                                          |
| `quality_intensity_percentage` | number   | Quality intensity time as percentage                                                |
| `hard_days_this_week`          | number/null | Count of days meeting zone ladder thresholds. **Power ladder** (5 rungs): Z3+ ≥ 30min, Z4+ ≥ 10min, Z5+ ≥ 5min, Z6+ ≥ 2min, or Z7 ≥ 1min. **HR fallback** (2 rungs, when no power zones): Z4+ ≥ 10min or Z5+ ≥ 5min. `null` if no zone data exists. Per Seiler 3-zone model + Foster |
| `polarisation_index`           | number   | Easy time (Z1+Z2) as ratio of total                                                 |
| `specificity_volume_ratio`     | number   | Event-specific volume ratio (0–1)                                                   |
| `load_recovery_ratio`          | number   | 7-day load divided by RI (secondary metric)                                         |
| `primary_readiness_status`     | string   | Summary of primary readiness marker (RI)                                            |
| `secondary_load_status`        | string   | Summary of secondary load metric status                                             |
| `benchmark_index`              | number   | FTP progression ratio                                                               |
| `benchmark_seasonal_expected`  | boolean  | Whether current Benchmark Index is within seasonal expectations                     |
| `w_prime_data_available`       | boolean  | Whether CP/W′ data is available                                                     |
| `w_prime_confidence`           | string   | Confidence level of W′ estimates ("high" / "medium" / "low" / "unavailable")        |
| `seiler_tid_7d`                | string   | Seiler TID classification for 7-day window (Polarized/Pyramidal/Threshold/etc.) |
| `seiler_tid_28d`               | string   | Seiler TID classification for 28-day window                                     |
| `tid_drift`                    | string   | TID drift category: "consistent" / "shifting" / "acute_depolarization"          |
| `durability_7d_mean`           | number   | Mean HR–Power decoupling (%) from qualifying steady-state sessions, 7-day       |
| `durability_28d_mean`          | number   | Mean HR–Power decoupling (%) from qualifying steady-state sessions, 28-day      |
| `durability_trend`             | string   | Durability trend: "improving" / "stable" / "declining"                          |
| `hrrc`                         | number/null | Per-activity HRRc: largest 60-second HR drop (bpm) after exceeding configured threshold HR for >1 min. Intervals.icu API field `icu_hrr`. Null when threshold not reached, recording stopped before cooldown, or no HR data. Higher = better parasympathetic recovery. |
| `capability.hrrc.mean_hrrc_7d` | number/null | Mean HRRc (bpm) from qualifying sessions in last 7 days. Requires ≥ 1 session. |
| `capability.hrrc.mean_hrrc_28d`| number/null | Mean HRRc (bpm) from qualifying sessions in last 28 days. Requires ≥ 3 sessions. |
| `capability.hrrc.trend`        | string/null | HRRc trend: "improving" / "stable" / "declining". >10% difference between 7d and 28d means = meaningful. Null if either window has insufficient sessions. Display only — not wired into readiness_decision signals. |

---

### Plan Metadata Schema (Section 11 B Reference)

| Field                 | Type    | Description                                                                         |
|-----------------------|---------|-------------------------------------------------------------------------------------|
| `data_source_fetched` | boolean | Whether JSON was successfully loaded from data source (local files, connector, or URL) |
| `json_fetch_status`   | string  | "success" / "failed" / "unavailable" — stop and request manual input if not success |
| `plan_version`        | string  | Version identifier for the plan                                                     |
| `phase`               | string  | Current macro-phase (Base/Build/Peak/Taper/Recovery)                                |
| `week`                | number  | Week number within current phase                                                    |
| `load_target_TSS`     | number  | Target weekly TSS                                                                   |
| `volume_hours`        | number  | Target weekly training hours                                                        |
| `polarization_ratio`  | number  | Target polarization (≈ 0.8)                                                         |
| `progression_vector`  | string  | Active progression type (duration/intensity/environmental)                          |
| `load_variance`       | boolean | Whether volume exceeds ±10% baseline                                                |
| `validation_protocol` | string  | Framework version (e.g., "URF_v5.1")                                                |
| `confidence`          | string  | "high" / "medium" / "low"                                                           |
| `override`            | boolean | Human override flag (requires athlete confirmation)                                 |
| `error`               | string  | Rejection reason if validation failed                                               |

Validation routines parse and cross-verify all metadata fields defined in Section 11 B — AI Training Plan Protocol to confirm compliance before plan certification.

---

End of Section 11 C. AI Validation Protocol

---

## Summary

This protocol ensures that any AI engaging with athlete data provides structured, evidence-based, non-speculative, and deterministic endurance coaching.

**If uncertain — ask, confirm, and adapt rather than infer.**

This ensures numerical integrity, auditability, and consistent long-term performance alignment with athlete objectives.

> This protocol draws on concepts from the **Intervals.icu GPT Coaching Framework** (Clive King, revo2wheels) and the **Unified Reporting Framework v5.1**, with particular reference to stress tolerance, zone distribution indexing, and tiered audit validation approaches. Special thanks to **David Tinker** (Intervals.icu) and **Clive King** for their foundational work enabling open endurance data access and AI coaching integration.

---

End of Section 11

---
