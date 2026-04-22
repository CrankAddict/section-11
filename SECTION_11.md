# Section 11 — AI Coach Protocol

**Protocol Version:** 11.37  
**Last Updated:** 2026-04-22
**License:** [MIT](https://opensource.org/licenses/MIT)

### Changelog

**v11.37 — has_intervals Semantics Fix:**
- `has_intervals` now requires at least one `type == "WORK"` segment in the intervals.json entry — previously any non-empty segment list set the flag true
- Pre-existing bug dating to v3.101 narrowing: Intervals.icu emits a single whole-session `RECOVERY` placeholder on unstructured endurance rides, which the prior check treated as structured. Live evidence from the v3.105 test run: 9 false positives (SkiErg, virtual endurance) vs 3 true RECOVERY,WORK activities across 62 sessions
- v3.101 intent ("narrowed to structured segments only") now actually enforced at the check level. Descriptive docs already reflected the intended behavior — no consumer semantics change, only the implementation catching up
- `has_dfa` behavior unchanged. `_generate_intervals` collection logic unchanged — intervals are still fetched for DFA purposes whether or not a WORK segment exists
- Requires sync.py v3.106

**v11.36 — Effort Response Signal:**
- New `effort_response` key on every `recent_activities[]` entry in `latest.json`. Deterministic classifier reading session IF (`intensity_factor`) against reported RPE (`rpe`) through the v11.34 RPE Expectation Bands
- Values: `"positive"` (RPE below band — fitness/freshness tell), `"neutral"` (RPE within band), `"negative"` (RPE above band — fatigue/under-recovery tell), `null` (IF absent, RPE absent or ≤ 0, or IF < 0.65)
- The IF < 0.65 null is a **deliberate design gap**, not missing data — recovery rides and aborted sessions fall outside the bands' calibration range. Classifier returns null rather than fabricating a band there
- Session IF used by design. Matches whole-session RPE the athlete actually logs. Work-portion IF from `intervals.json` remains available for case-by-case inspection but is not the field value
- `intensity_factor` is stored as percentage (0–100+) and is normalized to decimal at the classifier boundary to match the canonical band table
- New rendered `IF:` line on the post-workout per-session block (previously unrendered despite the field being on every activity)
- Interpretive overlay only. Does NOT alter Feel/RPE Override rules (v11.14) and does NOT enter the readiness P0–P3 ladder
- Closes the first of the `Known Future Touchpoints` flagged in v11.34
- Requires sync.py v3.105

**v11.35 — Aggregate Durability Reliability Gate:**
- Alert-firing paths now gated on sample size: alarm (28d mean > 5%) requires `qualifying_sessions_28d ≥ 5`; declining warning (7d > 28d by > 2%) requires `qualifying_sessions_7d ≥ 3 AND qualifying_sessions_28d ≥ 5`
- Below gate, `capability.durability` exposes `reliability_limited: true` and `reliability_note` (both current N values with both minimums) — means remain visible for situational awareness but no alert fires
- `high_drift_count_7d ≥ 3` warning unchanged (count-based, self-guarding)
- Filter criteria (VI ≤ 1.05, ≥ 90 min) unchanged — this is a sample-size safeguard, not a metric redefinition
- Citation fix: `Rothschild & Maunder (2025)` → `Rothschild et al. (2025)` in two places (9-author paper, `et al.` is the correct form)
- Addresses GitHub issue #11
- Requires sync.py v3.104

**v11.34 — Testing Protocol & RPE Expectation Bands:**
- New section: `Testing Protocol` — codifies when formal testing adds value given continuous-data coverage (Benchmark Index, DFA a1 crossings, sustained-power observations, power-curve / HR-curve deltas). Continuous-data-first philosophy; tests as validation/confirmation/onboarding, not primary zone source
- Data-driven staleness signals defined: DFA a1 calibration delta at `moderate`/`high` confidence and >5% dossier delta (primary trigger); Benchmark Index stall/regression outside seasonal expectation; sustained power above prescribed zones (requires ≥2 sessions in rolling 7d — noise guard); power-curve vs HR-curve divergence
- Negative triggers: non-go readiness, recovery week, illness within 14d, ACWR outside safe band, RI persistent amber, phase Peak or Taper, Race-Week Protocol active, adverse environment
- Protocol options table: 20-min ×0.95, ramp, 2×8min with honest strengths/limitations. Running equivalents deferred (owner: pace curve extension)
- Interpretation rules: same-conditions comparison (indoor vs outdoor, protocol, freshness), accept/reject criteria, expected improvement rates by phase
- New subsection: `RPE Expectation Bands (IF-calibrated)` — reference table mapping IF bands to expected RPE at the work portion. Consumers: test-result validation, general session-effort reading, canonical spec for future Effort Response Signal. Duration, indoor/outdoor, and environmental modifiers documented. Does NOT alter Feel/RPE Override rules (v11.14)
- Boundaries: does NOT mandate testing, does NOT auto-update dossier zones, does NOT enter readiness P0–P3, does NOT override continuous data
- Two-way cross-references added: Benchmark Index (Governance Rules) and DFA a1 Zone Validation Use both forward-link to Testing Protocol
- Documentation-only; no sync.py changes, no template changes, no report changes
- Future touchpoints flagged: post-workout report RPE-vs-expected commentary (separate template pass), running-specific RPE bands (with pace curve extension)

**v11.33 — Athlete Profile, Notes & Activity Unit Labels:**
- New top-level `athlete_profile` block in `latest.json` — stable identity fields from existing athlete endpoint call (zero new API calls): `date_of_birth`, derived `age`, `height_m`, `sex`, `location`, `timezone`, `platform_activated`, derived `years_on_platform`
- New top-level `athlete_notes` block — raw string passthrough of `icu_notes` (free-text athlete-maintained notes). Opaque text; AI may reference for context but should not parse for structured coaching parameters. Future schema work may restructure into a typed mini-dossier
- Per-field unit labels added to `recent_activities[]` entries: `avg_temp_unit` (`C`/`F` from athlete account setting), `wind_speed_unit` (`MPS`/`KPH`/`MPH` passthrough), `avg_speed_unit` and `max_speed_unit` (always `KPH` — sync.py force-converts m/s → km/h regardless of athlete preference; label surfaces this latent asymmetry vs. account-respecting temp/wind)
- Sibling-field form (e.g. `avg_temp` + `avg_temp_unit`) chosen over nested `{value, unit}` object — additive, non-breaking for existing consumers reading these as scalars
- Behavior posture: `athlete_profile` fields are informational. They do NOT enter readiness P0–P3 logic, threshold computation, or any numeric coaching pathway in the current protocol
- Data hygiene: silent trailing-space bug in Intervals.icu location strings (`'Aalborg '`, `'Nordjylland '`) handled via `.strip()` in `_compose_location` helper
- Requires sync.py v3.103

**v11.32 — has_dfa Split & dfa_summary:**
- New `has_dfa` boolean on `recent_activities[]` in `latest.json` — independent from `has_intervals`. AlphaHRV-equipped sessions now flag explicitly rather than overloading `has_intervals`
- `has_intervals` semantics narrowed: now `true` only when structured interval segments exist. A steady Z2 ride with AlphaHRV gets `has_intervals: false`, `has_dfa: true` (previously the latter overloaded the former)
- New compact `dfa_summary` block attached to `recent_activities[]` when `has_dfa: true` AND `quality.sufficient: true`. Fields: `avg`, `dominant_band` (max-pct, alphabetical tiebreak), `tiz_pct` (4 bands), `valid_pct`, `sufficient`, plus optional `drift_delta`/`drift_interpretable` and `lt1_watts`/`lt1_hr`/`lt2_watts`/`lt2_hr` (omitted when underlying data absent — never null-filled)
- AI layer can now write post-workout DFA commentary from `latest.json` alone without loading `intervals.json` for the common case. Full per-band HR/watts averages and per-interval detail still live in `intervals.json` for deep analysis
- `quality.sufficient` tightened: previously duration-only (≥20 min valid); now also requires `valid_pct ≥ 70%`. Excludes noisy AlphaHRV sessions that previously passed the duration gate. New constant `DFA_SUFFICIENT_MIN_VALID_PCT = 70.0`. Pre-existing latent bug where 40%-valid sessions reported `sufficient: true`
- `has_dfa: true` without a `dfa_summary` means AlphaHRV recorded but data quality was insufficient — AI must not cite DFA numbers in that case
- Interval Data Mirror loading rule simplified to two-flag form: load when `has_intervals: true` OR `has_dfa: true`. Three-trigger rule retired
- Docs sync across SECTION_11.md, SKILL.md, README.md, SETUP_ASSISTANT.md, examples/README.md, examples/json-examples/README.md, examples/json-local-sync/SETUP.md
- Requires sync.py v3.101

**v11.31 — DFA Power Calibration Indoor/Outdoor Split:**
- `trailing_by_sport.cycling` lt1_estimate / lt2_estimate: watts split by environment — `watts_outdoor`, `watts_indoor` (always present, null when no qualifying sessions in that environment). HR stays pooled (physiology signal, not environment-dependent). Non-cycling sports unchanged (`watts` key retained)
- Per-environment session counts: `n_sessions_outdoor`, `n_sessions_indoor` on each estimate block. Same 3/4–5/≥6 confidence thresholds apply per environment for watts calibration delta surfacing
- Zone Validation Use updated: compare `watts_outdoor` against dossier `ftp`, `watts_indoor` against `ftp_indoor`. Fallback: if only one environment has data and the other context's dossier FTP is missing, the available estimate may inform directionally with cross-environment caveat
- Shared `_is_indoor_cycling()` resolver (VirtualRide = indoor) used by DFA profile and sustainability profile
- Requires sync.py v3.100

**v11.30 — DFA a1 Protocol:**
- New section: DFA a1 Protocol — non-linear HRV index from AlphaHRV Connect IQ data field, ingested via Intervals.icu streams when direct Garmin sync is used (Strava strips developer fields)
- Threshold mapping: DFA a1 ≈ 1.0 ↔ LT1/AeT, DFA a1 ≈ 0.5 ↔ LT2/VT2 (Rowlands 2017, Gronwald 2020, Mateo-March 2023). Cycling-validated only — non-cycling sports get rollups but flagged validated=False
- Per-session `dfa` block in `intervals.json`: artifact-filtered avg, 4-band TIZ split (below_lt1 / lt1_transition / transition_lt2 / above_lt2) with HR/power cross-references per band, drift (first vs last third) with `interpretable` flag tied to time-above-LT2, LT1/LT2 crossing-band estimates (avg HR/watts in narrow ±0.05 windows around each threshold), quality block with sufficient flag
- `dfa_a1_profile` in `latest.json` capability block: latest_session + trailing_by_sport (per sport family, last 7 sessions, confidence low/moderate/high based on crossing-dwell N)
- Quality gates: ≥20 min valid data per session, max 5% artifact rate per second, AlphaHRV sentinel zeros excluded
- Tier-2 interpretive signal: does NOT enter readiness P0–P3 ladder, does NOT auto-update dossier zones; surfaces calibration deltas only
- Drift-on-structured-sessions guard: `interpretable: false` when >15% of session was above LT2 (drift number reflects session structure, not autonomic)
- Always-emit rule: when AlphaHRV streams fetched, dfa block is always written (even with `quality.sufficient: false`) so AI can distinguish "no AlphaHRV" from "AlphaHRV ran but unusable"
- `intervals.json` scope widened: activities now included when they have **either** structured intervals **or** an AlphaHRV `dfa` block. Pure endurance rides without intervals appear when DFA recorded — that's where DFA drift detection is most valuable
- Trailing window bumped 5 → 7 sessions so `confidence: high` (≥6 contributing) is achievable
- `latest_session` now carries a `validated` flag (cycling = true, others = false) so the AI cannot accidentally overread non-cycling sessions
- Intervals.json retention bumped 8d → 14d to support DFA drift analysis across multiple sessions
- Evidence base: 5 entries (Rowlands 2017, Gronwald 2020, Schaffarczyk 2023, Mateo-March 2023, Altini methodology)
- POST_WORKOUT_REPORT_TEMPLATE.md: new `DFA a1` line in per-session block (conditional on `dfa` block presence), Field Notes row with three-way branching rules (absent / sufficient=false / sufficient=true) and per-interval-vs-session-level distinction note, Assessment Labels row
- POST_WORKOUT_REPORT_EXAMPLES.md: Example 6 (long Z2 ride with interpretable drift flag triggering fueling/heat cross-reference per protocol) and Example 7 (sweet spot session with consonant DFA reading, drift flagged structural)
- BLOCK_REPORT_TEMPLATE.md: new `DFA a1 Calibration` section heavily gated (cycling only, validated=true, confidence ≥ moderate), Field Definitions row, Notes entry stressing protocol-anchored thresholds and no auto-zone-updates
- BLOCK_REPORT_EXAMPLES.md: Example 3 (6-week aerobic base block with DFA calibration surfacing — moderate confidence, empirical LT1 delta vs dossier, LT2 estimate appropriately omitted due to lt2_crossing_sessions=2)
- Interval Data Mirror loading rule: extended to also load when an activity has a `dfa` block (covers steady-state rides with no structured intervals — they now appear in intervals.json under the widened entry rule)
- Requires sync.py v3.99

**v11.29** — Post-Workout Report Completeness Rules: per-activity block enforcement, anti-merge, anti-hallucination guard for unexplained sessions; new multi-sport example; docs-only  
**v11.28** — Schema rename: `derived_metrics.polarisation_index` → `easy_time_ratio` (disambiguates from Seiler PI, no value change); sync.py v3.98  
**v11.27** — Readiness signal hygiene: low-side ACWR removed from ambers, RI amber requires 2-day persistence, ACWR high-side boundary unified ≥1.3/≥1.5; sync.py v3.97  
**v11.26** — Nutrition & Pacing Protocol expansion: kJ→carbs dosing, absorption limits, glycogen budget, temperature-driven hydration; fast-start penalty; W′ depletion under glycogen deficit  
**v11.25** — Course character fix: elevation_per_km as sole density metric; start_time on routes.json events  
**v11.24** — Route & Terrain Protocol: new section — route analysis, terrain-adjusted power, wind/drafting overlay, segment feasibility, pre-ride briefing; sync.py v3.95

**v11.23** — Checklist 5b: training metrics must come from current JSON data read, never from conversation history, prior messages, or cached/recalled context  
**v11.22** — Sustainability Profile capability metric: per-sport power/HR sustainability table for race estimation, 42-day window, cycling three-layer model (actual MMP, Coggan factors, CP/W'); sync.py v3.91  
**v11.21** — Sleep Signal Simplification: hours-only (quality/score removed from readiness — double-counts HRV/HR); sync.py v3.90  
**v11.20** — HR Curve Delta capability metric: max sustained HR at 4 anchor durations across two 28-day windows, no sport filter (cross-sport physiological); sync.py v3.88  
**v11.19** — Power Curve Delta capability metric: MMP at 5 anchor durations across two 28-day windows, rotation index (sprint vs endurance adaptation); sync.py v3.87  
**v11.18** — Environmental Conditions Protocol: delta-based heat stress tiers, session-type modification rules, acclimatization timeline, cold-weather subsection  
**v11.17** — Phase context + tomorrow preview in report templates (conditional on phase confidence, session planning)  
**v11.16** — Wellness field expansion: all Intervals.icu wellness fields passthrough (subjective, vitals, body comp, nutrition, lifestyle, cycle); `hrvSDNN` case-bug fix; sync.py v3.85  
**v11.15** — Per-sport zone preference: `ZONE_PREFERENCE` config for power/HR zone basis per sport family (config → env → default cascade); sync.py v3.83  
**v11.14** — Feel/RPE scope clarified: removed from automated readiness_decision signals (6 remain); three-layer definition (wellness/activity/in-session); Feel/RPE Override block, P2 de-escalation only  
**v11.13** — Readiness Decision (AAS formalization): pre-computed go/modify/skip, P0–P3 priority ladder, 7 signals, phase modifiers, structured modification output; sync.py v3.72  
**v11.12** — HRRc integration (heart rate recovery, 7d/28d trend); phase transition narrative + phase timeline added to weekly/block report templates  

**v11.11** — Phase Detection v2: dual-stream architecture (retrospective + prospective), 8 phase states, confidence model, hysteresis, reason codes  
**v11.10** — Hard day HR zone fallback for non-power sports (running, SkiErg, rowing); shared zone helpers  
**v11.9** — Efficiency Factor (EF = NP ÷ Avg HR) tracking with 7d/28d aggregation and trend detection  
**v11.8** — Per-Sport Threshold Schema: sport-isolated thresholds, cross-sport application forbidden, global estimates at top level

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
| Capability Metrics | Section 11 (11A, subsection 9) | AI capability-layer analysis (durability, TID comparison, power curve delta, HR curve delta, sustainability profile) |
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
2. **GitHub connector** — the athlete's data repo connected via the platform's native GitHub integration. The AI reads `latest.json`, `history.json`, `intervals.json`, and any other committed files (e.g., `DOSSIER.md`, `SECTION_11.md`) directly through the connector. No URLs needed. Connectors are read-only — they cannot trigger GitHub Actions or execute scripts.
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

#### Athlete Profile Schema

`athlete_profile` is a stable identity block sourced from the Intervals.icu athlete endpoint at sync time. Fields:

| Field | Type | Notes |
|-------|------|-------|
| `date_of_birth` | string/null | ISO `YYYY-MM-DD` |
| `age` | int/null | Derived from `date_of_birth` at sync time |
| `height_m` | float/null | Meters |
| `sex` | string/null | `M` / `F` |
| `location` | string/null | `"city, state, country"` (omitting null parts; whitespace stripped) |
| `timezone` | string/null | IANA tz, e.g. `Europe/Copenhagen` |
| `platform_activated` | string/null | ISO `YYYY-MM-DD` — Intervals.icu account creation date |
| `years_on_platform` | int/null | Derived from `platform_activated` at sync time; indicates available data depth |

These fields are informational context for AI coaching. They do NOT enter readiness P0–P3 logic, threshold computation, or any numeric coaching pathway in the current protocol.

#### Athlete Notes Schema

`athlete_notes` is a raw string passthrough of the athlete's `icu_notes` field — free-text athlete-maintained notes (training plan summaries, weekly structure, season context). Treated as opaque text by the protocol; AI may reference it for context but should not parse it for structured coaching parameters. Future schema work may restructure this into a typed mini-dossier.

#### Activity Unit Labels

`recent_activities[].avg_temp_unit`, `wind_speed_unit`, `avg_speed_unit`, and `max_speed_unit` accompany their respective numeric fields:

- `avg_temp_unit`: `"C"` or `"F"` — reflects athlete's Intervals.icu account temperature setting; the API returns `avg_temp` in this unit.
- `wind_speed_unit`: `"MPS"`, `"KPH"`, or `"MPH"` — reflects athlete's account wind setting; the API returns `wind_speed` in this unit.
- `avg_speed_unit` / `max_speed_unit`: always `"KPH"` — sync.py converts m/s → km/h unconditionally regardless of athlete preference. Surfacing the label makes this asymmetry visible.

#### History Data Mirror (history.json)

In addition to the real-time `latest.json` mirror, athletes may provide a `history.json` file containing longitudinal training data with tiered granularity:

- **90-day tier:** Daily resolution (date, hours, TSS, CTL/ATL/TSB, HRV, RHR, zone distribution, weight)
- **180-day tier:** Weekly aggregates (hours, TSS, CTL/ATL/TSB, zones, hard days, longest ride)
- **1/2/3-year tiers:** Monthly aggregates (hours, TSS, CTL range, zones, phase, data completeness)
- **FTP timeline:** Every FTP change with date and type (indoor/outdoor)
- **Data gaps:** Periods with missing or low data, flagged factually without inference

`history.json` is auto-generated by sync.py when missing or stale (>28 days), pulling fresh from the Intervals.icu API.

#### Interval Data Mirror (intervals.json)

Per-interval segment data for recent structured sessions, plus optional DFA a1 session-level rollups when AlphaHRV recorded. Activities in `latest.json` are flagged with two independent booleans: `has_intervals: true` (structured segments present) and `has_dfa: true` (AlphaHRV recorded). Either flag indicates a corresponding entry in `intervals.json`. Sessions with `has_dfa: true` and sufficient data quality also carry a compact `dfa_summary` block on the activity in `latest.json` (avg, dominant_band, tiz_pct, valid_pct, sufficient, plus optional drift_delta/drift_interpretable and lt1/lt2 watts/hr when crossings dwelled long enough). `has_dfa: true` without a `dfa_summary` means AlphaHRV recorded but data quality was insufficient to interpret — do not cite DFA numbers.

**Scope:** 14-day retention, incrementally cached (72h scan window on subsequent runs, 14-day backfill on first run). Activities in whitelisted sport families (cycling, run, ski, rowing, swim) are included when they have **either** detected interval structure (`intervals` array populated) **or** an AlphaHRV-recorded `dfa_a1` stream (`dfa` block present). Pure endurance rides without structured intervals appear in this file when they have a DFA block — that's by design, since steady-state rides are exactly where DFA a1 drift detection is most useful.

**Per-interval fields:**

| Field | Type | Notes |
|-------|------|-------|
| `type` | string | `WORK` or `RECOVERY` |
| `label` | string/null | Group ID from Intervals.icu (e.g., `596s@259w100rpm`) |
| `duration_secs` | number | Elapsed time for this segment |
| `avg_power` | number/null | Average power (watts) |
| `max_power` | number/null | Peak power (watts) |
| `avg_hr` | number/null | Average heart rate |
| `max_hr` | number/null | Peak heart rate |
| `avg_cadence` | number/null | Average cadence |
| `zone` | number/null | Power zone for this segment |
| `w_bal` | number/null | W' balance at end of segment |
| `training_load` | number/null | Segment training load |
| `decoupling` | number/null | HR:power decoupling for this segment |
| `avg_dfa_a1` | number/null | Per-interval DFA a1 average (when AlphaHRV recorded) |

Null fields are stripped from output — only populated fields appear per segment.

**Optional `dfa` block (per activity):** Present only when AlphaHRV Connect IQ data field recorded a `dfa_a1` stream and the activity reached Intervals.icu via direct Garmin sync. Absence of the block means no AlphaHRV recording. Block-present-with-`quality.sufficient: false` means AlphaHRV ran but data was unusable (too short, too noisy, sentinel-only).

| Field | Type | Notes |
|-------|------|-------|
| `avg` | number/null | Artifact-filtered, zero-excluded mean DFA a1 |
| `p25` / `p50` / `p75` | number/null | Quartiles of valid DFA a1 values |
| `tiz_below_lt1` | object/null | DFA a1 > 1.0 (below LT1, true aerobic): `secs`, `pct`, `avg_hr`, `avg_watts` |
| `tiz_lt1_transition` | object/null | 0.75 ≤ DFA a1 ≤ 1.0 (upper Z2 / tempo) |
| `tiz_transition_lt2` | object/null | 0.5 ≤ DFA a1 < 0.75 (sweet spot / threshold) |
| `tiz_above_lt2` | object/null | DFA a1 < 0.5 (above LT2, supra-threshold) |
| `drift` | object/null | First-third vs last-third comparison: `first_third_avg`, `last_third_avg`, `delta`, `interpretable` (false when >15% time above LT2 — structural noise) |
| `lt1_crossing` | object | HR/watts in 0.95–1.05 band: `secs_in_band`, `avg_hr`, `avg_watts` (null when secs_in_band < 60) |
| `lt2_crossing` | object | HR/watts in 0.45–0.55 band: same shape |
| `quality` | object | `valid_secs`, `total_secs`, `valid_pct`, `artifact_rate_avg`, `sufficient` |

**See DFA a1 Protocol section for interpretation rules.**

**Loading rule:** Load `intervals.json` when analyzing a specific activity where `has_intervals: true` OR `has_dfa: true`. For block reports, load `intervals.json` when any session in the block has either flag set. Use for: interval compliance, pacing analysis, cardiac drift per set, recovery quality, DFA a1 session-level interpretation, block-scale calibration deltas. Do not load for readiness, load management, or weekly summaries.

#### Data Source Usage Hierarchy

| Source | Purpose | When to Use |
|--------|---------|-------------|
| `latest.json` | Current state — readiness, load, go/modify/skip decisions | **Always primary.** All immediate coaching decisions use this. |
| `history.json` | Longitudinal context — trends, seasonal patterns, phase transitions | **Context only.** Reference when questions require historical depth. |
| `intervals.json` | Per-interval segment data for structured sessions, plus DFA a1 session rollups | **On-demand.** Load when analyzing activities with `has_intervals: true` or `has_dfa: true`. |

**Rules:**
1. `latest.json` is always primary. All immediate coaching decisions (readiness, load prescription, go/modify/skip) use `latest.json`.
2. `history.json` is context, never override. It informs interpretation but never overrides current readiness signals.
3. Reference `history.json` for: trend questions, seasonal pattern matching, phase transition decisions, FTP/Benchmark interpretation, and when data confidence is limited.
4. Do NOT reference `history.json` for: daily pre/post workout reports (unless investigating), simple go/modify/skip decisions where readiness is clear, or any time `latest.json` provides a definitive answer on its own.
5. `intervals.json` is on-demand only. Load when the athlete asks about a specific session, when generating a post-workout report for an activity with `has_intervals: true` or `has_dfa: true`, or when evaluating pacing/compliance across interval sets or DFA a1 session-level detail.

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
|   Rothschild et al. (2025)                                 | Validated HR and power decoupling as field-based durability predictors in endurance athletes                                  |
|   Smyth (2022)                                              | Cardiac drift analysis across 82,303 marathon performances; validated decoupling as durability marker at scale                |
|   Racinais et al. (2015); Périard et al. (2015) — Heat consensus | Heat acclimatization, environmental performance decrements, session modification in heat                                  |

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
| Overreached | Safety gate — triggers immediately when detected | Current-week ACWR ≥1.5, or elevated monotony (>2.5) + ACWR ≥1.3 + rising trend |
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

**Easy Time Ratio** (used in `derived_metrics.easy_time_ratio`):
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

#### Zone Preference Configuration

Zone aggregations (TID, polarization index, grey zone %, quality intensity %, hard day detection) default to **power zones preferred, HR zones as fallback** per activity. The `ZONE_PREFERENCE` config overrides this per sport family.

**Format:** `sport_family:basis` pairs, comma-separated. Example: `run:hr,cycling:power`.

When configured, the aggregation layer prefers the specified zone basis for that sport family, falling back to the other if the preferred basis is unavailable. Unspecified sport families retain the default (power-preferred).

**Output fields:**
- `zone_preference` in `READ_THIS_FIRST` — shows the active configuration (empty dict = default)
- `zone_basis` on `zone_distribution_7d`, `seiler_tid_7d`, `seiler_tid_7d_primary`, `seiler_tid_28d`, `seiler_tid_28d_primary` — `"power"`, `"hr"`, or `"mixed"` (when activities in the aggregation used different bases)

**AI coaching rule:** When `zone_basis` is not `"power"` (the default), note the basis in reports so the athlete understands which zones drove the analysis. Per-activity zone distributions in `recent_activities` still output both power and HR zones regardless of this setting.

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
- When Benchmark Index stalls or regresses outside seasonal expectations, see the `Testing Protocol` section below for guidance on when formal confirmation testing adds value

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
| 5b | No Conversational Data Substitution | Training metrics must come from the current JSON data read. Never use values from conversation history, prior messages, cached session context, or AI memory/recall. No data read in this response = no metric cited. If a value isn't in the JSON files at query time, state "data unavailable." |
| 6  | Temporal Data Validation         | Verify "last_updated" timestamp is <24 hours old. If data is >48 hours, request a refresh. Flag if athlete context (illness, travel) contradicts data. |               
| 6b | UTC Time Synchronization         | Confirm dataset and system clocks align to UTC. Flag if offset >60 min or timestamps appear ahead of query time.                                       |
| 7  | Multi-Metric Conflict Resolution | If HRV/RHR conflict with athlete-reported state, prioritize athlete-provided readiness. Note discrepancy, request clarification. Never override illness/fatigue with “good” TSB. |
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
   - Note (athlete text or coach notes, if present on the activity)
   Omit fields only if data unavailable for that activity type.
4. **Weekly totals (rolling 7d) block:** Polarization, Durability (7d/28d + trend), TID 28d (+ drift), TSB, CTL, ATL, Ramp rate, ACWR, Hours, TSS
5. **Overall:** Coach note (2–4 sentences — compliance, key quality observations, load context, recovery note if applicable)

See **Output Format Guidelines** for full field reference, assessment labels, and report templates.

**Do NOT:**
- Use single-paragraph responses for workout reviews
- Use bullet-point lists for session data (use structured line-by-line format)
- Ask follow-up questions when data is complete and metrics are good
- Omit weekly totals (polarization, durability, TID 28d, TSB, CTL, ATL, ACWR, hours, TSS)
- Cite "per Section 11" or "according to the protocol"
- Omit any completed activity whose date falls on the report day (athlete local time). Every such activity gets its own session block — walks, ski-erg, short rides, aborted rides, commutes included.
- Merge multiple activities into a single block. One activity ID, one block.
- Invent explanations for anomalous sessions (very short duration, aborted, equipment issue). Report what the data shows. If context is needed, use only the activity's `description` or `chat_notes` fields. If neither explains it, include the block and, if relevant, note the anomaly plainly in the interpretation without speculating about cause.

Elaborate only when thresholds are breached or athlete requests deeper analysis.

---

### 6. Recommendation Formatting

Present actionable guidance in concise, prioritized lists (3–5 items maximum).

Each recommendation must be specific, measurable, and data-linked:
- "Maintain ≥70% Z1–Z2 time this week."
- "If RI < 0.7 for 3+ consecutive days, shift next 3 sessions to recovery emphasis."
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
| ACWR                         | 0.8–1.3                                            | ≥ 1.3 (edge of optimal)           | ≥ 1.35 (above optimal)             | High-side only for readiness/overload. Low-side (<0.8) is load-state context (undertraining/taper), surfaced via acwr_interpretation. Persistence: ≥ 1.3 for 3+ days → alarm |
| Monotony                     | < 2.5                                              | At 2.3                             | At 2.5                              | See Monotony Deload Context below                                   |
| Strain                       | < 3500                                             | —                                  | > 3500                              | Cumulative stress                                                   |
| Recovery Index (RI)          | ≥ 0.8 good / 0.6–0.79 moderate / < 0.6 deload      | < 0.7 for 2+ days                 | < 0.7 for 3+ days → deload review; < 0.6 → immediate deload | Readiness indicator. Single-day dips 0.6–0.79 are context, not amber. |
| HRV                          | Within personal baseline                           | ↓ > 20% vs baseline               | Persists > 2 days                   | Use 7-day rolling baseline                                          |
| RHR                          | Within personal baseline                           | ↑ ≥ 5 bpm vs baseline             | Persists > 2 days                   | Use 7-day rolling baseline                                          |
| Fatigue Trend                | −0.2 to +0.2                                       | —                                  | —                                   | ΔATL − ΔCTL (stable range)                                          |
| Easy Time Ratio              | 0.75–0.9                                           | —                                  | —                                   | ~80/20 distribution                                                 |
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
3. **Tertiary:** Subjective markers (RPE, athlete-reported state)

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
| Feel ≥ 4/5 (wellness, if available)   | Adjust volume 30–40% for 3–4 days |

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
- If RI < 0.7 for 2+ consecutive days → flag for monitoring (early warning)
- If RI < 0.7 for 3+ consecutive days → trigger block-level deload or load-modulation review
- If RI < 0.6 → immediate deload required regardless of duration

AI systems must only consider caloric-reduction or weight-optimization phases during readiness-positive windows (DI ≥ 0.95, HR drift ≤ 3 %, RI ≥ 0.8), referencing Section 8 — Weight Adjustment Control.

---

### Readiness Decision (v11.13)

`sync.py` v3.72+ pre-computes a deterministic `readiness_decision` object using a priority ladder. AI coaches read this as the baseline go/modify/skip recommendation. The AI writes the coaching note and can override with explicit explanation, but the default decision is auditable and reproducible across LLMs.

**Priority Ladder (first match wins):**

| Priority | Condition | Result |
|----------|-----------|--------|
| **P0 — Safety stop** | RI < 0.6, OR any tier-1 alarm active | **Skip** (non-negotiable) |
| **P1 — Acute overload** | ACWR ≥ 1.5, OR (TSB < -30 + HRV ↓>10%), OR (RI < 0.7 + tier-1 alert persisting ≥2 days) | **Skip** |
| **P1 — Acute overload (modify)** | ACWR ≥ 1.3, OR (TSB < -25 + HRV ↓>10%) | **Modify** |
| **P2 — Accumulated fatigue** | Red signal count ≥ 2, OR (1 red in tightened phase), OR amber count ≥ phase threshold | **Modify** (or Skip if 2+ red) |
| **P3 — Green light** | None of the above | **Go** |

**Signal Classification:**

| Signal | Green | Amber | Red |
|--------|-------|-------|-----|
| HRV | Within ±10% of 7d baseline | ↓ 10–20% | ↓ >20% |
| RHR | At or below baseline | ↑ 3–4 bpm | ↑ ≥5 bpm |
| Sleep | ≥ 7h | 5–7h | < 5h |
| TSB | > phase threshold (default -15) | Between threshold and -30 | < -30 |
| ACWR | < 1.3 | ≥ 1.3 and < 1.5 | ≥ 1.5 |
| RI | ≥ 0.7, or single-day 0.6–0.69 | < 0.7 for 2+ consecutive days | < 0.6 |

Missing signals are classified as `unavailable` and excluded from amber/red counts.

**Heuristic notes (transparency):**
- **Low-side ACWR is intentionally excluded from readiness ambers.** An ACWR < 0.8 indicates reduced recent load relative to chronic fitness (taper, detraining, or simply an off-rhythm week) — it is a load-state/context signal, not a fatigue or overload signal. Using it as a readiness penalty conflates "did little recently" with "can't handle much today," which are near-opposite states. Low-side context still surfaces via `derived_metrics.acwr_interpretation` ("undertraining") for the AI layer to read as context, but it no longer contributes to amber counts or overload alerts.
- **RI amber requires 2-day persistence** (`ri < 0.7` today AND yesterday) to filter single-night noise from a composite signal built on HRV and RHR. Single-day dips in the 0.6–0.7 band remain visible via the reported value but do not trigger an amber. Red (`ri < 0.6`) still fires on any single day — deload review is warranted regardless of persistence.

**Feel/RPE Override:**
Athlete-reported state (wellness Feel, activity RPE, or direct communication) can adjust the readiness_decision in either direction:

- **Escalate** (Go → Modify, Modify → Skip): Unconditional. If the athlete reports feeling worse than automated signals indicate, honor it. Safety-first.
- **De-escalate** (Modify → Go): Permitted at P2 only, under these conditions:
  - The athlete explicitly attributes signal deviation to non-training factors (e.g., sleep tracker error, caffeine, warm room)
  - No more than 2 signals are amber. If 3+ signals agree on fatigue, the data outweighs subjective override — the athlete may be underreporting
  - AI must note the override and the athlete's stated reason in the coaching note
- **P0 and P1 are not overridable.** Safety stops and acute overload conditions reflect compounding physiological signals, not single-sensor noise.

Athletes can underreport fatigue — through ego, denial, or simply poor interoception. When multiple objective signals converge on fatigue and Feel contradicts them, the AI should flag the disagreement and recommend caution rather than accept the de-escalation.

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
- Feel ≥ 4/5 (wellness, if available)
- Performance decline

A negative TSB is the mechanism of adaptation, not a warning signal.

---

### Success & Progression Triggers

In addition to recovery-based deload conditions, AI systems must detect readiness for safe workload, intensity, or interval progression ("green-light" criteria).

#### Readiness Thresholds (All Available Must Be Met)

| **Metric**            | **Threshold**                           |
|-----------------------|-----------------------------------------|
| Durability Index (DI) | ≥ 0.97 for ≥ 3 long rides (≥ 2 h)       |
| HR Drift              | < 3% during aerobic durability sessions |
| Recovery Index (RI)   | ≥ 0.85 (7-day rolling mean)             |
| ACWR                  | Within 0.8–1.3                          |
| Monotony              | < 2.5                                   |
| Feel (if available)   | ≤ 3/5 (no systemic fatigue)             |

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

See **Environmental Conditions Protocol** for temperature-based session modification rules and acclimatization guidance.

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
- Maintain normal Z2 endurance unless global readiness metrics also indicate systemic fatigue (RI < 0.7 for 3+ days, HRV ↓ > 20%)

---

### Recovery Metrics Integration (HRV / RHR / Sleep / Feel)

**Purpose:** Provide a deterministic readiness validation layer linking daily recovery data to training adaptation.

**Key Variables:**
- HRV (ms): 7-day rolling baseline comparison
- RHR (bpm): 7-day rolling baseline comparison
- Sleep Hours: Objective duration. Classified as readiness signal (Green ≥ 7h, Amber 5–7h, Red < 5h)
- Sleep Quality / Sleep Score: Excluded from readiness classification (v11.21). These are device-derived composites of HRV + HR during sleep — signals already captured independently. Downstream impact of poor sleep surfaces in HRV and RHR. Quality/score remain in wellness data as coaching context.
- Feel (1–5): Manual subjective entry (1=Strong, 2=Good, 3=Normal, 4=Poor, 5=Weak)

**Extended Wellness Fields (v3.85+):** sync.py passes through all Intervals.icu wellness fields — subjective state (stress, mood, motivation, injury, fatigue, soreness, hydration), vitals (spO2, blood glucose, blood pressure, Baevsky SI, lactate, respiration), body composition (body fat, abdomen), nutrition (kcal, carbs, protein, fat), lifestyle (steps, hydration volume), and cycle tracking (menstrual phase). All categorical fields use a 1→4 positional scale where **1 = best state, 4 = worst state**. Per-field labels are in `wellness_field_scales` in READ_THIS_FIRST. Fields are null when not reported. These are coaching context — none are wired into the automated readiness_decision pipeline.

**Feel/RPE exists at three levels — usage differs by layer:**

| Layer | Source | When to use |
|-------|--------|-------------|
| Wellness Feel (1–5) | Daily wellness entry | Use when present in data. If absent: solicit only when other wellness signals are ambiguous and Feel would change the decision. |
| Activity Feel/RPE | Per-activity rating (post-session) | Use when present in activity data. If absent: solicit after key sessions or when compliance assessment is borderline. |
| In-session RPE | Real-time during workout | Athlete-volunteered mid-session. Drives bail-out and intensity adjustment rules (Section 9). |

Feel/RPE is not wired into the automated readiness_decision pipeline. It enriches coaching decisions when available and is solicited when decision-relevant — never required as routine input.

**Decision Logic:**
- HRV ↓ > 20% vs baseline → Active recovery / easy spin
- RHR ↑ ≥ 5 bpm vs baseline → Fatigue / illness flag

The following thresholds apply to wellness-level Feel. If Feel is present in the data, use it. If absent and other signals are ambiguous, solicit it. If absent and the picture is clear, do not ask.

- Feel ≥ 4 → Treat as low readiness; monitor for compounding fatigue  
- Feel ≥ 4 + 1 trigger (HRV, RHR, or Sleep deviation) → Insert 1–2 days of Z1-only training
- 1 trigger persisting ≥2 days → Insert 1–2 days of Z1-only training
- ≥ 2 triggers → Auto-deload (−30–40% volume × 3–4 days)

**Integration:**
Daily metrics synchronised through data hierarchy and mirrored in JSON dataset each morning. AI-coach systems must reference latest values before prescribing or validating any session.

---

### Environmental Conditions Protocol

**Purpose:** Provide data-driven environmental training modification rules when athletes exercise in heat stress conditions. No `sync.py` changes — the AI layer interprets existing temperature and humidity fields (`avg_temp`, `humidity`, `weather`, `wind_speed` per activity) and fetched forecast data.

#### Heat Stress Assessment

Heat stress is **relative to the athlete's recent thermal exposure**, not absolute temperature. A rider acclimatized to 30°C in Valencia experiences different physiological strain at 33°C than a rider emerging from a Danish winter at 8°C.

**Thermal Baseline:** Rolling mean `avg_temp` from qualifying outdoor activities over the most recent 14 days. Indoor activities and activities without temperature data are excluded. The 14-day window aligns with the heat acclimatization timeline — physiological adaptation is ~75% complete within 7 days and fully established at 10–14 days (Périard et al. 2015). A longer window would dilute recent climate transitions.

**Heat Stress Tiers (delta-based):**

| Tier | Delta Above Baseline | Modification Level | Expected Cardiac Drift |
|------|---------------------|--------------------|----------------------|
| Tier 1 — Moderate | +5–8°C above 14d baseline | Awareness; hydration emphasis | 5–10% HR elevation at same power *(estimated, extrapolated from literature)* |
| Tier 2 — High | +8–12°C above 14d baseline | Active session modification | 10–15%+ HR elevation at same power *(Racinais et al. 2015: −0.5%/°C power decrement)* |
| Tier 3 — Extreme | +12°C+ above 14d baseline | Endurance only or reschedule | 15–20%+ HR elevation *(study range: 13–19% at 35°C/60% VO₂max)* |

**Absolute guardrails:**
- **Floor:** No heat stress flag below 15°C apparent temperature, regardless of delta. Cold-to-mild transitions are not heat events.
- **Ceiling:** Above 38°C apparent temperature, all athletes are Tier 3 regardless of acclimatization status or baseline.

**Insufficient baseline fallback:** When fewer than 3 qualifying outdoor activities exist in the 14-day window, the delta calculation cannot produce a reliable baseline. Fall back to absolute thresholds based on thermoneutral reference (~15–20°C from the literature):

| Apparent Temp | Fallback Tier |
|---------------|---------------|
| 25–30°C | Tier 1 minimum |
| 30–35°C | Tier 2 |
| >35°C | Tier 3 |

These absolute thresholds are conservative — they assume no acclimatization, which is correct for an athlete emerging from indoor training. Once 3+ outdoor activities accumulate in the 14-day window, the delta system takes over.

**Tier boundary honesty:** The delta breakpoints (+5–8, +8–12, +12+) are practical heuristics informed by the acclimatization and performance decrement literature, not directly cited thresholds from a single study. The underlying science establishes that acclimatization status determines heat tolerance (Périard et al. 2015, Racinais et al. 2015) and that performance decrements scale at approximately −0.5% per °C (Racinais et al. 2015). The specific tier cutoffs are engineering applied to that evidence.

**Apparent temperature hierarchy:** Use the best available measurement, in order:
1. WBGT (Wet Bulb Globe Temperature) — gold standard, requires specialized equipment, rarely available
2. Heat index (air temperature + relative humidity; Steadman 1979) — practical field standard, computed by the AI from `avg_temp` and `humidity` when both are present
3. Raw air temperature — when humidity is unavailable, shift tier boundaries down by ~2°C to compensate for unknown humidity contribution

When humidity is available, use it. When it's not, work without it. Consistent with Section 11's general data philosophy.

**Temperature trend detection:** The AI should detect thermal transitions by comparing recent `avg_temp` values against the 14-day baseline in `history.json`. Key transition scenarios:
- First week of outdoor riding after winter indoor training
- Sudden heatwave (multi-day temperature spike above baseline)
- Travel to a warmer climate (training camp, race travel)
- Return from warm climate to cool (acclimatization decay — see below)

These transitions represent the highest-risk periods for heat-related performance problems and should trigger proactive coaching notes.

#### Performance Expectations in Heat

Quantified decrements so the AI does not flag normal heat-related performance changes as underperformance or fitness regression:

| Condition | Expected Decrement | Source |
|-----------|-------------------|--------|
| Cycling 30-min TT at 32°C vs 23°C | −6.5% power output (345W → 323W) | Tatterson et al. (2000) |
| Cycling 20km TT at 35°C vs 15°C | −6.3% power output | Tucker et al. (2004) |
| Cycling TT, unacclimatized, first heat exposure | Up to −16% power output | Racinais et al. (2015) |
| Scaling per degree | ~−0.5% per °C above thermoneutral | Racinais et al. (2015) |
| Gross efficiency in heat | −0.9% (accounts for ~half of TT performance loss) | Hettinga et al. (2007) |
| Marathon at WBGT 25°C, elite runners | ~3% slower | Ely et al. (2007) |
| Marathon at WBGT 25°C, 3-hour runners | ~12% slower | Ely et al. (2007) |
| Optimal endurance performance temperature | 10–15°C air temp / 7.5–15°C WBGT | Ely et al. (2007); multiple |

**Anticipatory pacing in heat:** Tatterson et al. (2000) demonstrated that power reduction in heat is *anticipatory* — athletes self-select lower output before core temperature rises significantly. Rectal temperature was similar between hot and cool trials despite substantial power differences. This is the body's protective thermoregulatory mechanism operating correctly. The AI must not interpret heat-related power drops as "athlete didn't try hard enough" or "pacing failure."

**Athlete ability matters:** Slower/less fit athletes experience larger heat-related performance decrements than elites (Ely et al. 2007). Section 11 serves a range of athletes — the AI should scale expectations accordingly and avoid applying elite-derived benchmarks to recreational athletes.

#### Session-Type Modification Rules

Heat does not require a binary switch from power-primary to HR-primary intensity guidance. The correct approach is **session-type dependent**. The principle: **HR is the safety ceiling, power is the training stimulus. Heat lowers the ceiling, which constrains achievable volume. The primary lever is volume reduction, not intensity reduction.**

**Endurance / Z2 sessions:** HR ceiling approach. Cap HR at the athlete's normal Z2 ceiling and let power float downward. The aerobic stimulus is preserved because systemic cardiovascular stress — not muscular power output — is the actual target at this intensity. If power drops >15% below normal Z2 power while maintaining the HR ceiling, the session is still achieving its physiological goal.

**Threshold / Sweetspot intervals:** Keep power targets. 260W stimulates the same muscular adaptations regardless of ambient temperature. Accept higher HR at the same power output. The primary adjustment lever is **volume reduction**: fewer intervals (e.g. 3×8min instead of 4×8min), not lower interval power. Reducing interval power to control HR defeats the session's purpose — the muscular stimulus is the point. If HR reaches threshold-level values during sub-threshold work, that is an abort signal — end the session or extend recovery between intervals significantly.

**VO₂max / short intervals (30/15s, 30/30s, Tabata-style):** Heat drift is negligible in efforts ≤30 seconds. Keep power targets unchanged. If accumulated heat stress builds across the session (evidenced by rising baseline HR between work bouts or RPE creep at constant power), cut a set rather than reducing interval intensity. Recovery intervals between sets may need extension.

**Long rides (3h+):** Power is more reliable than HR for pacing. As core temperature rises progressively over hours, HR keeps climbing at constant effort — making HR an increasingly unreliable pacing guide. Use power for pacing. HR functions as an **abort signal**: if HR reaches threshold-level at endurance power, the ride must stop or intensity must drop to recovery level. This is a safety boundary, not a pacing tool.

**Summary table:**

| Session Type | Power Targets | HR Role | Primary Adjustment |
|-------------|---------------|---------|-------------------|
| Endurance / Z2 | Float down | Ceiling (cap at Z2 HR) | Power reduction accepted |
| Threshold / SS intervals | Keep | Monitor (accept elevation) | Cut volume (fewer intervals) |
| VO₂max / short intervals | Keep | Monitor between sets | Cut sets if baseline HR rising |
| Long rides (3h+) | Keep for pacing | Abort signal only | Stop or drop to recovery if HR at threshold |

#### Heat Acclimatization

Evidence-based adaptation timeline for athletes entering heat:

**Adaptation kinetics (Périard et al. 2015; Racinais et al. 2015 consensus):**
- Days 1–3: Plasma volume expansion begins, initial HR reduction
- Days 3–6: Cardiovascular adaptations measurable (reduced exercising HR, improved cardiac output stability)
- Days 5–7: ~75% of major physiological adaptations achieved
- Days 5–14: Sweat rate increases, thermoregulatory improvements, sweat electrolyte concentration decreases
- Days 10–14: Full adaptation, including complete sweating and skin blood flow responses

**Protocol for entering heat:**
- Sessions ≥60 minutes per day in heat, sufficient to elevate core and skin temperature and stimulate sweating (Racinais et al. 2015 consensus)
- Does not require high intensity — Z2 endurance in heat provides adequate thermal stimulus
- First 3–5 days: Do not schedule quality sessions (threshold, VO₂max). Prioritize endurance work to build heat tolerance without compounding muscular fatigue
- First week: Reduce training volume 25–40% relative to temperate training load
- Days 5–7 onward: Gradually reintroduce structured intensity
- Days 10–14: Full training load in heat
- Consistent with Section 9, *3 Metabolic & Environmental Progression: only one progression variable modified per week. Do not combine first heat exposure with altitude training, fasted sessions, or a volume increase

**Acclimatization decay:**
- Adaptations begin declining within days of returning to temperate conditions
- Significant decay after approximately 1 week without heat exposure
- Scenario: athlete returns from a 10-day warm-weather training camp to cool home conditions. The AI should note that heat tolerance is fading, which is relevant if a warm-weather event is upcoming. Intermittent heat exposure (e.g. indoor heat sessions) can slow decay
- Decay is relevant even in the "positive" direction — an athlete acclimatized to heat who races in cool conditions may experience perceived ease due to reduced thermoregulatory demand. This is expected, not a sign of sudden fitness improvement

**Altitude + heat:** Training camps at altitude in warm locations (Mallorca, Tenerife, Gran Canaria) combine two environmental stressors. Per Section 9, *3 progression rules: one variable at a time. If both are present simultaneously, prioritize heat acclimatization (more immediate health risk) and accept reduced training quality for the altitude adaptation.

#### Indoor Heat

Indoor training without adequate cooling is likely the most common heat stress scenario for Section 11 users. A garage, apartment, or pain cave without air conditioning and limited airflow can produce heat stress conditions at temperatures that would be comfortable outdoors.

**Why indoor heat is different:** Outdoor cycling at 25+ km/h generates substantial convective cooling (airflow over the skin). Indoor training on a stationary trainer eliminates this. Additionally, humidity builds in enclosed spaces as the athlete sweats, compounding the thermal load. A 28°C indoor environment with no fan produces greater physiological strain than 30°C outdoors on the bike.

**Fan as primary mitigation:** Research consistently shows that fan airflow (~4.5 m/s) significantly attenuates cardiovascular drift during indoor exercise. A strong fan directed at the torso is the single most effective indoor heat countermeasure. This is a practical coaching recommendation, not a protocol prescription.

**Session modification:** The same session-type rules in the previous subsection apply to indoor heat. The AI uses `avg_temp` from the activity payload (indoor rides record temperature via device sensors or room sensors) to assess post-ride heat context. When `avg_temp` exceeds 25°C on an indoor activity, the AI should factor heat stress into its interpretation of power, HR, decoupling, and RPE data.

**"Move indoors" is not always a heat mitigation.** The pre-workout template guidance should not default to "consider moving indoors" as a heat avoidance strategy without considering whether the indoor environment is actually cooler. The recommendation should be: move to a **cooler** environment, which may be indoors with AC/fan or outdoors at a cooler time of day.

#### Cardiac Drift and Decoupling in Heat

The existing diagnostic logic in Durability Sub-Metrics states: "Normal Endurance Decay + High HR–Power Decoupling → Cardiovascular drift; assess hydration, heat, or aerobic base fitness." This section provides the concrete interpretation rules for the heat component.

**When `avg_temp` + `humidity` indicate heat stress (Tier 1+):**
- Elevated HR–Power decoupling is *expected*. Do not flag as a fitness concern, aerobic base regression, or durability decline
- Do not recommend additional recovery or load reduction based solely on heat-elevated decoupling
- Post-ride interpretation should explicitly attribute elevated decoupling to temperature when data supports it: "Decoupling was 7.2% — elevated, but consistent with the 31°C conditions. Not a durability concern."

**Cardiac drift magnitude by tier** *(estimated ranges — see tier boundary honesty note above)*:

| Tier | Expected HR Elevation at Same Power | Expected Power Reduction at Same HR |
|------|-------------------------------------|-------------------------------------|
| Tier 1 | 5–10% | 3–5% |
| Tier 2 | 10–15%+ | 5–10% |
| Tier 3 | 15–20%+ | 10–16% |

**Seasonal pattern:** Aggregate Durability trends will show apparent "decline" during seasonal warming (spring/summer transition) across the athlete's history. This is a temperature artifact, not a fitness change. The AI must contextualize durability trends with `avg_temp` data from the same period. A rising durability trend during summer is more meaningful than one during winter (it's working against the temperature headwind). A declining trend during the same temperature conditions is genuinely concerning; a declining trend coinciding with a +10°C seasonal shift is expected.

**Interaction with Aggregate Durability metric:** The 90-minute floor and VI ≤ 1.05 session filter for the Aggregate Durability metric remain unchanged. However, when qualifying sessions occur during heat stress conditions, the AI should weight their decoupling values with temperature context rather than treating them as equivalent to thermoneutral sessions. The protocol does not prescribe a mathematical temperature correction — this is an interpretation guidance, not a formula.

#### Cold Weather

Cold weather is a minor environmental modifier. It does not require tiers, session-type modification tables, or acclimatization protocols.

**Extended warm-up below ~5°C:** Muscles are less pliable and power output is reduced until core and peripheral temperature rise. Extend warm-up by 5–10 minutes. Do not evaluate early-session power against targets.

**Bronchospasm risk below ~0°C:** Exercise-induced bronchoconstriction (EIB) is more common in sub-zero air, with higher prevalence in endurance athletes exposed to cold/dry air at high ventilation rates (Rundell et al. 2004, 2013). Flag VO₂max and hard interval sessions below 0°C — consider moving indoors or reducing intensity to avoid sustained high ventilation rates in freezing air.

**Wind chill on long outdoor rides:** Descents, stops, and mechanicals create hypothermia risk when wet and exposed to wind. This is a safety note, not a training modification — the AI should flag it in pre-workout weather coach notes when conditions warrant.

**Power may read low for first 10–15 minutes:** Cold affects both the rider (reduced muscle efficiency) and some power meters (temperature compensation lag). Do not interpret early-ride power shortfall as underperformance.

**No session-type modification rules.** Once warmed up, training proceeds normally in cold. The session itself doesn't change — just the preparation and safety awareness.

#### Environmental Conditions — Evidence Base

| Reference | Finding | Section 11 Application |
|-----------|---------|----------------------|
| Tatterson et al. (2000) | 6.5% power reduction at 32°C vs 23°C in elite cyclists; reduction is anticipatory, not core-temp driven | Expected power discount in heat; do not interpret as underperformance |
| Tucker et al. (2004) | ~6.3% power reduction at 35°C vs 15°C in 20km cycling TT | Corroborates ~0.5% per °C power decrement scaling |
| Racinais et al. (2015) Med Sci Sports Exerc | −16% power unacclimatized first exposure, ~−0.5%/°C; largely restored after 2-week acclimatization | First heat exposures are worst; acclimatization restores most performance |
| Racinais et al. (2015) Scand J Med Sci Sports — Consensus | Heat acclimatization: 1–2 weeks, ≥60 min/day, must elevate core/skin temp and stimulate sweating | Acclimatization protocol and timeline |
| Périard et al. (2015) | ~75% of heat adaptations within 7 days; full at 10–14 days; CV adaptations 3–6 days; sweat adaptations 5–14 days | Concrete adaptation timeline; supports 14-day baseline window |
| Hettinga et al. (2007) | Gross efficiency drops ~0.9% in 35°C vs 15°C; accounts for approximately half of TT performance loss | Metabolic cost of thermoregulation beyond cardiac drift alone |
| Ely et al. (2007) | Marathon performance slows progressively above WBGT 5–10°C; slower athletes affected disproportionately | Range-of-ability consideration; scale expectations to athlete level |
| Steadman (1979) | Heat index formula combining air temperature and relative humidity | Practical alternative to WBGT for field-based heat assessment |
| Racinais et al. (2023) Br J Sports Med — IOC consensus | Updated IOC recommendations on event regulations in heat; WBGT-based risk classification | Environmental risk classification framework |
| Montain & Coyle (1992) | Dehydration exacerbates thermal and cardiovascular strain during exercise in heat | Hydration as heat stress modifier |
| Maunder et al. (2020) | At moderate heat stress (34–35°C), increased carbohydrate oxidation at higher intensities | Glycogen depletes faster in heat; adjust nutrition frequency in Tier 1+ conditions |
| Rundell et al. (2004, 2013) | Higher prevalence of airway hyperresponsiveness and EIB in athletes training in cold/dry air at high ventilation rates; repeated exposure causes airway damage | Flag high-intensity sessions below 0°C; cold weather bronchospasm risk |

---

### Route & Terrain Protocol

When `routes.json` contains terrain data for a planned event (`has_terrain: true` on the event in `latest.json`), the AI has access to the full route profile — distance, elevation, climbs, descents, gradients at 500m resolution, and GPS coordinates. This section defines how to interpret that data and apply it to coaching decisions: pacing, effort distribution, nutrition timing, segment targeting, and pre-ride briefing.

Route intelligence applies to any coaching conversation where terrain is known — race preparation, pre-ride planning, session context, or block-level event previewing. It is not limited to race day.

#### Route Analysis

**`routes.json` structure:** Each event with a GPX/TCX attachment produces a `terrain_summary` containing: `total_distance_km`, `total_elevation_m`, `elevation_per_km`, `course_character`, `climbs` array, `descents` array, and `polyline` (GPS track downsampled at 500m intervals with elevation).

**Course character** classifies the overall route profile using elevation density (m/km). Total elevation alone is distance-blind — 2000m over 300 km is rolling, not hilly. Section 11 convention:

| Classification | Criteria |
|---|---|
| flat | <5 m/km |
| rolling | ≥5 m/km |
| hilly | ≥20 m/km, OR has Cat 2 / Cat 1 / HC climb |
| mountain | ≥30 m/km |

Climb category presence upgrades classification — a route with a Cat 1 climb is `hilly` regardless of elevation density. A route with ≥30 m/km is `mountain` even without a single long categorized climb (catches routes with many short steep pitches).

**Climb classification** follows conventional UCI/Tour-derived categories based on elevation gain:

| Category | Elevation Gain | Character |
|---|---|---|
| Cat 4 | 100–200m | Short or gentle climb |
| Cat 3 | 200–400m | Moderate climb |
| Cat 2 | 400–650m | Significant sustained climb |
| Cat 1 | 650–1000m | Major climb |
| HC | 1000m+ | Extreme climb |

These are elevation-based conventions, not gradient-based. A 150m gain at 10% average is physiologically harder than 200m at 4% — the category captures scale, not intensity. The AI should communicate both category and gradient when briefing climbs. Climbs below 100m elevation gain with <3% average gradient are filtered out as terrain noise.

**Climb detail fields:** Each climb entry includes `position_km` (distance from start), `distance_km`, `elevation_m`, `avg_gradient_pct`, `max_gradient_pct` (steepest 200m subsection), `category`, and `start_coords`/`end_coords`. Use `max_gradient_pct` to warn about steep sections within an otherwise moderate climb — "averages 5.8% but kicks to 11.2% in the final kilometer."

**Descents as recovery windows:** Descents are not just terrain features — they are tactical recovery and fueling opportunities. Each descent entry includes the same positional and gradient fields. The AI should frame descents relative to the efforts around them: "4.2 km descent after the Cat 2 — eat, drink, recover before the rolling section."

**Polyline:** The `polyline` array provides `[km, lat, lon, elevation]` at every 500m of road distance, plus start and end points. This gives the AI gradient context at any point on the route — not just within detected climbs and descents. Use for: identifying false flats between climbs, spotting gradual elevation trends that don't trigger climb detection, and providing gradient-aware pacing guidance across the full course.

#### Terrain-Adjusted Power Estimation

Constant power on a variable-gradient course is not optimal. Research consistently shows that increasing power on climbs and decreasing it on descents — bounded variability — produces faster finishing times at the same physiological cost.

**Variable power pacing by gradient:**

The time savings from increasing power are disproportionately large on climbs and negligible on fast descents, because aerodynamic drag scales cubically with speed while gravitational resistance scales linearly with gradient:

- On a 6% grade, a 5% power increase above flat baseline saves approximately 78 seconds per 2.5 km (Atkinson & Brunskill, 2000).
- On a 1% grade, the same 5% increase saves only 16 seconds per 2.5 km.
- On descents above approximately 60 km/h, additional power provides diminishing returns — aerodynamic position matters more than watts.
- As a practical guideline, increase power 10–20% above flat baseline on climbs, scaling approximately 3–5% per 1% of gradient. Reduce power on descents — the time cost of soft-pedaling downhill is minimal.
- Comparative modeling confirms the effect: at identical average power of 300W, a variable strategy (285W flat / 325W climbing) beat constant 300W by 30 seconds over a 20 km TT with a 7% grade finish (2PEAK).
- Finite element optimization modeling showed 0.45–2.84% overall time improvement from variable vs constant power pacing (Boswell, 2025).

**Connecting to sustainability_profile:** The `capability.sustainability_profile` provides what the athlete can sustain at race-relevant durations. Apply gradient adjustments on top of these ceilings — not on top of FTP directly. For a climb estimated at 20 minutes, reference the athlete's 20-minute sustainability data, then adjust for gradient. If the climb's average gradient is 6%, the target power is 10–18% above the athlete's flat sustainable power for that duration — but capped at the athlete's actual observed MMP for that duration.

**Progressive target adjustment:** Effective threshold power decreases with accumulated work. After 2 hours at moderate intensity, power at the moderate-to-heavy transition drops approximately 10% (Maunder et al., 2022). In Five Monuments analysis, top-5 finishers maintained stable power beyond 60 kJ/kg of accumulated work while finishers 6th–30th showed significant declines (Leo et al., 2023/2025). The AI should reduce sustainable power targets by approximately 5% per hour after the first 2 hours, calibrated against the athlete's individual durability baseline from `durability_7d_mean` and `durability_28d_mean`. A climb at km 120 does not get the same target as the same gradient at km 30.

**Reduction rate honesty:** The ~5% per hour linear guideline is a practical heuristic informed by the Maunder (~10% at 2h) and Leo (durability decay beyond 60 kJ/kg) findings, not a directly cited threshold from a single study. Actual decay rates vary by athlete — the individual `durability_7d_mean` and `durability_28d_mean` baselines are the calibration signal. The heuristic provides a starting point when individual data is sparse.

**Fast starts are costly.** Exceeding planned power by more than 5% in the opening minutes consistently produces significantly worse overall finishing times in events over 30 minutes. The direction is well-established in pacing literature; specific magnitude varies by event duration and overcooking severity. The AI should flag early overcooking, not just late fading.

#### Wind Overlay

Wind direction and speed from weather data, matched against route bearing, determines headwind/tailwind assessment at any point on the course.

**Convention:** Meteorological wind direction is the direction wind comes FROM (0° = north, 90° = east). Segment or route bearing is the direction the athlete RIDES (standard geographic bearing). When wind direction equals route bearing, the athlete rides directly into the wind — headwind.

**Headwind/tailwind classification:**

```
angle_diff = abs(route_bearing - wind_direction)
if angle_diff > 180:
    angle_diff = 360 - angle_diff

if angle_diff < 45:       → headwind
elif angle_diff < 135:    → crosswind
else:                     → tailwind
```

Route bearing can be computed from consecutive polyline points for any section of the course. A route that goes north for 40 km then returns south has opposite wind effects on each leg.

**Wind impact by gradient tier:**

Wind impact is proportional to the athlete's speed, because aerodynamic drag scales with velocity cubed. On steep climbs, speed is low and gravity dominates — wind is a minor factor. On flat terrain, speed is high and aero drag dominates — wind is the primary external variable.

| Gradient | Speed regime | Wind impact | Coaching implication |
|---|---|---|---|
| Flat (<3%) | High (35+ km/h) | Dominant factor | Headwind substantially increases power cost at speed. Reduce speed target, not overcook effort. Tailwind = free speed |
| Moderate climb (3–6%) | Medium (15–25 km/h) | Secondary factor | Headwind adds cost but gradient is primary. Tailwind helps but don't oversell it |
| Steep climb (>6%) | Low (<15 km/h) | Minimal | Aerodynamic drag is a small fraction of total resistance at climbing speeds. Don't mention wind on steep climbs |

The AI should not cite wind as a factor on steep climbs — it misleads the athlete about what's actually hard. On flat and rolling terrain, wind context is essential for pacing and effort budgeting.

#### Drafting Estimates

In group riding situations, drafting reduces aerodynamic drag significantly, but the benefit is position-dependent: second wheel sees roughly 5–10% drag reduction, while riders deep in a large peloton can see 40% or more (Blocken et al., 2018). The commonly cited ~30% is a mid-group average. This substantially lowers the power required to maintain a given speed on flat and rolling terrain. On steep climbs, drafting benefit diminishes as gravity becomes the dominant resistance force.

When the AI knows the athlete will be in a group (race, group ride, sportive), power estimates for flat and rolling sections should account for drafting. Solo breakaway or time trial efforts use undrafted power. The AI should not assume drafting unless the context confirms it — a solo training ride is undrafted regardless of course character.

#### Segment Reasoning (Strava Integration)

When the agentic platform has Strava API access, segment data enriches route intelligence. This is protocol for the AI layer — not pipeline automation in `sync.py`.

**Priority hierarchy:** Starred segments (from `/athlete/segments/starred`) that fall on today's route are automatic priority targets. The athlete may also name specific segments in conversation. All other segments found along the route via `/segments/explore` are opportunistic — mention if conditions are perfect, don't pre-brief.

**Feasibility assessment:** Cross-reference the segment's expected duration (estimated from distance and gradient) with the athlete's power curve from `capability.sustainability_profile`. If the athlete's MMP at the expected segment duration is within 5% of the estimated power requirement, it's a realistic target. If the gap exceeds 10–15%, the AI should say so directly — the segment is above the athlete's current capability at that point in the ride. Factor in position in the ride: a segment at km 80 after 1500m of climbing requires progressive durability adjustment (see Terrain-Adjusted Power Estimation above).

**Wind × bearing = attempt/skip:** Compute headwind/tailwind from segment bearing (start to end coordinates) vs wind direction. A tailwind on a climb segment is the best-case scenario. A headwind on a flat segment makes PRs unlikely and the effort disproportionately expensive. The AI should proactively recommend which segments have favorable conditions today and which to skip, with reasoning.

**Strava API endpoints (reference):**

| Endpoint | Purpose |
|---|---|
| `GET /segments/explore?bounds=...&activity_type=riding` | Find segments in bounding boxes along the route |
| `GET /segments/{id}` | Full segment detail including polyline |
| `GET /athlete/segments/starred` | Athlete's starred segments — automatic priorities |
| `GET /segment_efforts?segment_id={id}` | Athlete's effort history — PR context |

The AI does not call these endpoints directly from `sync.py`. They are available when the agentic platform has Strava OAuth access. Reasoning rules apply regardless of how segment data arrives — Strava API, athlete-provided segment IDs, or manual upload.

#### Nutrition Timing Relative to Terrain

Terrain structure dictates when the athlete can and cannot eat. Fueling during a steep climb is physiologically harder (high breathing rate, high effort) and mechanically awkward. Descents and flat sections are optimal fueling windows.

**Rules:**

- Fuel before climbs, not during them. Carbohydrates require 15–20 minutes to absorb (Jeukendrup, 2014). Cue nutrition 15–20 minutes before the effort, which on a hilly course often means fueling on the preceding flat or descent.
- Descents are the primary fueling opportunity on mountain and hilly courses. The athlete can eat and drink without effort cost. If a climb follows, the descent is the last comfortable fueling window.
- On flat and rolling courses, nutrition timing is less constrained — the athlete can fuel at any point. Follow standard kJ-based dosing: approximately 250–300 kJ between fuel cues as a backstop.
- The AI should connect terrain to the nutrition skeleton in a pre-ride briefing: "Eat at km 15 on the flat before the Cat 3. Next opportunity is the descent at km 35. Fuel again at km 52 before the Cat 2."

**kJ-Based Carbohydrate Dosing:**

The terrain rules above govern *when* to fuel. This table governs *how much*. Carbohydrate requirements scale with actual energy expenditure (kJ output), not fixed gram-per-hour targets. The AI computes kJ/hour from ride data and maps to the appropriate intake rate:

| kJ/hour Output | Carb Target (g/hour) | Typical Context |
|---|---|---|
| 400–500 | 50–60 | Endurance pace, recreational athlete |
| 600–800 | 75–100 | Hard training day, fit amateur |
| 800+ | 90–120 | Race intensity, requires gut training |

**Dosing convention honesty:** The kJ→carbs mapping is a practical guideline synthesized from Jeukendrup (2014) dose-response findings and CTS/Rutberg (2025) field recommendations, not a single directly cited table. The relationship is physiologically grounded — higher output burns more glycogen, requiring proportionally more exogenous carbohydrate — but the specific g/hour figures per kJ band are applied engineering.

**Absorption limits by carbohydrate type:**

| Carb Source | Max Absorption Rate | Mechanism |
|---|---|---|
| Single source (glucose only) | ~60 g/hour | Saturates SGLT1 transporter |
| Glucose + fructose (1:0.8 ratio) | ~90 g/hour | Dual transporters (SGLT1 + GLUT5) |
| Gut-trained elite athletes | Up to 120 g/hour | Trained absorption capacity (Hearris et al., 2022) |

The absorption ceiling constrains what's achievable regardless of expenditure rate. An athlete burning 900 kJ/hour who hasn't gut-trained above 60 g/hour cannot absorb 90 g/hour just because the dosing table says so. The AI should match intake recommendations to the athlete's trained absorption capacity when known (from dossier or conversation), and default to 60 g/hour single-source when unknown.

Absorption form does not matter — drinks, gels, and chews produce equivalent exogenous carbohydrate oxidation rates at matched doses (Hearris et al., 2022).

**Glycogen Budget Model:**

The body stores approximately 2,000 kcal of glycogen (liver + muscle combined). Due to human mechanical efficiency (~22.5%), the kJ-to-kcal relationship is approximately 1:1 — kilojoules of work measured by a power meter roughly equal kilocalories burned. This means `kj_total` (or `kcal` from the activity payload) is a direct proxy for energy expenditure.

The AI can estimate glycogen status for pre-ride planning and post-ride analysis:

- **Pre-ride:** Estimate total kJ for the planned ride (from duration × expected NP, or from route profile and sustainability data). Compare against glycogen stores + planned intake to verify the nutrition plan is sufficient. A 4-hour ride at 200W NP burns ~2,880 kJ — more than glycogen stores alone. Without fueling, the athlete bonks.
- **Post-ride:** Compare `kj_total` against estimated carbohydrate intake. If the deficit exceeds 1,500–1,800 kcal, the athlete was in or approaching bonk territory. Use this to explain performance collapse in the final hour.
- **Glycogen depletion compounds with heat:** At 34–35°C, carbohydrate oxidation increases at high intensities (Maunder et al., 2020). In heat stress conditions (Tier 1+), the AI should assume glycogen burns faster and adjust nutrition recommendations accordingly.

CHO ingestion during exercise does not spare muscle glycogen — it maintains blood glucose, which is the actual fatigue trigger (Coyle et al., 1986). Low blood glucose signals the brain to terminate exercise. The practical implication: fueling prevents the bonk by maintaining blood glucose, not by topping up glycogen stores mid-ride.

**Glycogen budget honesty:** The ~2,000 kcal glycogen figure and the kJ≈kcal equivalence are well-established in exercise physiology. The 1,500–1,800 kcal deficit threshold for bonk risk is a practical heuristic — individual glycogen stores vary by body mass, muscle fiber composition, and pre-ride carbohydrate loading status. Athletes who carb-load effectively (10–12 g/kg from D-4, per Section 11's event preparation section) start with higher stores.

**Temperature-Driven Hydration Frequency:**

| Condition | Reminder Frequency | Notes |
|---|---|---|
| Below 15°C | Every 30–40 minutes | Easy to forget in cold; still losing fluid |
| 15–20°C | Every 20–30 minutes | Thermoneutral; standard hydration |
| 20–30°C | Every 15–20 minutes | Increased sweat rate |
| Above 30°C | Every 10–15 minutes | Aggressive; dehydration exacerbates cardiac drift (Montain & Coyle, 1992) |

HR drift at stable power in heat is a dehydration signal — the AI should combine drink cues with cardiac drift observations when both are present. Cross-reference with the Environmental Conditions Protocol for heat stress tier assessment.

#### Weather Data Source

For pre-ride weather and wind data, yr.no (Norwegian Meteorological Institute) provides free, high-quality forecasts with wind direction, speed, temperature, and precipitation. No API key required for reasonable usage.

MyWindSock offers cycling-specific wind analysis overlaid on route files — parked as a future integration option. Currently protocol-only: the AI can reference wind data from any source the athlete or platform provides.

The AI cross-references temperature against the Environmental Conditions Protocol (see above) for heat stress tier assessment. Wind data feeds the wind overlay logic in this section. Do not duplicate heat/cold guidance here — reference the existing protocol.

#### Pre-Ride Briefing Flow

When route data is available, the AI can produce a structured pre-ride briefing as part of a coaching conversation or pre-workout report. This follows a logical sequence: understand the course → identify key efforts → check conditions → plan pacing → plan nutrition.

**Briefing structure:**

1. **Route summary** — distance, total climbing, course character, number of significant climbs, overall profile narrative ("hilly first half, flat return" or "steady Cat 2 followed by fast descent and rolling finish").

2. **Key climbs and terrain features** — for each categorized climb: position in ride, distance, average and maximum gradient, category. Frame descents as recovery windows between efforts. Note sustained flat sections where the athlete can settle into tempo.

3. **Segment opportunities** — when Strava segment data is available: priority segments with feasibility assessment, conditions-based attempt/skip recommendations, target power and pacing notes. Non-priority segments mentioned only if conditions are unusually favorable.

4. **Conditions assessment** — wind direction and speed matched against route sections and segment bearings. Temperature and heat stress tier (cross-reference Environmental Conditions Protocol). Precipitation if relevant. The value-add is connecting conditions to specific course features: "Tailwind for the Cat 3 at km 22 — favorable. Headwind on the exposed flat from km 45–60 — conserve."

5. **Pacing strategy** — effort distribution across the course. Variable power targets by gradient (see Terrain-Adjusted Power Estimation). Where to push, where to save. Progressive adjustment for long events. Early overcooking warning.

6. **Nutrition skeleton** — fueling timing anchored to terrain features. Pre-climb fueling windows, descent fueling opportunities, flat-section backstops. Connects kJ expenditure estimates to the route profile.

**Conditional inclusion in pre-workout reports:** When `has_terrain: true` on a planned event and `routes.json` contains the corresponding terrain data, the pre-workout report should include a condensed terrain context block after the planned workout section: course character, key climbs (condensed), and a pacing note. The full briefing is available on request. Do not include terrain context when `has_terrain` is false or absent — the data doesn't exist.

#### Route & Terrain — Evidence Base

| Reference | Finding | Section 11 Application |
|---|---|---|
| Atkinson & Brunskill (2000), via CTS | 5% power increase saves 78s on 6% grade vs 16s on 1% grade over 2.5 km | Variable power pacing: disproportionate time gain on climbs vs flats |
| 2PEAK pacing comparison | 285W flat / 325W climbing beat constant 300W by 30s over 20 km TT at identical average power | Confirms variable power superiority at same physiological cost |
| Boswell (2025), Springer Nature | Finite element optimization showed 0.45–2.84% time improvement from variable vs constant power | Quantifies variable power benefit range |
| Maunder et al. (2022), Eur J Appl Physiol | Power at moderate-to-heavy transition decreased ~10% after 2h cycling at 90% VT1 | Progressive target reduction for long events; cross-ref sustainability profile |
| Leo et al. (2023/2025) | Five Monuments top-5 vs 6th–30th: stable power beyond 60 kJ/kg vs significant decline | Durability as differentiator; calibrate targets to accumulated work |
| Blocken et al. (2018) | CFD analysis of peloton aerodynamics: position-dependent drag reduction from ~5–10% (second wheel) to 40%+ (deep in peloton) | Drafting estimate for group riding power calculations |
| Jeukendrup (2014) | Carbohydrate absorption requires 15–20 min; dose-response confirmed up to absorption ceiling; single source max ~60 g/h, dual source (glucose+fructose) ~90 g/h | Nutrition timing, absorption limits, kJ-based dosing foundation |
| Hearris et al. (2022) | Absorption rates identical across sports drinks, gels, and chews at 120 g/h; gut-trained athletes achieve higher oxidation rates | Absorption form doesn't matter; gut training extends ceiling |
| CTS / Rutberg (2025) | kJ-to-carb dosing table linking output (400–800+ kJ/h) to intake recommendations (50–120 g/h) for amateur through elite | kJ-based nutrition dosing by output level |
| Miura et al. (2000) | W′ reduced ~20% (12.83→10.33 kJ) by glycogen depletion; CP unaffected | Late-ride segment feasibility: W′-dependent efforts degraded by glycogen deficit |
| Coyle et al. (1986) | CHO ingestion maintains blood glucose (actual fatigue trigger), does not spare muscle glycogen | Fueling prevents bonk via blood glucose, not glycogen sparing |
| Springer Nature (2025) | Power response to wind is non-linear and velocity-dependent; headwind substantially increases power cost at speed | Wind impact scales with speed regime, not gradient directly |
| Climb classification | UCI/Tour conventional categories — elevation-based thresholds | Industry convention, not a single research finding |
| Course character heuristic | Section 11 convention — flat/rolling/hilly/mountain boundaries from elevation density (m/km) + climb presence | Engineering decision for route classification |

---

---

### DFA a1 Protocol

#### Overview

DFA a1 (Detrended Fluctuation Analysis, short-term scaling exponent α1) is a non-linear heart rate variability index that quantifies the fractal correlation properties of beat-to-beat intervals during exercise. As intensity rises, autonomic balance shifts and the RR-interval signal loses its long-range correlations — DFA a1 falls. This makes it a continuous, real-time marker of internal load that maps meaningfully to ventilatory/lactate thresholds.

**Required (hard prerequisites for DFA a1 features in Section 11):**
- **AlphaHRV** Connect IQ data field by Marco Altini (free, [Garmin Connect IQ store](https://apps.garmin.com/en-US/apps/40fd5e67-1ed0-457b-944b-19fdb3aae7e7))
- A **Garmin head unit** with Connect IQ data field support (Edge 530/540/830/840/1030/1040/1050, recent Forerunner / fenix / Epix)
- A **chest strap** that broadcasts beat-to-beat RR intervals (Garmin HRM-Pro Plus, Polar H10, similar)
- AlphaHRV added to a **visible data screen** on the active bike/run profile (Connect IQ fields don't run on screens that aren't rendered)
- "**Save ALPHA1 to FIT**" enabled in AlphaHRV settings (and a full Edge restart after toggling)
- **Direct Garmin → Intervals.icu sync**, not via Strava — Strava strips FIT developer fields and AlphaHRV's output never reaches Intervals.icu via that path

**Non-Garmin athletes:** see [`examples/dfa_a1/NON_GARMIN.md`](../examples/dfa_a1/NON_GARMIN.md) for the current status of Suunto, Hammerhead Karoo, Wahoo, Coros, Polar, and phone-based fallback paths. As of v11.30, **only Garmin + AlphaHRV is verified end-to-end**. Other paths are documented as investigational with verification commands ready for users on those platforms to run.

**Ingest path:** Direct Garmin Connect → Intervals.icu sync. AlphaHRV writes DFA a1 to the FIT file as a developer field. Intervals.icu ingests it natively and exposes it as a per-second `dfa_a1` stream plus per-interval `average_dfa_a1` field. `sync.py` reads both via the streams API and produces the per-session `dfa` block in `intervals.json`.

**Quality dependency:** AlphaHRV needs uncorrupted RR data. The watch/head-unit ANT+ link to the strap must be clean. Connect IQ data fields can only run when active in the recording profile, so the field must be installed AND added to a data screen for the activity profile.

#### Threshold Mapping

The published mapping from DFA a1 to physiological thresholds:

| DFA a1 value | Physiological state |
|---|---|
| > 1.0 | Below LT1 / aerobic threshold (true Z2, sustainable hours) |
| ≈ 1.0 | LT1 / VT1 / aerobic threshold |
| 0.75 | Mid-transition (upper Z2 / tempo / Sweet Spot lower bound) |
| ≈ 0.5 | LT2 / VT2 / anaerobic threshold |
| < 0.5 | Above LT2 (VO₂max work, supra-threshold) |

**This mapping is cycling-validated** (Rowlands et al. 2017, Gronwald et al. 2020, Schaffarczyk et al. 2023, Mateo-March et al. 2023). Other sports get rollups computed but `validated: false` is flagged in `dfa_a1_profile.trailing_by_sport.{sport}` — running has higher movement-induced HRV noise and different autonomic dynamics, and per-sport calibration is not yet established. Treat non-cycling DFA estimates as informational only.

**Important caveats:**
- Athlete-specific calibration is needed before DFA-derived thresholds replace dossier values. The protocol surfaces deltas; the human decides.
- Fatigue shifts the relationship — a fatigued athlete's DFA a1 is depressed at submaximal work, so a "low" reading mid-session may reflect accumulated fatigue rather than true threshold crossing.
- Heat, dehydration, and glycogen state all push DFA a1 down at constant external load. Cross-reference Environmental Conditions Protocol and nutrition state before interpreting low readings as fitness signal.

#### Pre-Computed Signals Available

The AI does not compute DFA a1 statistics — `sync.py` does. The AI reads pre-computed values from two locations:

**`intervals.json` per-activity `dfa` block** (see Interval Data Mirror section above for full schema). Contains: artifact-filtered avg + quartiles, 4-band TIZ split with HR/power cross-references per band, drift (first vs last third) with `interpretable` flag, LT1/LT2 crossing-band estimates (`avg_hr`/`avg_watts` in narrow ±0.05 windows around each threshold), quality block.

**`latest.json` `derived_metrics.capability.dfa_a1_profile`**:
- `latest_session` — most recent activity with a sufficient dfa block: avg, tiz_split_pct, drift_delta, drift_interpretable, quality_pct, sufficient flag. If no recent session is sufficient, surfaces the most recent insufficient one with `sufficient: false` so the AI can see "AlphaHRV ran but data unusable".
- `trailing_by_sport` — keyed by sport family. Per sport: n_sessions (up to 7 most recent sufficient), date_range, avg_dfa_a1, drift_delta_mean, lt1_crossing_sessions / lt2_crossing_sessions (diagnostic: how many of n_sessions had ≥60s dwell in each crossing band — reveals whether low confidence is due to athlete rarely crossing a band vs other causes), lt1_estimate, lt2_estimate, quality_avg_pct, validated flag, confidence (`low` / `moderate` / `high` / null based on N sessions contributing to crossing-band estimates: 3 → low, 4–5 → moderate, ≥6 → high).

**Estimate shape — cycling:** `{hr, watts_outdoor, watts_indoor, n_sessions, n_sessions_outdoor, n_sessions_indoor}`. HR is pooled across all sessions (physiology signal). Watts are split by environment because the power-DFA relationship differs meaningfully between indoor (VirtualRide) and outdoor cycling — pooling would produce a blended estimate that is not actionable in either context. `watts_outdoor` / `watts_indoor` are always present; null when no qualifying sessions exist in that environment.

**Estimate shape — non-cycling:** `{hr, watts, n_sessions}`. No indoor/outdoor distinction.

#### Zone Validation Use

When `latest.json.derived_metrics.capability.dfa_a1_profile.trailing_by_sport.cycling` has `confidence: "moderate"` or `"high"`, the AI may compare the empirical LT1/LT2 estimates against the dossier-defined cycling thresholds.

**Environment-aware comparison (cycling):** Compare `watts_outdoor` against dossier `ftp` (outdoor). Compare `watts_indoor` against dossier `ftp_indoor`. Compare `hr` (pooled) against `lthr`. Use per-environment `n_sessions_outdoor` / `n_sessions_indoor` to assess depth — apply the same 3/4–5/≥6 confidence thresholds per environment before surfacing a watts calibration delta. If only one environment has sufficient data and the dossier lacks a threshold for the other environment, the available estimate may inform the missing context as a directional reference — but note the cross-environment caveat explicitly.

**If the empirical estimate disagrees with the dossier value by >5%:**
- The AI surfaces a calibration delta as a coaching observation
- The AI does NOT auto-update dossier zones
- The AI does NOT modify prescribed workouts based on DFA-derived thresholds
- The athlete is told the delta exists, the magnitude, the environment, and the underlying N sessions
- Final decision on whether to retest formally and update dossier rests with the athlete

**Confidence floor:** Do not surface calibration deltas at `confidence: "low"` (3 sessions). Single-session noise is too high. Wait for `moderate` or `high`. Per-environment watts deltas additionally require the environment-specific `n_sessions_outdoor` or `n_sessions_indoor` to meet the same thresholds.

**Validated sports only:** Only cycling estimates qualify for calibration delta surfacing. Other sports' estimates are descriptive only.

**Testing Protocol linkage:** When a calibration delta is surfaced per the rule above, see the `Testing Protocol` section below for guidance on when formal confirmation adds value vs. continued continuous-data tracking.

#### Session Interpretation Rules

For each completed session with a sufficient `dfa` block, the AI may apply the following interpretive rules:

**Steady-state Z1/Z2 rides** (prescribed as endurance):
- Should hold DFA a1 > 1.0 throughout
- If `drift.interpretable: true` AND `drift.delta < -0.2`, flag as physiological drift signal — likely fueling state, accumulated heat stress, dehydration, or fatigue. Cross-reference Environmental Conditions Protocol (heat tier) and the session's nutrition/hydration log if available.
- If session held below 1.0 for substantial time despite Z2 prescription, the session was harder internally than external load suggests — note this in the post-workout report

**Sweet Spot / threshold intervals**:
- Work intervals should land in 0.5–0.75 range
- Substantial time below 0.5 indicates the intervals went above LT2 — note as "harder than prescribed internally" if power was on target
- DFA a1 staying above 0.75 during work intervals indicates the work was lighter than threshold internally

**VO₂max intervals**:
- Work intervals should drop below 0.5
- DFA a1 staying above 0.5 during work efforts indicates incomplete recruitment of supra-threshold metabolic state

**Drift interpretability:** The AI checks `drift.interpretable` before applying the drift rule. When `false` (set automatically when >15% of session was above LT2), drift reflects session structure, not autonomic state, and the rule does not apply.

#### Quality Gates

The AI must check the quality block before any DFA-based statement:

| Condition | AI behavior |
|---|---|
| `quality.sufficient: false` | Refuse to interpret. Note "DFA a1 data exists but did not meet quality threshold (X% valid, Y minutes — minimum 20 min required)". Do not invent or infer values. |
| `quality.sufficient: true`, `quality.valid_pct < 80` | Interpret with reduced confidence; mention quality limitation in the report |
| `quality.sufficient: true`, `quality.valid_pct ≥ 80` | Standard interpretation |
| `dfa_a1_profile.trailing_by_sport.{sport}.confidence: null` or `"low"` | Do not surface threshold calibration deltas. Use only for descriptive reporting. |
| `dfa` block absent on activity | No AlphaHRV recording — say nothing about DFA for that session. Do not say "no data" as if it were a problem; the data was never expected. |

#### Boundaries

DFA a1 is a **Tier-2 interpretive signal**. The following constraints are absolute:

1. **Does NOT enter the readiness P0–P3 ladder.** No DFA-based readiness override. The readiness decision uses its existing 7 signals only.
2. **Does NOT auto-update dossier zones.** The AI surfaces deltas, the human decides on retesting and updating.
3. **Does NOT modify prescribed workout intensity.** A planned threshold session remains threshold even if yesterday's DFA suggested LT2 is 5W lower than dossier — the session is executed as planned, the calibration question is handled separately.
4. **One signal among many.** DFA a1 disagreeing with HR/power/RPE/feel is an observation, not a verdict. The AI cross-references rather than treating DFA as ground truth.
5. **Quality gates are non-negotiable.** When quality fails, the AI refuses to interpret. No "best guess" from insufficient data.

#### DFA a1 — Evidence Base

| Source | Finding | Application |
|---|---|---|
| Rowlands et al. (2017) Front Physiol — original framework | DFA a1 from short-term RR scaling correlates with ventilatory thresholds during incremental exercise; α1 ≈ 1.0 marks aerobic threshold, α1 ≈ 0.5 marks anaerobic threshold | Threshold mapping (1.0 ↔ LT1, 0.5 ↔ LT2) |
| Gronwald et al. (2020) Front Physiol — incremental cycling validation | DFA a1 dynamics during graded cycling test confirm the threshold mapping; loss of correlation properties accelerates near VT2 | Cycling-specific validation; rationale for 0.5 cutoff |
| Schaffarczyk et al. (2023) Sports Med Open — trained cyclists | DFA a1 thresholds in trained male cyclists correspond to gas-exchange thresholds with acceptable agreement; intra-individual variability noted | Confirms cycling validation; supports per-athlete calibration caveat |
| Mateo-March et al. (2023) Eur J Appl Physiol — pro cyclists | DFA a1 vs lactate threshold comparison in elite cyclists; method viable for field use, lactate remains gold standard | Pro-level cycling validation; DFA as accessible field proxy, not lab replacement |
| Rogers, Peake et al. (2025) Eur J Appl Physiol — Fatmaxxer validation | Open-source Android implementation (Fatmaxxer) shows close alignment with Kubios HRV reference for both DFA a1 responses and HRV thresholds across 23 cyclists in step-ramp-step protocol | Validates the open-source phone-app path documented in `examples/dfa_a1/NON_GARMIN.md`; relevant when phone fallback ever ships |
| Altini methodology (HRV4Training / AlphaHRV documentation) | Implementation: rolling 2-min windows, RR artifact correction, 5% artifact rate as trustworthiness threshold; sentinel zeros during warmup/uncorrected windows | Quality gates: 5% artifact filter, sentinel-zero exclusion, minimum dwell time |



### Testing Protocol

#### Overview

Continuous data from structured sessions provides most of what a formal FTP test provides — and does so without the single-day dependency on pacing skill, motivation, sleep, and fueling all aligning. The Benchmark Index (longitudinal modeled-FTP tracking), DFA a1 crossing-band estimates, sustained-power observations from `intervals.json`, Efficiency Factor trends, and power/HR curve deltas together produce a continuous picture of aerobic and threshold capability. Well-executed training is the test.

Formal testing retains value in specific situations: establishing a baseline when no historical data exists, resolving contradictions between continuous signals, confirming a suspected zone drift the athlete wants anchored to a number, or re-establishing baseline after an extended data gap.

This section codifies those situations — not as a mandate, but as guidance on when the AI may *suggest* a test and which protocol fits. The decision to test belongs to the athlete.

#### When Formal Testing Adds Value

- **New athlete onboarding** — no historical data to extrapolate from. A single baseline test anchors the dossier; subsequent tracking reverts to continuous data.
- **Athlete confidence** — continuous signals converge on a zone shift, but the athlete wants a concrete number to anchor training on before adjusting.
- **Contradictory signals** — EF trending up while power curve is flat (or the reverse); Benchmark Index positive while DFA a1 profile suggests LT1 regression. A single test resolves which signal to trust.
- **Post-break return** — returning from injury, illness, or extended layoff where continuous data was interrupted. Pre-break zones are unreliable; a test re-anchors.

#### Data-Driven Staleness Signals

The AI may surface a *test suggestion* (not a requirement) when one or more of the following are true. These are triggers for conversation, not prescriptions:

- **DFA a1 calibration delta** — `dfa_a1_profile.trailing_by_sport.cycling` at `moderate` or `high` confidence reports an LT1 or LT2 estimate >5% away from dossier FTP/LTHR (see `Zone Validation Use` above). This is the primary continuous trigger.
- **Benchmark Index stall or regression outside seasonal expectation** — sustained flat or negative Benchmark Index when the Seasonal Context table predicts progressive gains (e.g., Late Base / Build showing 0% or negative). See Benchmark Index section above for seasonal baselines.
- **Sustained power above prescribed zones** — a qualifying session is one where work-interval average power ran ≥3% above prescribed target AND reported RPE landed within or below the expected band for the IF actually achieved. Trigger fires when ≥2 qualifying sessions occur in a rolling 7d window; single-session overshoots are noise and do not trigger.
- **Power-curve vs HR-curve divergence** — shipped `power_curve_delta` shows improvement at a duration while `hr_curve_delta` is flat or negative at the same duration (same HR now sustaining more power). A test at that duration validates the capability shift.

Multiple concurrent signals strengthen the case. A single signal is a conversation; two or more from different sources is a stronger indication.

#### Negative Triggers (Do NOT Suggest a Test)

The AI must not suggest a formal test when any of the following apply:

- Readiness decision is not `go`
- Athlete is within an active recovery week (phase `Recovery` or active deload)
- Illness within the past 14 days (`alerts` block or athlete-reported)
- ACWR outside safe band (<0.8 or ≥1.3)
- RI persistent amber across the trailing 2 days
- Phase is `Peak` or `Taper` — testing disrupts the taper response
- Race-Week Protocol active (D-7 to D-0, see v11.6) — testing is categorically off-limits during race week
- Environmental conditions are adverse (heat tier ≥2, or outdoor conditions unstable)

A test during non-go readiness produces a number that anchors future training on a depressed day — worse than no test.

#### Protocol Options

| Protocol | Session Length | Strengths | Limitations |
|---|---|---|---|
| 20-min field test ×0.95 | ~60 min | Well-understood convention, familiar to most athletes, outdoor-capable | Pacing-skill dependent; first-time testers under-pace or over-pace; single-day dependency on all factors aligning |
| Ramp test (e.g., FTP Ramp) | ~25–35 min | Shorter, less pacing skill required, reproducible indoor protocol | Tends to overestimate for endurance athletes (VO₂max-biased); produces a number that over-prescribes threshold work |
| 2×8-min test | ~45 min | Less fatiguing than 20-min, better for mid-block checks, pacing easier than 20-min | Less common — athlete less familiar with effort; single-day dependency still applies |

**Running equivalents** (30-min threshold run, 5K time trial, critical speed test) — deferred to a later version. Owner: pace curve extension when running data becomes available.

All cycling protocols are outdoor-or-indoor; the result inherits the environment. Indoor tests produce an indoor FTP; outdoor tests produce an outdoor FTP. The shipped `ftp_indoor` / `ftp` dossier split already supports this — the athlete's dossier should carry both if both environments are trained.

#### Interpretation Rules

- **Same-conditions comparison** — compare a test result to the prior test in the same environment (indoor vs outdoor), same protocol, and similar freshness state. An indoor ramp result is not comparable to an outdoor 20-min result. The shipped `ftp_indoor` / `ftp` split formalizes this; apply the same discipline to raw test numbers.
- **Accept / reject criteria** — pacing criterion depends on protocol. For constant-power tests (20-min, 2×8min), power across the work portion must be stable within ±5% of its own average. For ramp tests, the athlete must reach volitional failure at the expected wattage range given training history — early termination from non-physiological causes (GI, mechanical, mental) is grounds to reject. In all protocols, RPE must land in the expected band (see RPE Expectation Bands below) and no environmental or physiological confounders may have intervened (heat tier ≥2, cramping, mechanical issues, nutrition failure). Any of those → reject, retest when conditions allow.
- **Expected improvement rates** — a progressive Base→Build block of 6–8 weeks may produce a +2% to +5% FTP change for an intermediate athlete; elite athletes see smaller absolute shifts. Larger apparent jumps (>7%) usually reflect a prior test that under-measured, not a genuine training response of that magnitude.

#### RPE Expectation Bands (IF-calibrated)

Reference table for interpreting effort against the intensity factor actually achieved. IF is read at session level by default; for highly structured sessions where warm-up and cool-down materially dilute session IF, the relevant read is the work-portion IF (computable from interval data). Used for test-result validation (was this a real threshold effort, or a pacing failure), for reading session effort in general, and as the spec reference for a future Effort Response Signal.

| IF        | Expected RPE | Notes                                                     |
|-----------|--------------|-----------------------------------------------------------|
| 0.65–0.75 | 2–4          | Endurance. RPE ≥6 is a fatigue signal.                    |
| 0.75–0.85 | 4–6          | Tempo / sweet spot. Drift late is normal.                 |
| 0.85–0.95 | 6–8          | Threshold. Sustained RPE <5 is a positive (fitness) tell. |
| 0.95–1.05 | 8–9          | Race-pace / FTP validation effort.                        |
| >1.05     | 9–10         | Supra-threshold.                                          |

**Duration modifier.** Same IF feels harder the longer the session. A 3h ride at IF 0.70 sits higher in the RPE band than 90min at IF 0.70 — drift within the band is expected and not a fatigue signal in itself. The table reads effort at the work portion; duration is a second axis the bands do not encode.

**Indoor vs outdoor modifier.** Same IF typically costs ~1 RPE point more indoors (no convective cooling, constrained thermoregulation, no terrain variation). Consistent with the shipped `ftp_indoor` / `watts_indoor` / `watts_outdoor` split — the physiology differs meaningfully enough that RPE expectation shifts too.

**Environmental modifier.** Heat tier ≥2, altitude, poor sleep, or accumulated fatigue all shift expected RPE up at the same IF. These are context, not override. Cross-reference Environmental Conditions Protocol for tier-specific expectations.

Bands are interpretive overlays; they do NOT alter the Feel/RPE Override rules (v11.14). A reported RPE outside the expected band is an observation to surface, not a signal that changes the readiness decision or the planned session.

#### Effort Response Signal

Since v11.36, every `recent_activities[]` entry in `latest.json` carries an `effort_response` field. This is the deterministic encoding of the RPE Expectation Bands above. The AI layer consumes it; it does not need to re-derive it.

Values:

| Value      | Meaning                                                                    |
|------------|----------------------------------------------------------------------------|
| `positive` | Reported RPE falls below the expected band for the IF achieved. Fitness/freshness tell |
| `neutral`  | Reported RPE within the expected band                                      |
| `negative` | Reported RPE above the expected band. Fatigue/under-recovery tell          |
| `null`     | Session IF absent, RPE absent or ≤ 0, or IF < 0.65 (out of band coverage)  |

**Session IF by design.** The field reads `intensity_factor` (session-level IF) against `rpe` (whole-session RPE the athlete logs). Work-portion IF is computable from `intervals.json` for highly structured sessions where warm-up and cool-down dilute session IF, but the emitted field value uses session IF — matching what the athlete's logged RPE actually references. Structured-session edge cases where the dilution materially distorts the read are caught by the Feel/RPE Override layer (v11.14) rather than by redefining the signal here.

**The IF < 0.65 null is intentional.** Recovery rides and aborted sessions sit below the bands' calibration range. A fabricated band in that regime would produce noise on exactly the sessions least worth flagging. `null` is the correct emission for "out of coverage," distinct from `null` for "missing data."

**Coverage expectation.** The field is sparse in practice — only activities with both a session IF and a logged RPE populate non-null. In a typical athlete's window this may be a small fraction of all activities (outdoor rides predominantly, where RPE is manually entered). Treat it as a low-frequency durability tell, not a per-session readout.

**Interpretation posture.**
- A single `positive` or `negative` reading is an observation to surface, not a trigger. Cross-reference Environmental Conditions Protocol (heat tier, altitude), recent sleep, and position in the training block before assigning meaning
- A repeated `negative` pattern across consecutive sessions — especially at stable or rising IF — is a stronger under-recovery signal and should inform the Interpretation section of the report and any conversation about near-term load
- `positive` readings during Race-Week Protocol or directly after a deload are expected; during build weeks they are a fitness tell worth naming
- The field does NOT modify the readiness P0–P3 decision. That ladder uses its existing six signals only

Report rendering: the post-workout report template emits `Effort response: [value]` on the per-session block, paired with a newly-rendered `IF: [X.XX]` line so the signal is verifiable at a glance. Null cases omit the line per the same convention used for Feel, RPE, and HRRc.

#### Boundaries

Testing Protocol constraints are absolute:

1. **Does NOT mandate testing.** The AI suggests; the athlete decides. An athlete who never formally tests but has continuous data coverage remains correctly served.
2. **Does NOT auto-update dossier zones.** A completed test produces a result; the athlete decides whether to update dossier thresholds. The AI surfaces the number and the delta from current dossier, nothing more.
3. **Does NOT enter the readiness P0–P3 ladder.** A suggested-or-scheduled test does not modify the readiness decision. The readiness decision uses its existing 6 signals only.
4. **Does NOT override continuous data.** When continuous signals and a recent test disagree, investigate first (pacing? environment? fueling?). A single test is one data point; the continuous picture accumulates many.
5. **Does NOT prescribe running or SkiErg tests.** Running equivalents deferred. SkiErg and rowing tests out of current scope.

#### Known Future Touchpoints

- Running-specific RPE bands (pace- or HR-calibrated) land with the pace curve extension.



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

1. **Primary readiness:** RI, HRV, RHR, Sleep
2. **Secondary load metrics:** Stress Tolerance, Load-Recovery Ratio, Consistency Index
3. **Tertiary diagnostics:** Zone Distribution Metrics, Durability Sub-Metrics, Capability Metrics (Aggregate Durability, TID Drift, Power Curve Delta, HR Curve Delta, Sustainability Profile)

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
| **Easy Time Ratio**              | `(Z1+Z2) Time ÷ Total Time`             | Validates 80/20 distribution by time                      |
| **Hard Days per Week**           | Count of days with Z4+ work             | Session-based intensity tracking for high-volume athletes |

**Zone Classification (7-Zone to Seiler 3-Zone Mapping):**

| 7-Zone Model | Seiler Zone | Classification | Notes                                                     |
|--------------|-------------|----------------|-----------------------------------------------------------|
| Z1–Z2        | Zone 1      | Easy           | Below LT1/VT1 (<2mM lactate)                              |
| Z3           | Zone 2      | Grey Zone      | Between LT1 and LT2 — "too much pain for too little gain" |
| Z4–Z7        | Zone 3      | Hard/Quality   | Above LT2/VT2 (>4mM lactate)                              |

**Intensity Distribution Targets:**

For athletes training **<10 hours/week** (time-based targets more practical):

| **Phase** | **Grey Zone % Target** | **Quality Intensity % Target** | **Easy Time Ratio** |
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
- Normal Endurance Decay + High HR–Power Decoupling → Cardiovascular drift; assess hydration, heat, or aerobic base fitness. See **Environmental Conditions Protocol — Cardiac Drift and Decoupling in Heat** for temperature-specific interpretation rules.
- High Z2 Stability variance → Inconsistent pacing execution; review session targeting

**Note:** HR–Power Decoupling (existing metric) serves as the cardiac drift diagnostic. Do not duplicate with separate "Aerobic Decay" metric.

#### Aggregate Durability (Capability Metric)

The per-session Durability Sub-Metrics above diagnose *individual session* limitations. The **Aggregate Durability** metric provides a *trend-level* view of aerobic efficiency across multiple sessions, using HR–Power decoupling as the signal.

**Data Source:** The `capability.durability` object in the data mirror provides rolling 7-day and 28-day aggregate decoupling from qualifying steady-state sessions.

**Session Filter (all must be true):**
- HR–Power decoupling value exists (not null)
- Variability Index (VI) exists, > 0, and ≤ 1.05 (steady-state power only)
- Moving time ≥ 5400 seconds (90 minutes)

**Rationale:** Per Maunder et al. (2021) and Rothschild et al. (2025), meaningful cardiac drift requires prolonged exercise. The 90-minute floor is the practical field threshold where drift becomes detectable. The VI ≤ 1.05 filter excludes interval sessions where decoupling reflects recovery dynamics, not aerobic drift. Negative decoupling values are included — they indicate HR drifted down relative to power (strong durability or cooling conditions).

**Aggregate Metrics:**

| **Metric**               | **Description**                                           | **Minimum Data** |
|--------------------------|-----------------------------------------------------------|-------------------|
| mean_decoupling_7d       | Mean decoupling from qualifying sessions in last 7 days   | ≥ 2 sessions (reliable ≥ 3) |
| mean_decoupling_28d      | Mean decoupling from qualifying sessions in last 28 days  | ≥ 2 sessions (reliable ≥ 5) |
| high_drift_count_7d/28d  | Count of qualifying sessions with decoupling > 5%         | —                 |
| trend                    | 7d vs 28d comparison: improving / stable / declining      | Both windows      |

**Trend Logic:**
- `improving`: 7d mean < 28d mean by > 1 percentage point
- `stable`: 7d and 28d means within ±1 percentage point
- `declining`: 7d mean > 28d mean by > 1 percentage point

Trend direction matters more than absolute values — an athlete's baseline decoupling varies with fitness, conditions, and terrain.

**Alert Thresholds:**

| Condition                                      | Severity | Action                                            |
|------------------------------------------------|----------|---------------------------------------------------|
| 28d mean > 5% sustained (N28 ≥ 5)             | alarm    | Aerobic efficiency concern — review volume/recovery |
| 7d mean > 28d mean by > 2% (N7 ≥ 3, N28 ≥ 5)  | warning  | Durability declining — check fatigue and recovery   |
| ≥ 3 sessions with > 5% in 7d                  | warning  | Repeated poor durability — investigate root cause   |

**Reliability Gate:**

The 28d mean is computed at ≥ 2 qualifying sessions but alerts require larger samples for statistical reliability. A mean of 2 sessions is too noise-prone for a 28-day trend metric — two unlucky rides can produce a misleading aggregate. The alert gates are:

- **Alarm** (28d mean > 5%): requires `qualifying_sessions_28d ≥ 5`
- **Declining warning** (7d > 28d by > 2%): requires `qualifying_sessions_7d ≥ 3 AND qualifying_sessions_28d ≥ 5`

Below gate, the durability object exposes `reliability_limited: true` and `reliability_note` with both current counts and minimums. Means remain visible for situational awareness but are not treated as actionable. The `high_drift_count_7d ≥ 3` warning is count-based and not subject to the reliability gate.

This gate is a sample-size safeguard, not a metric redefinition. Athletes whose training rarely produces qualifying sessions (e.g., primarily sub-90-minute indoor/structured sessions) will see `reliability_limited: true` often — this correctly signals that this specific long-duration steady-state durability metric has insufficient data for that training pattern, not that the athlete lacks durability. Interpret via other capability metrics in those cases.

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

#### Power Curve Delta (Capability Metric)

The per-session and trending capability metrics above (Durability, EF, HRRc) diagnose *how* the athlete executes sessions. **Power Curve Delta** provides a *what's changing* view — comparing MMP (Mean Maximal Power) at key durations across two time windows to reveal energy system adaptation direction that CTL/ATL/TSS miss entirely.

**Data Source:** The `capability.power_curve_delta` object in the data mirror compares MMP from two 28-day windows (current vs previous) fetched via the Intervals.icu `power-curves` API. Sport-filtered to cycling (`type=Ride`). Single API call per sync.

**Anchor Durations:**

| Anchor | Duration | Energy System | Physiological Signal |
|--------|----------|---------------|---------------------|
| 5s | 5 seconds | Neuromuscular | Sprint power, NM recruitment |
| 60s | 60 seconds | Anaerobic/VO₂ | Anaerobic capacity |
| 300s | 5 minutes | MAP | Max Aerobic Power |
| 1200s | 20 minutes | Threshold | FTP-adjacent sustainable power |
| 3600s | 60 minutes | Endurance | Aerobic endurance ceiling |

**Rotation Index:**

`rotation_index = mean(5s pct_change, 60s pct_change) - mean(1200s pct_change, 3600s pct_change)`

300s is excluded from the rotation calculation — it sits at the transitional boundary between anaerobic and aerobic energy systems and muddies the signal. It remains in the anchors block for coaching context.

| Rotation Index | Interpretation |
|---------------|----------------|
| Positive (> +1.0) | Sprint-biased gains — short-duration power improving faster than endurance |
| Near zero (±1.0) | Balanced adaptation or minimal change across the curve |
| Negative (< -1.0) | Endurance-biased gains — long-duration power improving faster than sprint |

**Data Quality Guards:**
- Per-anchor: null if that duration is not present in the window's data (athlete never rode long enough) or if watts value is 0
- Per-anchor pct_change: null if either window's anchor watts is null (avoids division by zero)
- Block-level: entire block nulled when either window has fewer than 3 valid anchor durations
- Rotation index: null if any of its 4 component anchors (5s, 60s, 1200s, 3600s) has null pct_change

**Interpretation Guidance:**
- Compare rotation direction to training phase: endurance-biased rotation during Base is expected; sprint-biased during Build with VO₂max work may indicate neuromuscular freshness while threshold stagnates
- Cross-reference with Benchmark Index and eFTP: if eFTP is flat but 300s/1200s anchors are rising, the power curve is seeing what FTP tracking misses
- Cross-reference with TID drift: if rotation is sprint-biased but TID shows Polarized → expected. Sprint-biased with Threshold TID → may indicate interval quality is good but volume adaptation is lagging
- Absolute watts matter for coaching context; pct_change matters for trend direction
- Small changes (< ±1.5% at an anchor) are within normal variation — don't overinterpret

**Scope:** Display and coaching context only. Not wired into readiness_decision signals. The AI coach layer interprets direction, magnitude, and phase context — no adaptation labels are baked into the data.

**References:**
- Pinot & Grappe (2011): Power profiling across durations for talent identification and training prescription.
- Quod et al. (2010): MMP tracking as a training monitoring tool in elite cyclists.

---

#### HR Curve Delta (Capability Metric)

While Power Curve Delta tracks *output* adaptation (watts), **HR Curve Delta** tracks *cardiac* adaptation — comparing max sustained heart rate at key durations across two time windows. This is the universal performance curve: it works for every athlete with a heart rate monitor, regardless of sport or power meter availability.

**Data Source:** The `capability.hr_curve_delta` object in the data mirror compares max sustained HR from two 28-day windows fetched via the Intervals.icu `hr-curves` API. No sport filter — HR is physiological, not sport-specific. Max sustained HR at 300s is max sustained HR at 300s whether it came from cycling, running, or SkiErg. The curve is naturally dominated by the hardest efforts regardless of modality.

**Anchor Durations (4 anchors — no 5s):**

| Anchor | Duration | Signal |
|--------|----------|--------|
| 60s | 1 minute | Anaerobic HR ceiling |
| 300s | 5 minutes | VO₂max HR |
| 1200s | 20 minutes | Threshold HR |
| 3600s | 60 minutes | Endurance HR |

No 5s anchor — peak HR at 5 seconds is just maximum heart rate, not an energy system signal.

**Rotation Index:**

`rotation_index = mean(60s pct_change, 300s pct_change) - mean(1200s pct_change, 3600s pct_change)`

| Rotation Index | Interpretation |
|---------------|----------------|
| Positive (> +1.0) | Intensity-biased HR shift — short-duration max HR rising faster |
| Near zero (±1.0) | Balanced or minimal change |
| Negative (< -1.0) | Endurance-biased HR shift — long-duration sustained HR rising faster |

**CRITICAL — Ambiguity of Rising HR:**

Unlike power where higher is always better, rising max sustained HR is **ambiguous**:

- **Positive interpretation:** Improved cardiac output, better ability to reach and sustain high HR (fitness gain, especially after base phase)
- **Negative interpretation:** Accumulated fatigue, dehydration, heat stress, overreaching — the heart is working harder for the same or less output

The AI coach **must** cross-reference with:
- Resting HRV and resting HR trends (declining HRV + rising max HR = fatigue signal)
- RPE trends (rising HR + rising RPE = fatigue; rising HR + stable/lower RPE = fitness)
- Power curve delta (rising HR + rising power = fitness; rising HR + flat power = efficiency loss)
- Environmental context (heat elevates HR — see Environmental Conditions Protocol)

**Data Quality Guards:** Same as power_curve_delta — per-anchor null, div-by-zero protection, block-level null when <3 valid anchors.

**Scope:** Display and coaching context only. Not wired into readiness_decision signals. The ambiguity of HR changes makes automated decision-making inappropriate — interpretation requires multi-signal context.

---

#### Sustainability Profile (Race Estimation)

The capability metrics above track adaptation direction (deltas) and session execution quality (durability, EF, HRRc). **Sustainability Profile** answers a different question: *what can this athlete sustain right now?* — the foundation for race performance estimation.

**Data Source:** The `capability.sustainability_profile` object provides per-sport power and HR sustainability at race-relevant anchor durations, fetched from a single 42-day window via sport-filtered `power-curves` and `hr-curves` API calls. Each sport family that has recent training data gets its own block.

**Three Model Layers (Cycling Only):**

At each anchor duration, cycling provides three power estimates — the divergence between them IS the coaching signal:

1. **Actual MMP** — observed best effort in the 42-day window. Ground truth, but training-context-dependent (athlete may not have produced a true max at every duration).
2. **Coggan Duration Factors** — sustainable power as % of athlete-set FTP, from the standard reference table (Allen & Coggan, *Training and Racing with a Power Meter*, 3rd ed.). Midpoints of published ranges:

| Duration | Factor | Range | Interpretation |
|----------|--------|-------|----------------|
| 5 min    | 1.06   | 1.00–1.12 | MAP / VO₂max ceiling |
| 10 min   | 0.97   | 0.94–1.00 | Upper threshold |
| 20 min   | 0.93   | 0.91–0.95 | ~FTP test effort |
| 30 min   | 0.90   | 0.88–0.93 | Threshold sustainability |
| 60 min   | 0.86   | 0.83–0.90 | TT pacing target |
| 90 min   | 0.82   | 0.78–0.85 | Long TT / road race |
| 2 h      | 0.78   | 0.75–0.82 | Endurance event floor |

3. **CP/W′ Model** — `P = CP + W′/t` (Skiba et al., 2012). Uses athlete-set FTP as CP proxy and W′ from the Intervals.icu power model. One equation, pre-evaluated at each anchor duration. More physiologically grounded at shorter durations where W′ contribution is meaningful.

**Model Trust by Duration:**
- **≤20 min:** CP/W′ is primary — W′ depletion dynamics dominate. Coggan is a sanity check.
- **30 min:** Crossover zone — both models apply. Compare for consistency.
- **≥60 min:** Coggan duration factors are the established reference — at longer durations, P = CP + W′/t converges to just CP, losing discriminatory power. Coggan's empirical percentages better capture real-world duration-dependent fatigue.

**Model Divergence (`model_divergence_pct`):**
- `(actual_watts - cp_model_watts) / cp_model_watts × 100`
- Positive at short durations → strong anaerobic capacity relative to CP, or stale W′ value
- Negative at short durations → athlete hasn't produced recent maximal short efforts (training gap, not necessarily fitness gap)
- Positive at long durations → aerobic engine outperforming the model (strong durability)
- Large divergence at any duration → model inputs (FTP, W′) may be stale — cross-reference with `ftp_staleness_days` and `benchmark_index`

**Non-Cycling Power Sports (SkiErg, Rowing):**
Actual MMP only. No published Coggan-equivalent duration factors exist. No sport-specific CP/W′ values are typically configured. These fields are absent from non-cycling sport blocks (not null — absent). The AI works with observed data and HR.

**Indoor vs Outdoor (Cycling Only):**
Power curves are fetched separately for `Ride` and `VirtualRide`. At each anchor, the higher value is used. The `source` flag indicates which environment produced the best effort:
- `observed_outdoor` — from outdoor rides (Ride type)
- `observed_indoor` — from indoor rides (VirtualRide type)
- Indoor MMP is typically 3–5% lower than outdoor (cooling limitations, motivational differences). If the best effort at a race-relevant duration is indoor, the outdoor race ceiling is likely higher. The source flag lets the AI communicate this to the athlete.

**HR Layer (Per-Sport):**
Each sport block includes `actual_hr` (max sustained HR at each anchor) and `pct_lthr` (as % of that sport's LTHR from the per-sport thresholds map, v11.8). HR curves are sport-filtered — cycling HR comes from cycling rides only, SkiErg HR from SkiErg sessions only. This avoids cross-sport contamination (running HR is typically 5–10 bpm higher than cycling at equivalent physiological effort).

**Coverage and Confidence:**
- `coverage_ratio` — fraction of anchors with observed actual data. Below 0.5, the profile is heavily model-dependent; communicate uncertainty.
- `ftp_staleness_days` — days since last FTP change in history. >60 days = high staleness; model predictions should carry wider uncertainty bands.
- Longer anchors (5400s, 7200s) are increasingly model-dependent — most athletes don't produce true max efforts at 90min+ in training. The AI should note when estimates rely on extrapolation.

**What Stays in the AI Layer (Not Pre-Computed):**
- Connecting the table to specific `race_calendar` events ("your 40km TT is ~60min, here's your sustainability data at that duration")
- Terrain and conditions adjustments (elevation, heat, wind, drafting, nutrition strategy)
- Training trajectory interpretation ("CTL rising + power curve delta improving → race-day ceiling is likely higher than today's table")
- Pacing strategy (even power, negative split, variable-terrain power management)
- Confidence narrative wrapping the pre-computed signals

**Sport-Specific Anchor Sets:**

| Sport | Anchors | Rationale |
|-------|---------|-----------|
| Cycling | 300s, 600s, 1200s, 1800s, 3600s, 5400s, 7200s | Covers 5min MAP through 2h endurance events |
| SkiErg | 60s, 120s, 300s, 600s, 1200s, 1800s | Sprint (500m) through 30min events |
| Rowing | 60s, 120s, 300s, 600s, 1200s, 1800s | Sprint (500m) through 30min events |

**Data Quality Guards:** Per-anchor null if duration not in API response or value is 0/null. W/kg null if weight unavailable. `pct_lthr` null if sport LTHR not configured. Block-level null if sport has <2 valid observed anchors. Weight fallback chain: today's wellness → most recent in wellness history → athlete profile (icu_weight) → null.

**Scope:** Coaching context and race estimation. Not wired into readiness_decision signals. The sustainability profile is a ceiling estimate — actual race-day performance depends on conditions, pacing, nutrition, and freshness that the pre-computed table cannot capture.

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

**W′ Depletion Under Glycogen Deficit:**

Glycogen depletion significantly reduces W′ (anaerobic work capacity) while Critical Power remains relatively unchanged. Miura et al. (2000) found W′ dropped from 12.83 kJ to 10.33 kJ (~20% reduction) after a glycogen depletion protocol. This means the athlete's ability to surge above threshold — for attacks, climbs, segment attempts — shrinks as the ride progresses and glycogen depletes.

The AI should reduce above-threshold expectations late in long rides. A segment that requires 5 minutes above CP at km 20 may be feasible, but the same effort at km 100 after 3,000+ kJ of expenditure faces a smaller W′ reservoir. Cross-reference with the glycogen budget model in the Nutrition Protocol — if the estimated glycogen deficit exceeds 1,500 kcal, W′-dependent efforts should carry wider feasibility margins in segment reasoning.

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
│  • Sleep (hours)                                            │
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
│  • Easy Time Ratio                                          │
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
| Grey Zone Percentage         | Easy Time Ratio           | **Complementary.** Easy Time Ratio validates 80/20 by easy time. Grey Zone Percentage specifically flags grey zone creep.            |
| Quality Intensity Percentage | Easy Time Ratio           | **Complementary.** Quality Intensity Percentage tracks quality intensity. For high-volume athletes, Hard Days per Week is preferred. |
| Stress Tolerance             | Strain                    | **Derived from.** Stress Tolerance = (Strain ÷ Monotony) ÷ 100, providing absorption capacity context.                               |
| Aggregate Durability         | HR–Power Decoupling       | **Aggregates.** Per-session decoupling is the raw input; aggregate durability provides the 7d/28d trend view.                        |
| Aggregate Durability         | Durability Index (DI)     | **Complementary.** DI = power output sustainability. Aggregate Durability = cardiovascular efficiency trend across sessions.          |
| Seiler TID (Treff PI)        | Easy Time Ratio           | **Different scale.** Easy Time Ratio = 0–1 easy-time share. Treff PI = logarithmic scale with 5-class classification.                |
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

**Data Freshness:** Every numeric value in any report must come from a current read of its source JSON file (`latest.json`, `history.json`, `intervals.json`, `ftp_history.json`, or `routes.json` as appropriate for the metric). Do not carry forward values from an earlier report or an earlier point in the conversation — upstream data may have updated between reads. This rule applies especially to AI systems with persistent memory or long-running sessions, where values from prior reports may be cached and reused inadvertently.

**Pre-Workout Reports must include:**
- Weather and coach note (if athlete location is available)
- Phase context (when confidence is high or medium)
- Readiness assessment (HRV, RHR, Sleep vs baselines)
- Load context (TSB, ACWR, Load/Recovery, Monotony if > 2.3)
- Capability snapshot (Durability 7d mean + trend; TID drift if not consistent)
- Today's planned workout with duration and targets (or rest day + next session preview)
- Go/Modify/Skip recommendation with rationale

See `PRE_WORKOUT_REPORT_TEMPLATE.md` in the examples directory for conditional fields and readiness decision logic.

**Post-Workout Reports must include:**
- One-line session summary
- Completed session metrics (power, HR, zones, decoupling, VI, TSS vs planned)
- Plan compliance assessment
- Weekly running totals (phase context, polarization, durability 7d/28d + trend, TID 28d + drift, CTL, ATL, TSB, ACWR, hours, TSS)
- Overall coach note (2-4 sentences: compliance, key quality observations, load context, recovery note)
- Tomorrow preview (when planned session exists)

See `POST_WORKOUT_REPORT_TEMPLATE.md` in the examples directory for field reference and rounding conventions.

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
"error": "ACWR ≥ 1.35 — exceeds safe progression threshold"

Human-review override requires athlete confirmation and metadata flag "override": true.

---

### 8 — Workout Reference Interface

When a plan requires a structured session (per Section 4), the AI must select from the **Workout Reference Library** (`examples/workout-library/WORKOUT_REFERENCE.md`).

**Selection rules:**
- Match target adaptation (Sweet Spot, VO₂max, Endurance, etc.) to the session slot identified by the plan.
- Use Section 11 A readiness outputs (TSB, RI, HRV trend) to choose the appropriate format variant and intensity level within that adaptation category.
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
    "protocol_version": "11.33",
    "checklist_passed": [0, 1, 2, 3, 4, 5, "5b", 6, "6b", 7, 8, 9, 10],
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
          "current_week_hard_days_completed": 1,
          "current_week_hard_days_total": 3,
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
    "easy_time_ratio": 0.97,
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
| `checklist_passed`             | array    | List of checklist items (0–10, including 5b and 6b) that passed validation                               |
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
| `phase_detection.basis.stream_2` | object | Prospective features: `planned_tss_delta`, `hard_sessions_planned` (retained for compat, superseded by `current_week_hard_days_total`), `current_week_hard_days_completed`, `current_week_hard_days_total`, `race_proximity`, `next_week_load`, `plan_coverage_current_week`, `plan_coverage_next_week`. |
| `phase_detection.basis.data_quality` | string | "good" / "mixed" / "poor" — penalized by HR-only intensity basis, short lookback. |
| `phase_detection.basis.stream_agreement` | boolean/null | Whether Stream 1 and Stream 2 suggested the same phase. null if either stream has no opinion. |
| `phase_detection.previous_phase` | string/null | Phase from last weekly_180d row (feeds hysteresis).                              |
| `phase_detection.phase_duration_weeks` | number | Consecutive weeks classified as current phase.                                 |
| `phase_detection.dossier_declared` | string/null | Phase declared in athlete dossier (optional input).                            |
| `phase_detection.dossier_agreement` | boolean/null | Whether detected phase matches dossier declaration.                           |
| `readiness_decision`           | object   | Pre-computed go/modify/skip decision (v3.72+). Top-level, alongside `alerts`. |
| `readiness_decision.recommendation` | string | "go" / "modify" / "skip" — baseline recommendation for pre-workout reports. |
| `readiness_decision.priority`  | number   | 0 (safety stop), 1 (acute overload), 2 (accumulated fatigue), 3 (green light). |
| `readiness_decision.signals`   | object   | Per-signal status objects (hrv, rhr, sleep, tsb, acwr, ri). Each has `status` (green/amber/red/unavailable) and raw values with deltas. |
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
| `easy_time_ratio`              | number   | Easy time (Z1+Z2) as ratio of total                                                 |
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
| `zone_basis`                   | string/null | Zone basis used for aggregation: `"power"`, `"hr"`, or `"mixed"`. Present on `zone_distribution_7d`, all `seiler_tid_*` blocks. Null when no zone data available. Reflects `ZONE_PREFERENCE` config. |
| `tid_drift`                    | string   | TID drift category: "consistent" / "shifting" / "acute_depolarization"          |
| `durability_7d_mean`           | number   | Mean HR–Power decoupling (%) from qualifying steady-state sessions, 7-day       |
| `durability_28d_mean`          | number   | Mean HR–Power decoupling (%) from qualifying steady-state sessions, 28-day      |
| `durability_trend`             | string   | Durability trend: "improving" / "stable" / "declining"                          |
| `hrrc`                         | number/null | Per-activity HRRc: largest 60-second HR drop (bpm) after exceeding configured threshold HR for >1 min. Intervals.icu API field `icu_hrr`. Null when threshold not reached, recording stopped before cooldown, or no HR data. Higher = better parasympathetic recovery. |
| `capability.hrrc.mean_hrrc_7d` | number/null | Mean HRRc (bpm) from qualifying sessions in last 7 days. Requires ≥ 1 session. |
| `capability.hrrc.mean_hrrc_28d`| number/null | Mean HRRc (bpm) from qualifying sessions in last 28 days. Requires ≥ 3 sessions. |
| `capability.hrrc.trend`        | string/null | HRRc trend: "improving" / "stable" / "declining". >10% difference between 7d and 28d means = meaningful. Null if either window has insufficient sessions. Display only — not wired into readiness_decision signals. |
| `capability.power_curve_delta.window_days` | number | Window size in days (default 28). |
| `capability.power_curve_delta.current_window` | object | `{start, end}` date strings for the current (recent) window. |
| `capability.power_curve_delta.previous_window` | object | `{start, end}` date strings for the previous (comparison) window. |
| `capability.power_curve_delta.anchors` | object/null | Per-anchor MMP comparison. Keys: `5s`, `60s`, `300s`, `1200s`, `3600s`. Each has `current_watts`, `previous_watts`, `pct_change`. Null when block-level guard fails. |
| `capability.power_curve_delta.anchors.{dur}.current_watts` | number/null | MMP watts at this anchor duration in the current window. Null if duration not in data or watts is 0. |
| `capability.power_curve_delta.anchors.{dur}.previous_watts` | number/null | MMP watts at this anchor duration in the previous window. Null if duration not in data or watts is 0. |
| `capability.power_curve_delta.anchors.{dur}.pct_change` | number/null | Percentage change from previous to current window. Rounded to 1 decimal. Null if either window's watts is null. |
| `capability.power_curve_delta.rotation_index` | number/null | `mean(5s,60s pct_change) - mean(1200s,3600s pct_change)`. Positive = sprint-biased gains, negative = endurance-biased. 300s excluded. Null if any component anchor has null pct_change. Rounded to 1 decimal. |
| `capability.power_curve_delta.note` | string | Interpretation guidance for AI coaches. |
| `capability.hr_curve_delta.window_days` | number | Window size in days (default 28). |
| `capability.hr_curve_delta.current_window` | object | `{start, end}` date strings for the current (recent) window. |
| `capability.hr_curve_delta.previous_window` | object | `{start, end}` date strings for the previous (comparison) window. |
| `capability.hr_curve_delta.anchors` | object/null | Per-anchor max sustained HR comparison. Keys: `60s`, `300s`, `1200s`, `3600s`. Each has `current_bpm`, `previous_bpm`, `pct_change`. Null when block-level guard fails. |
| `capability.hr_curve_delta.anchors.{dur}.current_bpm` | number/null | Max sustained HR (bpm) at this anchor duration in the current window. Null if duration not in data or value is 0. |
| `capability.hr_curve_delta.anchors.{dur}.previous_bpm` | number/null | Max sustained HR (bpm) at this anchor duration in the previous window. Null if duration not in data or value is 0. |
| `capability.hr_curve_delta.anchors.{dur}.pct_change` | number/null | Percentage change from previous to current window. Rounded to 1 decimal. Null if either window's value is null. |
| `capability.hr_curve_delta.rotation_index` | number/null | `mean(60s,300s pct_change) - mean(1200s,3600s pct_change)`. Positive = intensity-biased HR shift, negative = endurance-biased. Null if any component anchor has null pct_change. AMBIGUOUS: rising HR may indicate fitness or fatigue — cross-reference required. |
| `capability.hr_curve_delta.note` | string | Interpretation guidance for AI coaches. Emphasizes HR ambiguity. |
| `capability.sustainability_profile.window` | object | `{days, start, end}` — window size and date range for sustainability curves. Default 42 days. |
| `capability.sustainability_profile.weight_kg` | number/null | Weight used for W/kg calculations. Null if no weight available (all W/kg fields null). |
| `capability.sustainability_profile.weight_source` | string/null | Source of weight: `wellness_recent`, `wellness_extended`, or `athlete_profile`. Null if unavailable. |
| `capability.sustainability_profile.{sport}` | object/null | Per-sport sustainability block. Key is sport family: `cycling`, `ski`, `rowing`. Absent if sport has no recent activity data. |
| `capability.sustainability_profile.{sport}.anchors` | object/null | Per-anchor sustainability data. Keys are duration labels (e.g., `300s`, `1200s`, `3600s`). Null if <2 valid observed anchors. |
| `capability.sustainability_profile.{sport}.anchors.{dur}.actual_watts` | number/null | Observed MMP at this duration in the 42d window. Null if no effort at this duration or value is 0. |
| `capability.sustainability_profile.{sport}.anchors.{dur}.actual_wpkg` | number/null | Actual watts / weight_kg. Null if watts or weight unavailable. |
| `capability.sustainability_profile.{sport}.anchors.{dur}.actual_hr` | number/null | Max sustained HR (bpm) at this duration from sport-filtered HR curves. Null if unavailable. |
| `capability.sustainability_profile.{sport}.anchors.{dur}.pct_lthr` | number/null | `actual_hr / sport_lthr × 100`. Uses sport-specific LTHR from per-sport thresholds (v11.8). Null if LTHR not configured for this sport. |
| `capability.sustainability_profile.{sport}.anchors.{dur}.source` | string/null | `observed_outdoor`, `observed_indoor` (cycling only — from Ride vs VirtualRide), or `observed` (non-cycling). Null if no observed data. |
| `capability.sustainability_profile.{sport}.anchors.{dur}.coggan_watts` | number/null | Cycling only. FTP × Coggan duration factor (midpoint). Null for non-cycling sports or if FTP unavailable. |
| `capability.sustainability_profile.{sport}.anchors.{dur}.coggan_wpkg` | number/null | Cycling only. Coggan watts / weight_kg. |
| `capability.sustainability_profile.{sport}.anchors.{dur}.cp_model_watts` | number/null | Cycling only. `CP + W′/t` where CP ≈ FTP, t = anchor duration in seconds. Null if FTP or W′ unavailable. |
| `capability.sustainability_profile.{sport}.anchors.{dur}.cp_model_wpkg` | number/null | Cycling only. CP model watts / weight_kg. |
| `capability.sustainability_profile.{sport}.anchors.{dur}.model_divergence_pct` | number/null | Cycling only. `(actual - cp_model) / cp_model × 100`. Positive = actual exceeds model. Null if either value missing. |
| `capability.sustainability_profile.{sport}.coverage_ratio` | number | Fraction of anchors with observed actual_watts data. 0.0–1.0. Below 0.5 = heavily model-dependent. |
| `capability.sustainability_profile.cycling.ftp_used` | number/null | Cycling only. Athlete-set FTP used for Coggan and CP/W′ calculations. From sportSettings, not eFTP. |
| `capability.sustainability_profile.cycling.w_prime_used` | number/null | Cycling only. W′ (joules) from Intervals.icu power model, used for CP/W′ calculations. |
| `capability.sustainability_profile.cycling.ftp_staleness_days` | number/null | Cycling only. Days since last FTP change in ftp_history.json. >60 = high staleness. |
| `capability.sustainability_profile.cycling.model_trust_note` | string | Cycling only. Interpretation guidance for model trust by duration. |

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
