#!/usr/bin/env python3
"""
Intervals.icu → GitHub/Local JSON Export
Exports training data for LLM access.
Supports both automated GitHub sync and manual local export.

Version 3.112 - Body weight signal block (current_status.weight): gated fields
  for block-level W/kg and weekly weight trend, all surfaced via a single
  _build_weight_signal helper. Failed-gate fields are absent from the JSON;
  AI layer omits the corresponding report section silently (no boilerplate).
  Display blocks ship for narrated weights per Display Unit Semantics; W/kg
  stays unit-universal.
  Fields:
    weight_latest_kg / weight_latest_date — gate: latest weigh-in age <=14d
    wkg_current + wkg_ftp_source [+ ftp_setting_date] — gate: weight_latest
      present + FTP source. Tested cycling FTP from sportSettings preferred,
      eFTP fallback. eFTP is not suppressed for stale tested FTP — the
      source tag plus ftp_setting_date carry the staleness signal. Date
      reflects the FTP setting change recorded in ftp_history.json (not a
      formal test date — Intervals does not expose one).
    wkg_block_start / wkg_block_end / wkg_block_delta — gate: >=1 weigh-in
      within the FIRST 4 days of the trailing 28d window AND >=1 weigh-in
      within the LAST 4 days (v1 block proxy; protocol does not yet track
      explicit block boundaries). Both endpoints use current FTP, so delta
      reflects weight change only.
    weight_7d_avg_kg — gate: >=4 weigh-ins in trailing 7d
    weight_28d_slope_kg_per_week — gate: >=14 weigh-ins in trailing 28d
    display.{weight_latest, weight_7d_avg, weight_28d_slope_per_week} —
      _to_display style {value, unit} pairs respecting athlete weight pref;
      slope built manually to preserve 3dp and append "/week" to unit code.
  Pairs with SECTION_11.md v11.43 (new Body Weight Handling section incl.
  Deliberately Deferred subsection) and weight rows in BLOCK / WEEKLY
  report templates. Pre-workout and post-workout templates intentionally
  untouched in v1.

Version 3.111 - latest.history.last_generated freshness fix: auto-history
  generation block (should_generate_history → generate_history → write/publish)
  moved in main() from after collect_training_data to before it.
  _get_history_confidence() inside collect_training_data now reads the
  just-written history.json, so latest.history.last_generated reflects the same
  generated_at as the on-disk history. Previously, runs that triggered a
  history rebuild published latest.json with stale last_generated because the
  freshness read happened during data dict construction, before the rebuild
  step. Local and GitHub modes share a single guarded block — args.output picks
  the write target. try/except resilience preserved: failed history regen still
  permits latest.json publish. Routes/intervals generation unchanged (still
  runs after collect_training_data, which populates _intervals_data and
  _routes_data). No schema change.

Version 3.110 - Weekly capability rollup + monthly phase alignment + decoupling 0.0 fix:
  (1) weekly_180d rows now carry six per-week capability fields: durability_mean /
  durability_qualifying (VI<=1.05, VI>0, mt>=5400, decoupling not None), ef_mean /
  ef_qualifying (cycling types, VI<=1.05, VI>0, mt>=1200, EF not None), hrrc_mean /
  hrrc_qualifying (icu_hrr>0). N>=1 emits a mean; qualifying count signals confidence.
  Trajectory layer for Season Report v2 — no alert or trend logic at this layer.
  (2) monthly_*y[].dominant_phase now derives from modal aggregation of already-computed
  weekly_180d[].phase_detected values rather than the previous standalone CTL-trend +
  qi_pct inline rule. Overlap test: week_start < next_month AND week_end >= current_month
  (catches boundary weeks straddling month edges). Most-frequent label wins; TSS is
  tie-break only. Null when no overlapping weekly rows (month outside 180d window).
  Vocabulary now matches _detect_phase_v2 output.
  (3) _calculate_durability: replaced `or`-chain fallback (`get("icu_hr_decoupling") or
  get("decoupling")`) with explicit is-None check — prevents silent drop of 0.0 values.
  (4) Same is-None pattern applied to all three HRRc dict-extraction sites
  (_calculate_hrrc_trend qualifying filter, weekly capability rollup, activity formatter
  raw_hrrc): explicit `value is None` check before falling through to `hrr`. If API ever
  returns `{"value": 0, ...}`, 0 is now treated as authoritative (then filtered by the
  >0 gate) rather than falling through to a sibling key. SEASON_REPORT_TEMPLATE.md Notes
  section updated: phase-narrative bullet now describes modal-from-_detect_phase_v2
  derivation and the structural null-for-older-months behavior; capability-absent bullet
  replaced with per-week trajectory field documentation.

Version 3.109 - Display Unit Semantics: every narrative-bearing field that ships in
  canonical metric (distance_km, elevation_m, weight_kg, height_m, avg_speed/max_speed
  as KPH, position_km, total_distance_km, total_elevation_m, elevation_per_km,
  distance_meters) now sits alongside a nested display block ({value, unit} sub-objects
  under `display.*`) converted to the athlete's Intervals.icu unit preferences. One
  schema shape across every emission site — AI rule is uniformly "quote display.*".
  Canonical fields are preserved verbatim — the AI quotes display.* in narrative;
  calculations continue to use the canonical fields (preserves the no-virtual-math
  contract). New athlete_profile.display_preferences block surfaces the six-key prefs
  map (wind/temp/rain/distance/weight/height) — no new API call (already extracted by
  _athlete_units_from_dict). Two new helpers: _to_display(value, kind, athlete_units) —
  single converter for six kinds (distance / elevation / elevation_per_distance /
  weight / height / speed), null-safe, idempotent on metric (just rounds);
  _refresh_terrain_display(ts, athlete_units) — recomputes display sub-objects on
  copy-forward terrain caches (recent_activities terrain copy-forward + routes.json
  attachment-id cache) so a unit-pref change picks up next sync without invalidating
  the expensive trackpoint analysis. Sites: athlete_profile.display.height,
  current_status.current_metrics.display.weight, recent_activities[].display.{distance,
  elevation, avg_speed, max_speed}, terrain_summary.display.{total_distance,
  total_elevation, elevation_per_distance} + climbs[]/descents[].display.{position,
  distance, elevation} (recent_activities and routes.json — same code path via
  _analyze_terrain), summary.by_activity_type[].display.distance,
  wellness_data[].display.weight, history.json daily_90d/weekly_180d[].display.weight,
  monthly_*y[].display.avg_weight (aggregate naming preserved),
  race_calendar.all_races[].display.distance. Sustainability profile weight_kg
  deliberately stays canonical-only (calculation input for W/kg, not user-facing).
  Existing per-activity unit siblings (avg_speed_unit/max_speed_unit/avg_temp_unit/
  wind_speed_unit) and weather_summary.units block left as-is — additive layer, not
  replacement; SECTION_11.md v11.40 documents the layering.

Version 3.108 - Conservative error classification for intervals/streams/terrain fetchers:
  resolves v3.107 TODO. _fetch_activity_intervals, _fetch_activity_streams, and
  _fetch_terrain_streams now return (status, payload) tuples: terminal_error for HTTP
  404/410 only, transient for everything else (5xx, 429, all other 4xx incl. 401/403,
  network, timeout, parse, shape). Caller skips the cache write on transient — activity
  stays out of cached_ids and is retried next sync. Pre-3.108 streams/intervals caught
  all exceptions as []/{}, so a transient hiccup wrote a partial entry that locked out
  valid DFA/interval data forever. Conservative {404, 410} whitelist prevents auth or
  config glitches (401, 403) from permanently marking activities as failed. Terrain 4xx
  branch narrowed from broad-4xx-terminal to the same whitelist. Schema unchanged.

Version 3.107 - Completed-Activity Terrain & Weather: terrain_summary and weather_summary
  blocks embedded on outdoor activities in recent_activities[]. State-on-record (no new
  files) — sync.py loads its own previous latest.json at start of each run and copies
  forward; presence of terrain_summary or a terminal terrain_status IS the "already
  pulled" signal. Indoor activities have no field at all (type is the indoor signal).
  New _fetch_terrain_streams returns (status, payload) with terminal/transient
  classification (5xx/429/network NOT cached). latlng dual-array gotcha: Intervals stores
  lat in data and lng in data2 — NOT Strava's paired [lat, lng]. max_grade_pct now tracks
  max abs grade across all 200m chunks rather than detected-climbs-only — earlier impl
  reported 0.0 on rolling routes whose kickers didn't cross the sustained-climb threshold.
  Smoothed-pipeline attenuates peak gradients (12-15% real reads as 6-8%); SECTION_11
  max_grade_pct >= 8 trigger calibrated to this scale. weather_summary uses stable keys
  plus a units sub-block; athlete unit settings fetched once per sync. weather_status
  re-evaluated every sync (unlike terrain) since Intervals can compute weather
  minutes-to-hours after upload. New helpers: _compute_grade_distribution,
  _streams_to_trackpoints, _fetch_terrain_streams, _athlete_units_from_dict,
  _load_previous_latest, _build_terrain_for_activity, _build_weather_for_activity.
  Companion: examples/agentic/pull.py read-only streams/units fetcher.

Version 3.106 - has_intervals semantics fix: has_intervals is now true only when at least
  one interval segment is type=="WORK". Pre-existing bug: a non-empty intervals list was
  treated as structured, but Intervals.icu emits a single whole-session RECOVERY placeholder
  on unstructured endurance rides. Live v3.105 test across 62 activities showed 9 false
  positives (SkiErg, virtual endurance) vs 3 true RECOVERY,WORK structures. This realizes
  the v3.101 intent ("narrowed to structured segments only") which never took effect at the
  check level. has_dfa and intervals collection logic unchanged — only the downstream flag
  is tightened.

Version 3.105 - Effort Response Signal: new effort_response key on every recent_activities[]
  entry. Deterministic classifier mapping session IF (icu_intensity) against reported RPE
  (icu_rpe) through the v11.34 RPE Expectation Bands. Values: "positive" (RPE below band —
  fitness/freshness tell), "neutral" (RPE within band), "negative" (RPE above band —
  fatigue/under-recovery tell), null when IF or RPE absent, RPE <= 0, or IF < 0.65 (out of
  band coverage — recovery/aborted sessions are a deliberate gap, not missing data). Session
  IF used by design; matches whole-session RPE the athlete actually logs, and work-portion
  IF from intervals.json is available for case-by-case inspection but not the field value.
  icu_intensity is stored as percentage (0-100+); classifier normalizes to decimal at entry
  to match the canonical band table in SECTION_11.md §RPE Expectation Bands. Interpretive
  overlay — does NOT alter Feel/RPE Override rules (v11.14) and does NOT enter the
  readiness P0-P3 ladder.

Version 3.104 - Aggregate Durability reliability gate: alarm (28d mean > 5%) now requires
  qualifying_sessions_28d >= 5 before firing; declining warning (7d > 28d by > 2%) now
  requires qualifying_sessions_7d >= 3 AND qualifying_sessions_28d >= 5. Below gate, metrics
  stay visible in capability.durability but no alert fires. Two new fields on the durability
  object: reliability_limited (bool, true when N28<5 or N7<3) and reliability_note (string
  with both N values and both minimums, null when unlimited). The high_drift_count_7d >= 3
  warning is count-based and untouched. Filter criteria (VI <= 1.05, >= 90min) unchanged —
  this is a sample-size safeguard, not a metric redefinition. Addresses GitHub issue #11.

Version 3.103 - Athlete profile + notes + per-field unit labels: new top-level athlete_profile
  block in latest.json (date_of_birth, derived age, height_m, sex, location, timezone,
  platform_activated, derived years_on_platform) sourced from the existing athlete endpoint
  call — zero new API calls. New top-level athlete_notes block (raw string passthrough of
  icu_notes; raw form chosen to keep the change minimal — restructure expected when mini-
  dossier work lands). Per-field unit labels added to recent_activities entries:
  avg_temp_unit ("C"/"F" from athlete.fahrenheit), wind_speed_unit (MPS/KPH/MPH from
  athlete.wind_speed enum, passthrough), avg_speed_unit and max_speed_unit (hardcoded
  "KPH" — sync.py converts m/s → km/h unconditionally at format time, label reflects the
  emitted value, not user preference; a US user gets KPH regardless of account setting,
  which is the current latent behavior the label now surfaces). Sibling-field form chosen
  over nested {value, unit} object — additive, non-breaking for existing consumers reading
  these as scalars. New helpers _years_since() (ISO YYYY-MM-DD → complete years to today,
  null-safe; serves both age-from-DOB and tenure-from-activation) and _compose_location()
  (joins city/state/country with .strip() to handle Intervals.icu trailing-space data,
  returns null when all parts empty). athlete_profile fields are informational; do NOT
  enter readiness P0–P3 logic, threshold computation, or any numeric coaching pathway.
  icu_api_key is in the raw athlete dict response — explicit-allow extraction pattern
  preserved; never serialize the raw athlete dict.

Version 3.102 - Phase detection fixes: corrected three independent bugs causing in-Build weeks
  to misclassify as Base on Mon/Tue after a deload→Build cycle. (1) ctl_slope was a 2-point chord
  divided by len(values) instead of (n-1) and included the in-progress current week's partial
  mid-day CTL — replaced with statistics.linear_regression over finalized weeks (chord-over-(n-1)
  fallback for Python <3.10). (2) Build/Base scorer used hard_sessions_planned (current week
  remainder only), never merging completed-so-far with planned-remaining — added
  current_week_hard_days_completed and current_week_hard_days_total on stream_2; scorer now
  reads the merged total. (3) plan_coverage_* denominator was hard-coded expected_sessions=5,
  producing values up to 2.6 for athletes training 12-17 sessions/week — now derives from rolling
  4-week mean activity_count over finalized weeks (fallback 5). New is_backfill flag on
  _phase_stream1_features and _detect_phase_v2 controls whether weekly_rows[-1] is sliced off
  (live, in-progress week excluded) or kept (backfill, target week sits at [-1]). History
  regen loop now skips the in-progress current week entirely. Live weekly_rows build extended
  to include activity_count per row (was history-only before).

Version 3.101 - has_dfa split + dfa_summary: new has_dfa boolean on recent_activities[] in
  latest.json, independent from has_intervals. has_intervals semantics narrowed to structured
  segments only — a steady Z2 ride with AlphaHRV now reports has_intervals: false, has_dfa: true
  (previously the latter overloaded the former). New compact dfa_summary block attached when
  has_dfa: true AND quality.sufficient: true — fields: avg, dominant_band (max-pct, alphabetical
  tiebreak), tiz_pct (4 bands), valid_pct, sufficient, plus optional drift_delta/drift_interpretable
  and lt1/lt2 watts/hr (omitted when underlying data absent — never null-filled). Lets the AI
  write post-workout DFA commentary from latest.json alone for the common case. quality.sufficient
  tightened: previously duration-only (>=20 min valid); now also requires valid_pct >= 70%. New
  constant DFA_SUFFICIENT_MIN_VALID_PCT = 70.0. Excludes noisy AlphaHRV sessions that previously
  passed the duration gate (pre-existing latent bug). New helper _build_dfa_summary() — pure
  extractor, no computation, single source of truth shared with capability summary.

Version 3.100 - DFA power calibration indoor/outdoor split: trailing_by_sport.cycling lt1/lt2
  estimates now split watts by environment (watts_outdoor, watts_indoor — always present, null
  when no qualifying sessions). HR stays pooled. Per-environment n_sessions for depth assessment.
  Shared _is_indoor_cycling() resolver (VirtualRide = indoor) replaces inline checks.
  Non-cycling sports unchanged. Activity name anonymization removed — names pass through as-is
  for coaching context (route identification, terrain association). athlete_id always redacted.

Version 3.99–3.96 — DFA a1 Protocol (per-session dfa block, dfa_a1_profile, streams fetcher, 14d retention); schema rename derived_metrics.polarisation_index → easy_time_ratio; readiness signal hygiene (low-side ACWR removed, RI 2-day persistence, ACWR boundary unification, recovery_index_yesterday); course character fix (elevation_per_km only, climb-category upgrade retained).

Version 3.95–3.88 — Polyline + event metadata; phase detection live weekly rows; Route & Terrain Intelligence (GPX/TCX → routes.json); local-sync auto-clear on script change; Sustainability Profile (per-sport power/HR for race estimation); sleep signal simplified to hours-only; phase detection current-week runtime overlay; HR Curve Delta (4 anchor durations, cross-sport).

Version 3.87–3.85 — Power curve delta, primary sport TSS filtering for phase detection, wellness field expansion
Version 3.84–3.80 — Activity description passthrough, per-sport zone preference, interval-level data, feel removed from readiness, orphan cleanup
Versions 3.7–3.79 — Phase detection v2, readiness decision, HRRc, week alignment, local sync pipeline, hash manifest, feel/RPE fix
Versions 3.3.0–3.6.5 — EF tracking, HR zone fallback, race calendar, durability, TID, alerts, history.json, smart fitness metrics
"""

import requests
import json
import os
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import base64
import math
import statistics
import hashlib
import zipfile
import tempfile
import shutil
import atexit
from collections import defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET


class IntervalsSync:
    """Sync Intervals.icu data to GitHub repository or local file"""
    
    INTERVALS_BASE_URL = "https://intervals.icu/api/v1"
    GITHUB_API_URL = "https://api.github.com"
    FTP_HISTORY_FILE = "ftp_history.json"
    HISTORY_FILE = "history.json"
    UPSTREAM_REPO = "CrankAddict/section-11"
    CHANGELOG_FILE = "changelog.json"
    VERSION = "3.112"
    INTERVALS_FILE = "intervals.json"
    ROUTES_FILE = "routes.json"

    # Sport families eligible for interval-level data extraction.
    # Only structured sessions in these families are worth fetching
    # per-interval detail for. Walk, strength, yoga, other excluded.
    INTERVAL_SPORT_FAMILIES = {"cycling", "run", "ski", "rowing", "swim"}
    INTERVAL_SCAN_HOURS = 72    # Only scan recent activities for new intervals
    INTERVAL_RETENTION_DAYS = 14  # Keep cached intervals for 14 days (DFA drift analysis window)

    # --- DFA a1 Protocol (v3.99) ---
    # Per-session DFA a1 rollups computed from streams when AlphaHRV Connect IQ field
    # has written to the FIT and Intervals.icu surfaces dfa_a1 + artifacts streams.
    # Threshold mapping (1.0 / 0.5) is cycling-validated (Rowlands 2017, Gronwald 2020,
    # Mateo-March 2023). Other sports get rollups but validated=False.
    DFA_LT1 = 1.0                       # DFA a1 above this = below LT1 (true aerobic)
    DFA_LT2 = 0.5                       # DFA a1 below this = above LT2 (supra-threshold)
    DFA_LT1_BAND = 0.05                 # crossing window for LT1 estimate: 0.95-1.05
    DFA_LT2_BAND = 0.05                 # crossing window for LT2 estimate: 0.45-0.55
    DFA_MIN_CROSSING_DWELL_SECS = 60    # min seconds in crossing band to emit threshold estimate
    DFA_ARTIFACT_MAX_PCT = 5.0          # drop seconds where artifacts % exceeds this
    DFA_MIN_VALID_VALUE = 0.01          # exclude AlphaHRV sentinel zeros
    DFA_MIN_DURATION_SECS = 1200        # 20 min minimum valid data for sufficient=True
    DFA_SUFFICIENT_MIN_VALID_PCT = 70.0 # min valid_pct for sufficient=True (excludes noisy AlphaHRV sessions)
    DFA_DRIFT_INTERPRETABLE_MAX_LT2_PCT = 15.0  # if >15% time above LT2, drift is structural noise
    DFA_TRAILING_WINDOW_N = 7           # latest N AlphaHRV sessions for trailing window (≥6 needed for 'high' confidence)
    DFA_VALIDATED_SPORTS = {"cycling"}  # sports where 1.0/0.5 mapping is literature-validated

    # Sport family mapping for per-sport monotony calculation
    # Multi-sport athletes get inflated total monotony when cross-training
    # adds a consistent TSS floor across days. Per-sport monotony isolates
    # the actual load variation within each modality.
    SPORT_FAMILIES = {
        "Ride": "cycling",
        "VirtualRide": "cycling",
        "MountainBikeRide": "cycling",
        "GravelRide": "cycling",
        "EBikeRide": "cycling",
        "VirtualSki": "ski",
        "NordicSki": "ski",
        "Walk": "walk",
        "Hike": "walk",
        "Run": "run",
        "VirtualRun": "run",
        "TrailRun": "run",
        "Swim": "swim",
        "Rowing": "rowing",
        "WeightTraining": "strength",
        "Yoga": "other",
        "Workout": "other",
    }
    
    # Activity types that may contain location data in their name
    OUTDOOR_TYPES = {"Ride", "MountainBikeRide", "GravelRide", "EBikeRide",
                     "Run", "TrailRun", "NordicSki", "Walk", "Hike"}
    
    # Indoor cycling detection — shared resolver for DFA profile, sustainability profile, etc.
    INDOOR_CYCLING_TYPES = {"VirtualRide"}

    @classmethod
    def _is_indoor_cycling(cls, activity_type: str) -> bool:
        """True when activity_type represents an indoor cycling session."""
        return activity_type in cls.INDOOR_CYCLING_TYPES

    # Training week start day (Python weekday: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6)
    # Default Monday (ISO). Override via .sync_config.json, WEEK_START env var, or --week-start CLI arg.
    WEEK_START_DAY = 0
    
    # --- Sustainability Profile (v3.91) ---
    # Race estimation lookup table: what power/HR is sustainable at each duration?
    SUSTAINABILITY_WINDOW_DAYS = 42
    
    # Per-sport anchor durations (seconds). Cycling covers long events; SkiErg/rowing are shorter.
    SUSTAINABILITY_ANCHORS = {
        "cycling": {"300s": 300, "600s": 600, "1200s": 1200, "1800s": 1800, "3600s": 3600, "5400s": 5400, "7200s": 7200},
        "ski":     {"60s": 60, "120s": 120, "300s": 300, "600s": 600, "1200s": 1200, "1800s": 1800},
        "rowing":  {"60s": 60, "120s": 120, "300s": 300, "600s": 600, "1200s": 1200, "1800s": 1800},
    }
    
    # Coggan duration factors — midpoints of published ranges. Cycling only.
    # Source: Allen & Coggan, Training and Racing with a Power Meter (3rd ed.)
    # Sustainable power as fraction of FTP by duration.
    COGGAN_DURATION_FACTORS = {
        300:  1.06,   # 5min:  ~106% FTP (range 100-112%)
        600:  0.97,   # 10min: ~97% FTP (range 94-100%)
        1200: 0.93,   # 20min: ~93% FTP (range 91-95%)
        1800: 0.90,   # 30min: ~90% FTP (range 88-93%)
        3600: 0.86,   # 60min: ~86% FTP (range 83-90%)
        5400: 0.82,   # 90min: ~82% FTP (range 78-85%)
        7200: 0.78,   # 2h:    ~78% FTP (range 75-82%)
    }
    
    # Activity types for sport-filtered power-curves fetch
    SUSTAINABILITY_POWER_TYPES = {
        "cycling": ["Ride", "VirtualRide"],
        "ski":     ["NordicSki", "VirtualSki"],
        "rowing":  ["Rowing"],
    }
    
    # Activity types for sport-filtered hr-curves fetch
    SUSTAINABILITY_HR_TYPES = {
        "cycling": ["Ride", "VirtualRide"],
        "ski":     ["NordicSki", "VirtualSki"],
        "rowing":  ["Rowing"],
    }
    
    def __init__(self, athlete_id: str, intervals_api_key: str, github_token: str = None, 
                 github_repo: str = None, debug: bool = False, week_start_day: int = None,
                 zone_preference: dict = None):
        self.athlete_id = athlete_id
        self.intervals_auth = base64.b64encode(f"API_KEY:{intervals_api_key}".encode()).decode()
        self.github_token = github_token
        self.github_repo = github_repo
        self.debug = debug
        self.script_dir = Path(__file__).parent
        self.data_dir = Path.cwd()  # Data files (history.json, ftp_history.json) write to caller's working directory
        self.week_start_day = week_start_day if week_start_day is not None else self.WEEK_START_DAY
        self.zone_preference = zone_preference or {}  # {"run": "hr", "cycling": "power", ...}
        self._cached_script_hash = None  # lazy-computed
    
    @property
    def script_hash(self) -> str:
        """SHA256 of sync.py itself. Used to invalidate cached files on any code change."""
        if self._cached_script_hash is None:
            script_path = Path(__file__).resolve()
            h = hashlib.sha256()
            with open(script_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    h.update(chunk)
            self._cached_script_hash = h.hexdigest()[:12]  # short hash, sufficient for change detection
        return self._cached_script_hash
    
    def _intervals_get(self, endpoint: str, params: Dict = None) -> Dict:
        """Fetch from Intervals.icu API"""
        if endpoint:
            url = f"{self.INTERVALS_BASE_URL}/athlete/{self.athlete_id}/{endpoint}"
        else:
            url = f"{self.INTERVALS_BASE_URL}/athlete/{self.athlete_id}"
        headers = {
            "Authorization": f"Basic {self.intervals_auth}",
            "Accept": "application/json"
        }
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def _get_activity_messages(self, activity_id: str) -> List[str]:
        """Fetch messages/notes for a completed activity. Returns list of text strings."""
        url = f"{self.INTERVALS_BASE_URL}/activity/{activity_id}/messages"
        headers = {
            "Authorization": f"Basic {self.intervals_auth}",
            "Accept": "application/json"
        }
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            messages = response.json()
            if isinstance(messages, list):
                return [m.get("content", m.get("text", "")) for m in messages if (m.get("content") or m.get("text", "")).strip()]
            return []
        except Exception:
            return []
    
    def _fetch_activity_intervals(self, activity_id: str) -> tuple:
        """
        Fetch interval segments for a single activity.

        Distinguishes terminal from transient errors so the caller can decide
        whether to write the cache entry (terminal: definitive answer, cache it
        and skip on future syncs) or skip the write (transient: retry next sync).

        Returns (status, payload):
            ("ok", icu_intervals_list)  — 200 with non-empty icu_intervals
            ("no_data", [])             — 200 with empty/missing icu_intervals
                                          (legitimate unstructured ride)
            ("terminal_error", "http_NNN") — 404, 410 (resource genuinely gone)
            ("transient", reason_str)   — everything else: 5xx, 429, all other
                                          4xx (incl. 401/403 — auth/config flakes
                                          must NOT become permanent cache truth),
                                          network, timeout, parse error,
                                          unexpected response shape
        """
        url = f"{self.INTERVALS_BASE_URL}/activity/{activity_id}"
        headers = {
            "Authorization": f"Basic {self.intervals_auth}",
            "Accept": "application/json"
        }
        try:
            response = requests.get(url, headers=headers, params={"intervals": "true"}, timeout=30)
        except requests.exceptions.Timeout:
            return ("transient", "timeout")
        except requests.exceptions.RequestException as e:
            return ("transient", f"network: {str(e)[:80]}")

        status_code = response.status_code
        if status_code == 200:
            try:
                data = response.json()
            except ValueError:
                return ("transient", "parse_error")
            if not isinstance(data, dict):
                return ("transient", "unexpected_shape")
            intervals = data.get("icu_intervals", [])
            if not isinstance(intervals, list):
                return ("transient", "unexpected_shape")
            if not intervals:
                return ("no_data", [])
            return ("ok", intervals)
        elif status_code in (404, 410):
            return ("terminal_error", f"http_{status_code}")
        else:
            # Conservative: all other non-2xx (incl. 401/403/5xx/429) treated as
            # transient. Better to retry than permanently cache an auth/config flake.
            return ("transient", f"http_{status_code}")

    def _fetch_activity_streams(self, activity_id: str, types: List[str]) -> tuple:
        """
        Fetch per-second streams for a single activity.

        Generic streams fetcher for any rollup metric that needs second-by-second data.
        Distinguishes terminal from transient errors so the caller can decide whether
        to write a cache entry (terminal: definitive, skip on future syncs) or skip
        the write (transient: retry next sync).

        Returns (status, payload):
            ("ok", streams_dict)        — 200 with at least one requested stream
                                          populated; dict keyed by stream type,
                                          value is the data list
            ("no_data", {})             — 200 but none of the requested streams
                                          present (legitimate — e.g., no AlphaHRV
                                          Connect IQ field installed, sourced via
                                          Strava which strips dev fields)
            ("terminal_error", "http_NNN") — 404, 410 (resource genuinely gone)
            ("transient", reason_str)   — everything else: 5xx, 429, all other
                                          4xx (incl. 401/403 — auth/config flakes
                                          must NOT become permanent cache truth),
                                          network, timeout, parse error,
                                          unexpected response shape

        Note on cache invalidation: streams are fetched once per activity. If the
        underlying FIT is reprocessed in AlphaHRV's mobile app and re-uploaded,
        the cached rollup will be stale. Rare in practice; workaround is to delete
        intervals.json.
        """
        url = f"{self.INTERVALS_BASE_URL}/activity/{activity_id}/streams"
        headers = {
            "Authorization": f"Basic {self.intervals_auth}",
            "Accept": "application/json"
        }
        try:
            response = requests.get(url, headers=headers, timeout=30)
        except requests.exceptions.Timeout:
            return ("transient", "timeout")
        except requests.exceptions.RequestException as e:
            return ("transient", f"network: {str(e)[:80]}")

        status_code = response.status_code
        if status_code == 200:
            try:
                data = response.json()
            except ValueError:
                return ("transient", "parse_error")
            if not isinstance(data, list):
                return ("transient", "unexpected_shape")
            wanted = set(types)
            out = {}
            for s in data:
                stype = s.get("type")
                if stype in wanted:
                    sdata = s.get("data")
                    if isinstance(sdata, list):
                        out[stype] = sdata
            if not out:
                return ("no_data", {})
            return ("ok", out)
        elif status_code in (404, 410):
            return ("terminal_error", f"http_{status_code}")
        else:
            # Conservative: all other non-2xx (incl. 401/403/5xx/429) treated as
            # transient. Better to retry than permanently cache an auth/config flake.
            return ("transient", f"http_{status_code}")

    def _fetch_terrain_streams(self, activity_id: str) -> tuple:
        """
        Fetch latlng + altitude streams for terrain analysis.
        
        Distinguishes terminal from transient errors so the caller can decide
        whether to write a terminal status (skip on future syncs) or leave
        unmarked (retry on next sync).
        
        The latlng stream uses Intervals' dual-array shape (data=lat, data2=lng)
        which the generic fetcher discards, so this terrain-specific fetcher
        returns the raw stream list rather than reusing _fetch_activity_streams.
        
        Returns (status, payload):
            ("ok", streams_list)         — 200 with usable streams
            ("no_gps", None)             — 200 but no latlng stream present
            ("no_elevation", streams_list) — 200 with latlng but no altitude
                                            (caller may still want trackpoints)
            ("terminal_error", "http_NNN") — 404, 410 (resource genuinely gone)
            ("transient", reason_str)    — everything else: 5xx, 429, all other
                                           4xx (incl. 401/403 — auth/config flakes
                                           must NOT become permanent cache truth),
                                           network, timeout, parse error,
                                           unexpected response shape
        """
        url = f"{self.INTERVALS_BASE_URL}/activity/{activity_id}/streams.json?types=time,distance,altitude,latlng"
        headers = {
            "Authorization": f"Basic {self.intervals_auth}",
            "Accept": "application/json"
        }
        try:
            response = requests.get(url, headers=headers, timeout=30)
        except requests.exceptions.Timeout:
            return ("transient", "timeout")
        except requests.exceptions.RequestException as e:
            return ("transient", f"network: {str(e)[:80]}")
        
        status_code = response.status_code
        if status_code == 200:
            try:
                data = response.json()
            except ValueError:
                return ("transient", "parse_error")
            if not isinstance(data, list):
                return ("transient", "unexpected_shape")
            latlng_stream = next((s for s in data if s.get("type") == "latlng"), None)
            altitude_stream = next((s for s in data if s.get("type") == "altitude"), None)
            if not latlng_stream:
                return ("no_gps", None)
            lat_arr = latlng_stream.get("data") or []
            lng_arr = latlng_stream.get("data2") or []
            valid_pairs = sum(1 for la, ln in zip(lat_arr, lng_arr) if la is not None and ln is not None)
            if valid_pairs < 10:
                return ("no_gps", None)
            if not altitude_stream or not (altitude_stream.get("data") or []):
                return ("no_elevation", data)
            return ("ok", data)
        elif status_code in (404, 410):
            return ("terminal_error", f"http_{status_code}")
        else:
            # Conservative: all other non-2xx (incl. 401/403/5xx/429) treated as
            # transient. Better to retry than permanently cache an auth/config flake.
            return ("transient", f"http_{status_code}")

    def _athlete_units_from_dict(self, athlete: Dict) -> Dict[str, str]:
        """
        Extract the athlete's unit preferences from an already-fetched athlete dict.
        
        Returns a dict mapping concept to unit code:
            {
              "wind":     "m/s" | "km/h" | "mph",
              "temp":     "c" | "f",
              "rain":     "mm" | "in",
              "distance": "metric" | "imperial",
              "weight":   "kg" | "lb",
              "height":   "cm" | "in"
            }
        
        Used to populate the `units` block on weather_summary so the data values
        can stay in stable keys (e.g. avg_wind_speed) regardless of athlete
        settings, with the unit resolved separately. Falls back to all-metric
        defaults if the input dict is missing or empty.
        """
        defaults = {
            "wind": "m/s", "temp": "c", "rain": "mm",
            "distance": "metric", "weight": "kg", "height": "cm"
        }
        if not athlete:
            return defaults
        # Map Intervals settings to our normalized codes.
        wind_map = {"MPS": "m/s", "KPH": "km/h", "MPH": "mph"}
        rain_map = {"MM": "mm", "IN": "in"}
        return {
            "wind": wind_map.get(athlete.get("wind_speed"), defaults["wind"]),
            "temp": "f" if athlete.get("fahrenheit") else "c",
            "rain": rain_map.get(athlete.get("rain"), defaults["rain"]),
            "distance": "imperial" if athlete.get("measurement_preference") not in ("meters", None) else "metric",
            "weight": "lb" if athlete.get("weight_pref_lb") else "kg",
            "height": "in" if athlete.get("height_units") == "IN" else "cm"
        }

    def _to_display(self, value: Optional[float], kind: str,
                    athlete_units: Optional[Dict[str, str]] = None) -> Optional[Dict]:
        """
        Convert a canonical-metric value into a display-ready {value, unit} pair
        based on the athlete's Intervals.icu unit preferences.
        
        Canonical (input) units are fixed by sync.py — calculations always use these:
          - distance / position / total_distance: km
          - elevation / total_elevation: m (positive or signed)
          - elevation_per_distance: m/km
          - weight: kg
          - height: m
          - speed: km/h
        
        Display blocks let the AI narrate without doing unit math. Metric athletes
        get the same numeric value with a metric unit code; imperial athletes get
        the converted value with an imperial unit code. The conversion is a no-op
        on metric (input == output, just rounded).
        
        kinds: "distance" | "elevation" | "elevation_per_distance" |
               "weight"   | "height"    | "speed"
        
        Returns {"value": <rounded float>, "unit": <code>} — or None if value is None.
        Unit codes (display, lowercase): km/mi, m/ft, m/km, ft/mi, kg/lb, cm/in, km/h, mph.
        """
        if value is None:
            return None
        units = athlete_units or {}
        
        if kind == "distance":
            if units.get("distance") == "imperial":
                return {"value": round(value * 0.621371, 2), "unit": "mi"}
            return {"value": round(value, 2), "unit": "km"}
        
        if kind == "elevation":
            if units.get("distance") == "imperial":
                return {"value": round(value * 3.28084), "unit": "ft"}
            return {"value": round(value), "unit": "m"}
        
        if kind == "elevation_per_distance":
            # m/km → ft/mi: m * 3.28084 / (km * 0.621371) = m/km * 5.28
            if units.get("distance") == "imperial":
                return {"value": round(value * 5.28), "unit": "ft/mi"}
            return {"value": round(value), "unit": "m/km"}
        
        if kind == "weight":
            if units.get("weight") == "lb":
                return {"value": round(value * 2.20462, 1), "unit": "lb"}
            return {"value": round(value, 1), "unit": "kg"}
        
        if kind == "height":
            # canonical input is meters
            if units.get("height") == "in":
                return {"value": round(value * 39.3701), "unit": "in"}
            return {"value": round(value * 100), "unit": "cm"}
        
        if kind == "speed":
            # canonical input is km/h (sync.py converts m/s → km/h regardless of pref)
            if units.get("distance") == "imperial":
                return {"value": round(value * 0.621371, 1), "unit": "mph"}
            return {"value": round(value, 1), "unit": "km/h"}
        
        return None

    def _refresh_terrain_display(self, terrain_summary: Dict,
                                 athlete_units: Optional[Dict[str, str]] = None) -> Dict:
        """
        Refresh display blocks on a copy-forward terrain_summary using current
        athlete_units. Canonical metric fields (total_distance_km, climbs[].position_km,
        etc.) are preserved verbatim; only the display sub-objects are recomputed.
        
        This lets terrain caches (recent_activities[].terrain_summary copy-forward
        and routes.json attachment-id cache) survive a unit preference change
        without invalidating the expensive trackpoint analysis.
        
        Defensive: if the cached object pre-dates v3.109 and has no display block,
        one is created. If athlete_units is None, the cached display is preserved
        (fall-back to whatever was last written).
        """
        if not isinstance(terrain_summary, dict):
            return terrain_summary
        if athlete_units is None:
            return terrain_summary
        
        out = dict(terrain_summary)  # shallow copy
        out["display"] = {
            "total_distance": self._to_display(out.get("total_distance_km"), "distance", athlete_units),
            "total_elevation": self._to_display(out.get("total_elevation_m"), "elevation", athlete_units),
            "elevation_per_distance": self._to_display(out.get("elevation_per_km"), "elevation_per_distance", athlete_units),
        }
        for key in ("climbs", "descents"):
            segments = out.get(key)
            if not isinstance(segments, list):
                continue
            refreshed = []
            for seg in segments:
                if not isinstance(seg, dict):
                    refreshed.append(seg)
                    continue
                seg_out = dict(seg)
                seg_out["display"] = {
                    "position": self._to_display(seg_out.get("position_km"), "distance", athlete_units),
                    "distance": self._to_display(seg_out.get("distance_km"), "distance", athlete_units),
                    "elevation": self._to_display(seg_out.get("elevation_m"), "elevation", athlete_units),
                }
                refreshed.append(seg_out)
            out[key] = refreshed
        return out

    def _load_previous_latest(self) -> Dict[str, Dict]:
        """
        Read previous latest.json and build an activity-id-keyed lookup dict.
        
        Used as the persistent state for terrain/weather summaries — fields
        already populated on a previous sync are copied forward instead of
        being re-fetched. The presence of `terrain_summary` (or terminal
        `terrain_status`) on a record IS the "already pulled" signal.
        
        Returns a dict mapping str(activity_id) -> {
            "terrain_summary": <dict or absent>,
            "terrain_status":  <str or absent>,
            "terrain_error":   <str or absent>,
            "weather_summary": <dict or absent>
            # weather_status not copied forward — re-evaluated each sync from
            # current activity-list `has_weather` field.
        }
        Empty dict when latest.json is absent (first sync, fresh data dir).
        Activity IDs are normalized to strings to defend against type mismatch
        between dict construction and lookup.
        """
        latest_path = self.data_dir / "latest.json"
        if not latest_path.exists():
            return {}
        try:
            with open(latest_path, 'r') as f:
                data = json.load(f)
        except Exception as e:
            if self.debug:
                print(f"    ⚠️  Could not read previous latest.json: {e}")
            return {}
        
        lookup = {}
        for act in data.get("recent_activities", []):
            act_id = act.get("id")
            if act_id is None:
                continue
            entry = {}
            if "terrain_summary" in act:
                entry["terrain_summary"] = act["terrain_summary"]
            if "terrain_status" in act:
                entry["terrain_status"] = act["terrain_status"]
            if "terrain_error" in act:
                entry["terrain_error"] = act["terrain_error"]
            if "weather_summary" in act:
                entry["weather_summary"] = act["weather_summary"]
            if entry:
                lookup[str(act_id)] = entry
        return lookup

    def _build_terrain_for_activity(self, act: Dict, previous_lookup: Dict[str, Dict],
                                    athlete_units: Optional[Dict[str, str]] = None) -> Dict:
        """
        Resolve terrain fields for one activity per the per-activity decision logic.
        
        Returns a dict of fields to attach to the activity record (may be empty).
        Possible keys in the returned dict: terrain_summary, terrain_status,
        terrain_error.
        
        Decision tree:
          1. activity.type not in OUTDOOR_TYPES        → return {} (no field; type is the indoor signal)
          2. previous has terrain_summary              → copy forward (success, never re-fetch)
          3. previous has terminal terrain_status      → copy forward (no_gps/no_elevation/failed are terminal)
          4. otherwise                                  → fetch streams, classify, attach
                ok            → terrain_summary
                no_gps        → terrain_status="no_gps"
                no_elevation  → terrain_status="no_elevation" (still terminal — won't gain altitude later)
                terminal_error→ terrain_status="failed", terrain_error=<code>
                transient     → return {} (no field written → retry next sync)
        
        athlete_units (v3.109): when provided, fresh terrain analyses get display
        blocks; copy-forward also refreshes display blocks from canonical metric
        fields so a unit-preference change picks up next sync without invalidating
        the (expensive) terrain cache.
        """
        act_type = act.get("type", "")
        if act_type not in self.OUTDOOR_TYPES:
            return {}
        
        act_id = act.get("id")
        if act_id is None:
            return {}
        prev = previous_lookup.get(str(act_id), {})
        
        # Copy-forward: success — refresh display blocks from canonical fields
        if "terrain_summary" in prev:
            return {"terrain_summary": self._refresh_terrain_display(prev["terrain_summary"], athlete_units)}
        # Copy-forward: terminal non-success
        prev_status = prev.get("terrain_status")
        if prev_status in {"no_gps", "no_elevation", "failed"}:
            out = {"terrain_status": prev_status}
            if "terrain_error" in prev:
                out["terrain_error"] = prev["terrain_error"]
            return out
        
        # Not yet attempted: fetch and classify
        status, payload = self._fetch_terrain_streams(act_id)
        if status == "ok":
            trackpoints = self._streams_to_trackpoints(payload)
            if len(trackpoints) < 2:
                return {"terrain_status": "no_gps"}
            # Defensive: even when _fetch_terrain_streams reports the altitude
            # array exists, individual values may all be None (sensor failure
            # mid-ride, malformed upload). _streams_to_trackpoints filters
            # None elevations per-point. If no trackpoint ended up with an
            # `ele` key, we'd otherwise produce a misleading flat summary.
            if not any("ele" in tp for tp in trackpoints):
                return {"terrain_status": "no_elevation"}
            summary = self._analyze_terrain(
                trackpoints, source="activity_streams", include_polyline=False,
                athlete_units=athlete_units
            )
            if summary is None:
                # Final guard — _analyze_terrain returns None for degenerate
                # paths beyond the all-None case caught above.
                return {"terrain_status": "no_elevation"}
            return {"terrain_summary": summary}
        elif status == "no_gps":
            return {"terrain_status": "no_gps"}
        elif status == "no_elevation":
            # Has GPS but no altitude. Coach can't reason about climbs/grade,
            # so we mark terminal rather than emit a misleading "flat" summary.
            return {"terrain_status": "no_elevation"}
        elif status == "terminal_error":
            return {"terrain_status": "failed", "terrain_error": payload}
        else:
            # transient — write nothing, retry next sync
            if self.debug:
                print(f"    ⚠️  Terrain fetch transient failure for {act_id}: {payload} (will retry)")
            return {}

    def _build_weather_for_activity(self, act: Dict, previous_lookup: Dict[str, Dict],
                                    units: Dict[str, str]) -> Dict:
        """
        Resolve weather fields for one activity.
        
        Weather is provided by Intervals on the activity-list response (no extra
        API call), gated on `has_weather: true`. Unlike terrain, weather has NO
        terminal failure mode — `weather_status: "unavailable"` is never copied
        forward, because Intervals may compute weather later and we want to
        re-evaluate every sync.
        
        Decision tree:
          1. activity.type not in OUTDOOR_TYPES → return {} (no field)
          2. previous has weather_summary       → copy forward (one less rebuild)
          3. has_weather true                   → build summary from current data
          4. else                               → weather_status="unavailable"
        
        Note: step 2 is purely an optimization (avoid rebuilding the summary
        every sync). Since Intervals' weather fields don't change once set,
        the copy-forward result is identical to a fresh build.
        """
        act_type = act.get("type", "")
        if act_type not in self.OUTDOOR_TYPES:
            return {}
        
        act_id = act.get("id")
        prev = previous_lookup.get(str(act_id), {}) if act_id is not None else {}
        if "weather_summary" in prev:
            return {"weather_summary": prev["weather_summary"]}
        
        if not act.get("has_weather"):
            return {"weather_status": "unavailable"}
        
        # Build summary from existing fields on the activity list response.
        # Stable keys + explicit `units` block (no dynamic suffixes).
        summary = {
            "source": "intervals_open_meteo",
            "units": {
                "wind": units.get("wind", "m/s"),
                "temp": units.get("temp", "c"),
                "rain": units.get("rain", "mm"),
            },
            "avg_wind_speed": act.get("average_wind_speed"),
            "avg_wind_gust": act.get("average_wind_gust"),
            "prevailing_wind_deg": act.get("prevailing_wind_deg"),
            "headwind_pct": act.get("headwind_percent"),
            "tailwind_pct": act.get("tailwind_percent"),
            "avg_temp": act.get("average_weather_temp"),
            "avg_temp_device": act.get("average_temp"),
            "avg_feels_like": act.get("average_feels_like"),
            "min_feels_like": act.get("min_feels_like"),
            "max_feels_like": act.get("max_feels_like"),
            "min_temp": act.get("min_weather_temp"),
            "max_temp": act.get("max_weather_temp"),
            "clouds_pct": act.get("average_clouds"),
            "rain": act.get("max_rain"),
            "snow": act.get("max_snow"),
        }
        # Round numerics for cleaner JSON; preserve None values.
        for k, v in list(summary.items()):
            if isinstance(v, float):
                summary[k] = round(v, 2)
        return {"weather_summary": summary}

    def _compute_dfa_block(self, streams: Dict[str, List]) -> Optional[Dict]:
        """
        Compute per-session DFA a1 rollup from raw streams.

        Inputs: streams dict from _fetch_activity_streams, expected keys:
          dfa_a1, artifacts, heartrate, watts (heartrate/watts optional but degrade output)

        Returns the dfa block dict, or None if dfa_a1 stream is absent entirely
        (i.e. AlphaHRV did not record on this activity).

        When dfa_a1 IS present but data is insufficient to interpret (too short,
        too noisy), returns a block with quality.sufficient=False so the AI can
        distinguish "no AlphaHRV" (None → no dfa key in output) from "AlphaHRV
        ran but unusable" (block present, sufficient=False).

        Filtering rules (in order):
          1. Drop seconds where dfa_a1 < DFA_MIN_VALID_VALUE (AlphaHRV sentinel zeros)
          2. Drop seconds where artifacts > DFA_ARTIFACT_MAX_PCT (5%, Altini convention)
        Both filters applied jointly to dfa_a1, hr, watts so they stay aligned.
        """
        dfa_stream = streams.get("dfa_a1")
        if not dfa_stream:
            return None  # no AlphaHRV recording on this activity

        artifacts_stream = streams.get("artifacts") or [0.0] * len(dfa_stream)
        hr_stream = streams.get("heartrate") or [None] * len(dfa_stream)
        watts_stream = streams.get("watts") or [None] * len(dfa_stream)

        # Align all streams to dfa_a1 length (defensive — should already match)
        n = len(dfa_stream)
        if len(artifacts_stream) != n:
            artifacts_stream = (artifacts_stream + [0.0] * n)[:n]
        if len(hr_stream) != n:
            hr_stream = (hr_stream + [None] * n)[:n]
        if len(watts_stream) != n:
            watts_stream = (watts_stream + [None] * n)[:n]

        # Apply filters
        valid_dfa, valid_hr, valid_watts = [], [], []
        artifact_sum = 0.0
        artifact_count = 0
        for i in range(n):
            d = dfa_stream[i]
            a = artifacts_stream[i]
            if a is not None:
                artifact_sum += a
                artifact_count += 1
            if d is None or d < self.DFA_MIN_VALID_VALUE:
                continue
            if a is not None and a > self.DFA_ARTIFACT_MAX_PCT:
                continue
            valid_dfa.append(d)
            valid_hr.append(hr_stream[i])
            valid_watts.append(watts_stream[i])

        valid_secs = len(valid_dfa)
        total_secs = n
        valid_pct = round(100.0 * valid_secs / total_secs, 1) if total_secs else 0.0
        artifact_rate_avg = round(artifact_sum / artifact_count, 2) if artifact_count else None
        sufficient = (
            valid_secs >= self.DFA_MIN_DURATION_SECS
            and valid_pct >= self.DFA_SUFFICIENT_MIN_VALID_PCT
        )

        quality = {
            "valid_secs": valid_secs,
            "total_secs": total_secs,
            "valid_pct": valid_pct,
            "artifact_rate_avg": artifact_rate_avg,
            "sufficient": sufficient,
        }

        if not sufficient:
            # Emit minimal block — AI sees AlphaHRV ran but data unusable
            return {
                "avg": None,
                "p25": None, "p50": None, "p75": None,
                "tiz_below_lt1": None,
                "tiz_lt1_transition": None,
                "tiz_transition_lt2": None,
                "tiz_above_lt2": None,
                "drift": None,
                "lt1_crossing": None,
                "lt2_crossing": None,
                "quality": quality,
            }

        # Sufficient — full rollup
        sorted_dfa = sorted(valid_dfa)
        avg = round(sum(valid_dfa) / valid_secs, 3)
        p25 = round(sorted_dfa[valid_secs // 4], 3)
        p50 = round(sorted_dfa[valid_secs // 2], 3)
        p75 = round(sorted_dfa[(valid_secs * 3) // 4], 3)

        # 4-band TIZ with HR/power cross-references per band
        def _band_stats(predicate):
            secs = 0
            hr_sum, hr_n = 0, 0
            w_sum, w_n = 0, 0
            for i in range(valid_secs):
                if predicate(valid_dfa[i]):
                    secs += 1
                    if valid_hr[i] is not None:
                        hr_sum += valid_hr[i]
                        hr_n += 1
                    if valid_watts[i] is not None:
                        w_sum += valid_watts[i]
                        w_n += 1
            if secs == 0:
                return None
            return {
                "secs": secs,
                "pct": round(100.0 * secs / valid_secs, 1),
                "avg_hr": round(hr_sum / hr_n) if hr_n else None,
                "avg_watts": round(w_sum / w_n) if w_n else None,
            }

        tiz_below_lt1 = _band_stats(lambda d: d > self.DFA_LT1)
        tiz_lt1_transition = _band_stats(lambda d: 0.75 <= d <= self.DFA_LT1)
        tiz_transition_lt2 = _band_stats(lambda d: self.DFA_LT2 <= d < 0.75)
        tiz_above_lt2 = _band_stats(lambda d: d < self.DFA_LT2)

        # Drift: first-third vs last-third of valid data
        third = valid_secs // 3
        if third >= 60:  # need at least 60s per third for meaningful drift
            first_third = valid_dfa[:third]
            last_third = valid_dfa[-third:]
            first_avg = round(sum(first_third) / len(first_third), 3)
            last_avg = round(sum(last_third) / len(last_third), 3)
            drift_delta = round(last_avg - first_avg, 3)
            # Drift is interpretable only on steady-state work — if significant time
            # was spent above LT2, the session has hard intervals and drift is structural
            above_lt2_pct = tiz_above_lt2["pct"] if tiz_above_lt2 else 0.0
            interpretable = above_lt2_pct <= self.DFA_DRIFT_INTERPRETABLE_MAX_LT2_PCT
            drift = {
                "first_third_avg": first_avg,
                "last_third_avg": last_avg,
                "delta": drift_delta,
                "interpretable": interpretable,
            }
        else:
            drift = None

        # LT1 / LT2 crossing-band estimates (the actually-coachable threshold candidates)
        def _crossing_stats(center, band):
            lo, hi = center - band, center + band
            secs = 0
            hr_sum, hr_n = 0, 0
            w_sum, w_n = 0, 0
            for i in range(valid_secs):
                if lo <= valid_dfa[i] <= hi:
                    secs += 1
                    if valid_hr[i] is not None:
                        hr_sum += valid_hr[i]
                        hr_n += 1
                    if valid_watts[i] is not None:
                        w_sum += valid_watts[i]
                        w_n += 1
            if secs < self.DFA_MIN_CROSSING_DWELL_SECS:
                return {"secs_in_band": secs, "avg_hr": None, "avg_watts": None}
            return {
                "secs_in_band": secs,
                "avg_hr": round(hr_sum / hr_n) if hr_n else None,
                "avg_watts": round(w_sum / w_n) if w_n else None,
            }

        lt1_crossing = _crossing_stats(self.DFA_LT1, self.DFA_LT1_BAND)
        lt2_crossing = _crossing_stats(self.DFA_LT2, self.DFA_LT2_BAND)

        return {
            "avg": avg,
            "p25": p25, "p50": p50, "p75": p75,
            "tiz_below_lt1": tiz_below_lt1,
            "tiz_lt1_transition": tiz_lt1_transition,
            "tiz_transition_lt2": tiz_transition_lt2,
            "tiz_above_lt2": tiz_above_lt2,
            "drift": drift,
            "lt1_crossing": lt1_crossing,
            "lt2_crossing": lt2_crossing,
            "quality": quality,
        }

    def _build_dfa_summary(self, dfa_block: Dict) -> Dict:
        """
        Build the compact dfa_summary attached to recent_activities[] in latest.json (v3.100).

        Pure extractor — no computation. All numbers come from _compute_dfa_block output.
        Caller must only invoke this when dfa_block["quality"]["sufficient"] is True;
        the sufficient=False branch of _compute_dfa_block returns all-None tiz_* fields
        and is not summarisable. Per-band None (zero time in band) is handled here as 0.0.
        Optional fields are omitted (not nulled) when their underlying data is absent.
        """
        def _band_pct(name):
            b = dfa_block.get(name)
            return b["pct"] if b else 0.0

        bands = {
            "below_lt1": _band_pct("tiz_below_lt1"),
            "lt1_transition": _band_pct("tiz_lt1_transition"),
            "transition_lt2": _band_pct("tiz_transition_lt2"),
            "above_lt2": _band_pct("tiz_above_lt2"),
        }
        # Dominant band: max pct, alphabetical tiebreak (deterministic, conservative).
        dominant_band = sorted(bands.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

        summary = {
            "avg": dfa_block["avg"],
            "dominant_band": dominant_band,
            "tiz_pct": bands,
            "valid_pct": dfa_block["quality"]["valid_pct"],
            "sufficient": dfa_block["quality"]["sufficient"],
        }

        drift = dfa_block.get("drift")
        if drift is not None and drift.get("delta") is not None:
            summary["drift_delta"] = drift["delta"]
            summary["drift_interpretable"] = drift.get("interpretable", False)

        lt1 = dfa_block.get("lt1_crossing") or {}
        if lt1.get("avg_watts") is not None:
            summary["lt1_watts"] = lt1["avg_watts"]
        if lt1.get("avg_hr") is not None:
            summary["lt1_hr"] = lt1["avg_hr"]

        lt2 = dfa_block.get("lt2_crossing") or {}
        if lt2.get("avg_watts") is not None:
            summary["lt2_watts"] = lt2["avg_watts"]
        if lt2.get("avg_hr") is not None:
            summary["lt2_hr"] = lt2["avg_hr"]

        return summary

    
    def _generate_intervals(self, activities: List[Dict]) -> set:
        """
        Generate intervals.json with incremental caching.
        
        First run (no cache): scans full retention window (14 days) to backfill.
        Subsequent runs: scans recent activities (72h) for new sessions only.
        Fetches per-interval data for new qualifying activities, merges
        with cached data, and purges entries older than 14 days.

        DFA a1 (v3.99): for each new qualifying activity, also fetches streams
        (dfa_a1, artifacts, heartrate, watts) and computes a per-session dfa block.
        Attached to the activity entry as 'dfa' key when AlphaHRV recorded.
        
        Returns set of activity IDs that have interval data (for has_intervals flag).
        """
        now = datetime.now()
        retention_cutoff = (now - timedelta(days=self.INTERVAL_RETENTION_DAYS)).strftime("%Y-%m-%d")
        
        # Load existing cache
        intervals_path = self.data_dir / self.INTERVALS_FILE
        cached = {"activities": []}
        first_run = not intervals_path.exists()
        if not first_run:
            try:
                with open(intervals_path, 'r') as f:
                    cached = json.load(f)
                # Invalidate cache if sync.py changed
                if cached.get("script_hash") != self.script_hash:
                    if self.debug:
                        print(f"    🔄 intervals.json stale (sync.py changed), re-scanning all")
                    cached = {"activities": []}
                    first_run = True
            except Exception as e:
                if self.debug:
                    print(f"    ⚠️  Could not read intervals.json: {e}")
                cached = {"activities": []}
                first_run = True
        
        # First run: backfill full retention window (14 days). Subsequent: scan 72h only.
        if first_run:
            scan_cutoff = retention_cutoff
            print("    First run — scanning 14 days for interval data...")
        else:
            scan_cutoff = (now - timedelta(hours=self.INTERVAL_SCAN_HOURS)).strftime("%Y-%m-%d")
        
        cached_ids = {a["activity_id"] for a in cached.get("activities", [])}
        
        # Filter activities to scan window + sport family whitelist.
        # NOTE (v3.99): interval_summary requirement removed. Pure endurance rides
        # without structured intervals are exactly where DFA a1 is most valuable
        # (steady-state drift detection, LT1 calibration). We attempt both intervals
        # AND streams fetches; entry is emitted if either yields data.
        candidates = []
        for act in activities:
            date_str = act.get("start_date_local", "")[:10]
            if date_str < scan_cutoff:
                continue
            act_type = act.get("type", "")
            family = self.SPORT_FAMILIES.get(act_type)
            if family not in self.INTERVAL_SPORT_FAMILIES:
                continue
            act_id = act.get("id")
            if act_id in cached_ids:
                continue
            candidates.append(act)
        
        # Fetch intervals for new qualifying activities
        new_entries = []
        for act in candidates:
            act_id = act.get("id")
            print(f"    Fetching intervals/streams for {act.get('name', act_id)}...")

            # v3.108: classify fetch outcomes. Transient on either fetcher → skip
            # this activity entirely (no cache write). Activity stays out of
            # cached_ids and is retried on the next sync. Terminal (404/410) and
            # no_data are definitive: cache the entry so we don't keep retrying.
            intervals_status, intervals_payload = self._fetch_activity_intervals(act_id)
            if intervals_status == "transient":
                if self.debug:
                    print(f"    ⚠️  Intervals fetch transient failure for {act_id}: {intervals_payload} (will retry)")
                continue

            streams_status, streams_payload = self._fetch_activity_streams(
                act_id, ["dfa_a1", "artifacts", "heartrate", "watts"]
            )
            if streams_status == "transient":
                if self.debug:
                    print(f"    ⚠️  Streams fetch transient failure for {act_id}: {streams_payload} (will retry)")
                continue

            # Normalize payloads. On no_data/terminal_error, payload is a sentinel
            # ([] / {} / "http_NNN") — treat as "definitively absent" rather than
            # iterating over it.
            raw_intervals = intervals_payload if intervals_status == "ok" else []

            # Format interval segments (empty list if no structured intervals exist)
            segments = []
            for iv in raw_intervals:
                segment = {
                    "type": iv.get("type"),
                    "label": iv.get("group_id"),
                    "duration_secs": iv.get("elapsed_time"),
                    "avg_power": iv.get("average_watts"),
                    "max_power": iv.get("max_watts"),
                    "avg_hr": iv.get("average_heartrate"),
                    "max_hr": iv.get("max_heartrate"),
                    "avg_cadence": iv.get("average_cadence"),
                    "zone": iv.get("zone"),
                    "w_bal": iv.get("w_bal"),
                    "training_load": iv.get("training_load"),
                    "decoupling": iv.get("decoupling"),
                    # Per-interval avg_dfa_a1 is the Intervals.icu-computed value (UNFILTERED).
                    # The session-level dfa.avg below IS artifact-filtered. Don't try to
                    # reconcile the two — they use different denominators by design.
                    "avg_dfa_a1": iv.get("average_dfa_a1"),
                }
                # Strip None values to keep output lean
                segment = {k: v for k, v in segment.items() if v is not None}
                segments.append(segment)

            # DFA a1 session-level rollup (v3.99) — compute block only on ok.
            # None means no AlphaHRV recording on this activity (skip dfa key entirely).
            # A block with quality.sufficient=False means AlphaHRV ran but data unusable.
            dfa_block = None
            if streams_status == "ok":
                try:
                    if streams_payload.get("dfa_a1"):
                        dfa_block = self._compute_dfa_block(streams_payload)
                except Exception as e:
                    if self.debug:
                        print(f"    ⚠️  DFA a1 computation failed for {act_id}: {e}")
                    dfa_block = None

            # Emit entry if EITHER segments OR dfa block exists.
            # Pure endurance rides with AlphaHRV: no segments, has dfa.
            # Structured intervals without AlphaHRV: has segments, no dfa.
            # Both: full entry. Neither: skip silently.
            if segments or dfa_block is not None:
                entry = {
                    "activity_id": act_id,
                    "date": act.get("start_date_local", "")[:10],
                    "type": act.get("type", "Unknown"),
                    "name": act.get("name", ""),
                    "interval_summary": act.get("interval_summary"),
                    "intervals": segments
                }
                if dfa_block is not None:
                    entry["dfa"] = dfa_block
                new_entries.append(entry)
        
        if new_entries:
            print(f"    ✅ Fetched intervals for {len(new_entries)} new activit{'y' if len(new_entries) == 1 else 'ies'}")
        
        # Merge: keep cached entries within retention window + new entries
        retained = [a for a in cached.get("activities", []) if a.get("date", "") >= retention_cutoff]
        all_entries = retained + new_entries
        
        # Build intervals.json
        self._intervals_data = {
            "generated_at": now.isoformat(),
            "version": self.VERSION,
            "script_hash": self.script_hash,
            "scan_hours": self.INTERVAL_SCAN_HOURS,
            "retention_days": self.INTERVAL_RETENTION_DAYS,
            "activities": all_entries
        }
        
        # Return all activity IDs that have interval data
        return {a["activity_id"] for a in all_entries}
    
    # ── Route & Terrain Intelligence (v3.93) ─────────────────────────────
    
    def _generate_terrain(self, events: List[Dict],
                          athlete_units: Optional[Dict[str, str]] = None) -> Dict:
        """
        Parse GPX/TCX attachments on events into routes.json.
        
        Scans all events for attachments, downloads and parses route files,
        produces terrain_summary with climb/descent detection. Caches by
        attachment ID to avoid re-downloading unchanged files.
        
        Returns dict of event_id → terrain_summary for has_terrain flags.
        
        athlete_units (v3.109): plumbed through to _analyze_terrain so each
        terrain_summary in routes.json carries display blocks. Copy-forward
        cache hits also refresh display blocks (canonical metric fields are
        preserved verbatim) so a unit-preference change picks up next sync.
        """
        routes_path = self.data_dir / self.ROUTES_FILE
        
        # Load existing cache
        cached = {"events": []}
        if routes_path.exists():
            try:
                with open(routes_path, 'r') as f:
                    cached = json.load(f)
                # Invalidate cache if sync.py changed (schema may differ)
                if cached.get("script_hash") != self.script_hash:
                    if self.debug:
                        print(f"    🔄 routes.json stale (sync.py changed), re-parsing all")
                    cached = {"events": []}
            except Exception as e:
                if self.debug:
                    print(f"    ⚠️  Could not read routes.json: {e}")
                cached = {"events": []}
        
        # Build lookup of cached attachment_id → terrain entry
        cached_by_attachment = {}
        for entry in cached.get("events", []):
            aid = entry.get("attachment_id")
            if aid:
                cached_by_attachment[aid] = entry
        
        # Scan events for attachments
        new_entries = []
        for evt in events:
            attachments = evt.get("attachments")
            if not attachments:
                continue
            
            evt_id = evt.get("id")
            evt_name = evt.get("name", "Unnamed")
            evt_date = (evt.get("start_date_local") or "")[:10]
            evt_category = evt.get("category", "")
            
            # Start time: HH:MM when set (not midnight)
            evt_start_time = None
            raw_start = evt.get("start_date_local") or ""
            if "T" in raw_start:
                time_part = raw_start.split("T")[1][:5]
                if time_part != "00:00":
                    evt_start_time = time_part
            
            for att in attachments:
                att_id = att.get("id")
                filename = att.get("filename", "")
                url = att.get("url", "")
                
                if not att_id or not url:
                    continue
                
                # Skip non-route files by extension
                ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
                if ext not in ("gpx", "tcx", "fit"):
                    continue
                
                # Check cache — reuse if attachment ID unchanged
                if att_id in cached_by_attachment:
                    entry = cached_by_attachment[att_id].copy()
                    # Update event metadata (name/date may change)
                    entry["event_id"] = evt_id
                    entry["event_name"] = evt_name
                    entry["event_date"] = evt_date
                    entry["category"] = evt_category
                    if evt_start_time:
                        entry["start_time"] = evt_start_time
                    else:
                        entry.pop("start_time", None)
                    # Refresh display blocks against current prefs (v3.109).
                    # Canonical metric fields are preserved; only display sub-objects
                    # are recomputed so a pref change picks up without invalidating
                    # the GPX-parse cache.
                    cached_ts = entry.get("terrain_summary")
                    if isinstance(cached_ts, dict):
                        entry["terrain_summary"] = self._refresh_terrain_display(cached_ts, athlete_units)
                    new_entries.append(entry)
                    if self.debug:
                        print(f"    ✓ Cached terrain: {evt_name} ({filename})")
                    continue
                
                # Download and parse
                if self.debug:
                    print(f"    ↓ Downloading: {filename} for {evt_name}")
                
                terrain_summary = self._download_and_parse_route(url, filename, athlete_units=athlete_units)
                
                entry = {
                    "event_id": evt_id,
                    "event_name": evt_name,
                    "event_date": evt_date,
                    "category": evt_category,
                    "attachment_id": att_id,
                    "filename": filename,
                    "terrain_summary": terrain_summary
                }
                if evt_start_time:
                    entry["start_time"] = evt_start_time
                new_entries.append(entry)
        
        # Build routes.json
        self._routes_data = {
            "generated_at": datetime.now().isoformat(),
            "sync_version": self.VERSION,
            "script_hash": self.script_hash,
            "events": new_entries
        }
        
        # Return event_id → True for has_terrain flags
        return {e["event_id"] for e in new_entries if e.get("terrain_summary")}
    
    def _download_and_parse_route(self, url: str, filename: str,
                                  athlete_units: Optional[Dict[str, str]] = None) -> Optional[Dict]:
        """Download a route file attachment and parse it into a terrain_summary."""
        try:
            response = requests.get(url, timeout=30)
            if response.status_code != 200:
                return {"error": f"download failed (HTTP {response.status_code})"}
            content = response.content
        except Exception as e:
            return {"error": f"download failed: {str(e)[:100]}"}
        
        if not content or len(content) < 50:
            return {"error": "empty or invalid file"}
        
        return self._parse_route_file(content, filename, athlete_units=athlete_units)
    
    def _parse_route_file(self, content: bytes, filename: str,
                          athlete_units: Optional[Dict[str, str]] = None) -> Optional[Dict]:
        """Detect route file format and dispatch to parser."""
        text_start = content[:200].decode("utf-8", errors="ignore").strip()
        
        if text_start.startswith("<?xml") or text_start.startswith("<gpx") or "<gpx" in text_start[:500]:
            return self._parse_gpx(content, athlete_units=athlete_units)
        elif "<TrainingCenterDatabase" in text_start or "TrainingCenterDatabase" in content[:500].decode("utf-8", errors="ignore"):
            return self._parse_tcx(content, athlete_units=athlete_units)
        elif content[:2] == b'.F' or content[:4] == b'\x0e\x10\xd9\x07':
            # FIT binary magic bytes
            return {"error": "FIT format not yet supported"}
        else:
            # Fall back to extension
            ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
            if ext == "gpx":
                return self._parse_gpx(content, athlete_units=athlete_units)
            elif ext == "tcx":
                return self._parse_tcx(content, athlete_units=athlete_units)
            elif ext == "fit":
                return {"error": "FIT format not yet supported"}
            return {"error": f"unrecognized route file format"}
    
    def _parse_gpx(self, content: bytes,
                   athlete_units: Optional[Dict[str, str]] = None) -> Optional[Dict]:
        """Parse GPX file into trackpoints, then analyze terrain."""
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            return {"error": f"GPX parse error: {str(e)[:100]}"}
        
        # Handle namespace
        ns = ""
        tag = root.tag
        if "}" in tag:
            ns = tag[:tag.index("}") + 1]
        
        trackpoints = []
        for trkpt in root.iter(f"{ns}trkpt"):
            lat = trkpt.get("lat")
            lon = trkpt.get("lon")
            ele_elem = trkpt.find(f"{ns}ele")
            if lat and lon:
                tp = {"lat": float(lat), "lon": float(lon)}
                if ele_elem is not None and ele_elem.text:
                    try:
                        tp["ele"] = float(ele_elem.text)
                    except ValueError:
                        pass
                trackpoints.append(tp)
        
        if len(trackpoints) < 2:
            return {"error": "insufficient trackpoints"}
        
        return self._analyze_terrain(trackpoints, athlete_units=athlete_units)
    
    def _parse_tcx(self, content: bytes,
                   athlete_units: Optional[Dict[str, str]] = None) -> Optional[Dict]:
        """Parse TCX file into trackpoints, then analyze terrain."""
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            return {"error": f"TCX parse error: {str(e)[:100]}"}
        
        # Handle namespace
        ns = ""
        tag = root.tag
        if "}" in tag:
            ns = tag[:tag.index("}") + 1]
        
        trackpoints = []
        for tp_elem in root.iter(f"{ns}Trackpoint"):
            pos = tp_elem.find(f"{ns}Position")
            if pos is None:
                continue
            lat_elem = pos.find(f"{ns}LatitudeDegrees")
            lon_elem = pos.find(f"{ns}LongitudeDegrees")
            alt_elem = tp_elem.find(f"{ns}AltitudeMeters")
            
            if lat_elem is not None and lon_elem is not None:
                try:
                    tp = {"lat": float(lat_elem.text), "lon": float(lon_elem.text)}
                    if alt_elem is not None and alt_elem.text:
                        tp["ele"] = float(alt_elem.text)
                    trackpoints.append(tp)
                except (ValueError, TypeError):
                    continue
        
        if len(trackpoints) < 2:
            return {"error": "insufficient trackpoints"}
        
        return self._analyze_terrain(trackpoints, athlete_units=athlete_units)
    
    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine distance in meters between two GPS coordinates."""
        R = 6371000  # Earth radius in meters
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    def _analyze_terrain(self, trackpoints: List[Dict],
                         source: str = "gpx_attachment",
                         include_polyline: bool = True,
                         athlete_units: Optional[Dict[str, str]] = None) -> Dict:
        """
        Analyze trackpoints into terrain_summary.
        
        Computes: total distance, total elevation gain, climb/descent detection,
        course character, elevation_per_km. Elevation smoothed with rolling
        window (~50m) before gradient calculation to reduce GPS jitter.
        
        Parameters:
            trackpoints: list of {lat, lon, ele?} dicts.
            source: tag stored in output. "gpx_attachment" for route attachments
                (default, preserves existing routes.json behavior). "activity_streams"
                for completed activities pulled from Intervals streams API.
            include_polyline: emit downsampled polyline (500m intervals). True for
                routes.json (used for map rendering). False for activity terrain
                (raw streams available on demand via pull.py).
            athlete_units: six-key prefs map ({distance, weight, height, ...}). When
                provided, terrain_summary and each climb/descent get a `display`
                block alongside canonical metric fields. None preserves the
                metric-only output for any caller not yet plumbed (v3.109).
        """
        has_elevation = any("ele" in tp for tp in trackpoints)
        
        # Compute cumulative distance and collect elevation
        cum_dist = [0.0]  # cumulative distance in meters
        for i in range(1, len(trackpoints)):
            d = self._haversine(
                trackpoints[i - 1]["lat"], trackpoints[i - 1]["lon"],
                trackpoints[i]["lat"], trackpoints[i]["lon"]
            )
            cum_dist.append(cum_dist[-1] + d)
        
        total_distance_m = cum_dist[-1]
        total_distance_km = round(total_distance_m / 1000, 1)
        
        if not has_elevation or total_distance_m < 100:
            return {
                "source": source if has_elevation else f"{source}_no_elevation",
                "total_distance_km": total_distance_km,
                "total_elevation_m": 0,
                "elevation_per_km": 0.0,
                "course_character": "flat",
                "climbs": [],
                "descents": [],
                "display": {
                    "total_distance": self._to_display(total_distance_km, "distance", athlete_units),
                    "total_elevation": self._to_display(0, "elevation", athlete_units),
                    "elevation_per_distance": self._to_display(0.0, "elevation_per_distance", athlete_units),
                }
            } if not has_elevation else None
        
        # Smooth elevation: rolling window ~50m of distance
        raw_ele = [tp.get("ele", 0.0) for tp in trackpoints]
        smoothed_ele = list(raw_ele)  # copy
        SMOOTH_WINDOW_M = 50.0
        
        for i in range(len(trackpoints)):
            # Find indices within ±SMOOTH_WINDOW_M/2 of current point
            lo, hi = i, i
            while lo > 0 and cum_dist[i] - cum_dist[lo - 1] < SMOOTH_WINDOW_M / 2:
                lo -= 1
            while hi < len(trackpoints) - 1 and cum_dist[hi + 1] - cum_dist[i] < SMOOTH_WINDOW_M / 2:
                hi += 1
            if lo < hi:
                smoothed_ele[i] = sum(raw_ele[lo:hi + 1]) / (hi - lo + 1)
        
        # Total elevation gain (from smoothed)
        total_gain = 0.0
        for i in range(1, len(smoothed_ele)):
            diff = smoothed_ele[i] - smoothed_ele[i - 1]
            if diff > 0:
                total_gain += diff
        total_elevation_m = round(total_gain)
        
        elevation_per_km = round(total_elevation_m / total_distance_km, 1) if total_distance_km > 0 else 0.0
        
        # Detect climbs and descents
        # Entry gradient is low (1.5%) to catch long gradual climbs like Brocken.
        # Post-filter by elevation gain: segments with <100m gain AND <3% avg are
        # filtered out to avoid detecting gentle inclines as "climbs."
        raw_climbs = self._detect_segments(trackpoints, cum_dist, smoothed_ele, min_gradient=1.5, min_distance=500.0, ascending=True, athlete_units=athlete_units)
        climbs = [c for c in raw_climbs if c["elevation_m"] >= 100 or c["avg_gradient_pct"] >= 3.0]
        raw_descents = self._detect_segments(trackpoints, cum_dist, smoothed_ele, min_gradient=1.5, min_distance=500.0, ascending=False, athlete_units=athlete_units)
        descents = [d for d in raw_descents if abs(d["elevation_m"]) >= 100 or abs(d["avg_gradient_pct"]) >= 3.0]
        
        # Course character — elevation density (m/km) only.
        # Total elevation is distance-blind: 2000m over 300km is rolling,
        # not hilly. Climb category upgrades handle "flat with one big climb."
        if elevation_per_km >= 30:
            course_character = "mountain"
        elif elevation_per_km >= 20:
            course_character = "hilly"
        elif elevation_per_km >= 5:
            course_character = "rolling"
        else:
            course_character = "flat"
        
        # Upgrade based on climb severity
        max_category = None
        for c in climbs:
            cat = c.get("category")
            if cat in ("HC", "Cat 1", "Cat 2"):
                max_category = "hilly"
                break
        if max_category == "hilly" and course_character in ("flat", "rolling"):
            course_character = "hilly"
        
        # Downsample trackpoints at 500m intervals for polyline (when requested).
        # Activities skip the polyline since the raw streams are available on demand
        # via pull.py — saves ~1-3 KB per activity in latest.json.
        polyline = None
        if include_polyline:
            POLYLINE_INTERVAL_M = 500.0
            polyline = []
            next_threshold = 0.0
            for i, tp in enumerate(trackpoints):
                if cum_dist[i] >= next_threshold or i == 0 or i == len(trackpoints) - 1:
                    km = round(cum_dist[i] / 1000, 1)
                    pt = [km, round(tp["lat"], 5), round(tp["lon"], 5)]
                    if has_elevation:
                        pt.append(round(smoothed_ele[i]))
                    polyline.append(pt)
                    if i == 0:
                        next_threshold = POLYLINE_INTERVAL_M
                    else:
                        next_threshold = cum_dist[i] + POLYLINE_INTERVAL_M
        
        # Start coordinates — first valid trackpoint. Useful for "where did this
        # ride happen" without needing to read the full polyline.
        start_coords = [round(trackpoints[0]["lat"], 5), round(trackpoints[0]["lon"], 5)]
        
        # Grade distribution + max grade — both derived from the same 200m chunked
        # walk over smoothed elevation. max_grade_pct captures the steepest
        # 200m anywhere on the route (including short pitches that don't
        # form sustained climbs and therefore aren't in climbs[]).
        grade_distribution, max_grade_pct = self._compute_grade_distribution(cum_dist, smoothed_ele)
        
        result = {
            "source": source,
            "total_distance_km": total_distance_km,
            "total_elevation_m": total_elevation_m,
            "elevation_per_km": elevation_per_km,
            "course_character": course_character,
            "max_grade_pct": max_grade_pct,
            "grade_distribution": grade_distribution,
            "start_coords": start_coords,
            "climbs": climbs,
            "descents": descents,
            "display": {
                "total_distance": self._to_display(total_distance_km, "distance", athlete_units),
                "total_elevation": self._to_display(total_elevation_m, "elevation", athlete_units),
                "elevation_per_distance": self._to_display(elevation_per_km, "elevation_per_distance", athlete_units),
            }
        }
        if include_polyline:
            result["polyline"] = polyline
        return result
    
    def _compute_grade_distribution(self, cum_dist: List[float],
                                    smoothed_ele: List[float]) -> Tuple[Dict[str, float], float]:
        """
        Compute time-in-grade distribution + max absolute grade.
        
        Walks the route in 200m chunks. For each chunk, computes the gradient
        and assigns it to a bucket. Returns (distribution, max_abs_grade_pct).
        
        Buckets (absolute gradient — descents and climbs both count toward
        the same bucket since coaching-relevant grade impact is symmetric):
            flat:     |grade| < 1%
            gentle:   1-3%
            moderate: 3-6%
            steep:    >= 6%
        
        First return value is a dict with keys flat_pct, gentle_pct,
        moderate_pct, steep_pct (sums to ~100, rounding residual possible).
        
        Second return value is the steepest 200m chunk encountered anywhere
        on the route, NOT just inside detected climbs. This catches short
        steep pitches on otherwise rolling routes that don't form sustained
        climbs (and therefore don't appear in the climbs[] array). Coach
        protocol uses max_grade_pct ≥ 10 as a "surface terrain" trigger;
        gating that on detected-climb max would miss exactly the rides
        where a single short kicker mattered.
        """
        CHUNK_M = 200.0
        total_dist = cum_dist[-1] if cum_dist else 0.0
        if total_dist < CHUNK_M:
            return ({"flat_pct": 100.0, "gentle_pct": 0.0, "moderate_pct": 0.0, "steep_pct": 0.0}, 0.0)
        
        buckets = {"flat": 0.0, "gentle": 0.0, "moderate": 0.0, "steep": 0.0}
        max_grade = 0.0
        n = len(cum_dist)
        i = 0
        chunk_start_dist = 0.0
        while i < n - 1:
            # Advance j until chunk_distance >= CHUNK_M or end of track
            j = i
            while j < n - 1 and cum_dist[j] - chunk_start_dist < CHUNK_M:
                j += 1
            chunk_dist = cum_dist[j] - chunk_start_dist
            if chunk_dist <= 0:
                break
            ele_change = smoothed_ele[j] - smoothed_ele[i]
            grade_pct = abs(ele_change / chunk_dist * 100.0)
            if grade_pct > max_grade:
                max_grade = grade_pct
            if grade_pct < 1.0:
                buckets["flat"] += chunk_dist
            elif grade_pct < 3.0:
                buckets["gentle"] += chunk_dist
            elif grade_pct < 6.0:
                buckets["moderate"] += chunk_dist
            else:
                buckets["steep"] += chunk_dist
            chunk_start_dist = cum_dist[j]
            i = j
        
        return ({
            "flat_pct": round(buckets["flat"] / total_dist * 100, 1),
            "gentle_pct": round(buckets["gentle"] / total_dist * 100, 1),
            "moderate_pct": round(buckets["moderate"] / total_dist * 100, 1),
            "steep_pct": round(buckets["steep"] / total_dist * 100, 1),
        }, round(max_grade, 1))
    
    def _streams_to_trackpoints(self, streams: List[Dict]) -> List[Dict]:
        """
        Convert Intervals.icu streams response into trackpoint dicts compatible
        with _analyze_terrain.
        
        Intervals stores latlng as a single stream object with two parallel
        arrays: `data` holds latitudes, `data2` holds longitudes (NOT the Strava
        paired-array convention). Altitude is its own stream with a `data` array.
        
        Skips trackpoints where either lat or lng is None (GPS dropout). Altitude
        is included when present and non-None at the same index.
        """
        latlng_stream = next((s for s in streams if s.get("type") == "latlng"), None)
        altitude_stream = next((s for s in streams if s.get("type") == "altitude"), None)
        if not latlng_stream:
            return []
        
        lat_arr = latlng_stream.get("data") or []
        lng_arr = latlng_stream.get("data2") or []
        ele_arr = (altitude_stream.get("data") if altitude_stream else None) or []
        
        n = min(len(lat_arr), len(lng_arr))
        trackpoints = []
        for i in range(n):
            lat, lng = lat_arr[i], lng_arr[i]
            if lat is None or lng is None:
                continue
            tp = {"lat": float(lat), "lon": float(lng)}
            if i < len(ele_arr) and ele_arr[i] is not None:
                tp["ele"] = float(ele_arr[i])
            trackpoints.append(tp)
        return trackpoints
    
    def _detect_segments(self, trackpoints: List[Dict], cum_dist: List[float],
                         smoothed_ele: List[float], min_gradient: float,
                         min_distance: float, ascending: bool,
                         athlete_units: Optional[Dict[str, str]] = None) -> List[Dict]:
        """
        Detect sustained climb or descent segments using chunk-based analysis.
        
        Divides route into ~200m chunks, classifies each by gradient, then finds
        contiguous climbing/descending runs. Tolerates brief flats and small dips
        within a climb (real climbs have false flats and switchbacks). A climb ends
        when elevation drops >50m from the local high water mark, indicating a
        genuine descent, not a brief dip.
        
        athlete_units (v3.109): when provided, each segment dict carries a `display`
        block with position, distance, and elevation in the athlete's preferred units.
        """
        CHUNK_M = 200  # chunk size for gradient classification
        DIP_TOLERANCE_M = 50  # max elevation loss before ending a climb
        
        n = len(trackpoints)
        if n < 2 or cum_dist[-1] < CHUNK_M:
            return []
        
        # Build chunks: each has start_idx, end_idx, gradient, distance, ele_change
        chunks = []
        ci = 0
        while ci < n - 1:
            cj = ci + 1
            while cj < n and cum_dist[cj] - cum_dist[ci] < CHUNK_M:
                cj += 1
            if cj >= n:
                cj = n - 1
            if cj <= ci:
                break
            
            chunk_dist = cum_dist[cj] - cum_dist[ci]
            chunk_ele = smoothed_ele[cj] - smoothed_ele[ci]
            chunk_grad = (chunk_ele / chunk_dist * 100) if chunk_dist > 10 else 0
            
            chunks.append({
                "si": ci, "ei": cj,
                "dist": chunk_dist, "ele": chunk_ele, "grad": chunk_grad
            })
            ci = cj
        
        if not chunks:
            return []
        
        # Find climbing or descending segments using high-water-mark logic
        segments = []
        i = 0
        
        while i < len(chunks):
            c = chunks[i]
            
            # Look for start of a potential segment
            if ascending and c["grad"] < 1.0:
                i += 1
                continue
            elif not ascending and c["grad"] > -1.0:
                i += 1
                continue
            
            # Start tracking a segment
            seg_start_idx = c["si"]
            seg_start_ele = smoothed_ele[seg_start_idx]
            
            if ascending:
                high_mark = seg_start_ele
                high_mark_chunk = i
            else:
                low_mark = seg_start_ele
                low_mark_chunk = i
            
            j = i
            while j < len(chunks):
                current_ele = smoothed_ele[chunks[j]["ei"]]
                
                if ascending:
                    if current_ele > high_mark:
                        high_mark = current_ele
                        high_mark_chunk = j
                    # End if we've dropped too far from high water mark
                    if high_mark - current_ele > DIP_TOLERANCE_M:
                        break
                else:
                    if current_ele < low_mark:
                        low_mark = current_ele
                        low_mark_chunk = j
                    # End if we've risen too far from low water mark
                    if current_ele - low_mark > DIP_TOLERANCE_M:
                        break
                j += 1
            
            # Determine segment boundaries
            if ascending:
                seg_end_idx = chunks[high_mark_chunk]["ei"]
            else:
                seg_end_idx = chunks[low_mark_chunk]["ei"]
            
            # Trim flat approach: advance start until the LOCAL gradient
            # (over the next ~1km) shows sustained climbing. Prevents valley
            # roads with slight uphill trend being included in mountain climbs.
            LOCAL_TRIM_DIST = 2000  # look 2km ahead for local gradient check
            LOCAL_TRIM_GRAD = 2.5   # minimum local gradient to start the climb
            if ascending:
                for t in range(i, min(high_mark_chunk, len(chunks))):
                    t_start = chunks[t]["si"]
                    # Find point ~1km ahead
                    ahead_idx = t_start
                    for ai in range(t_start + 1, min(chunks[high_mark_chunk]["ei"] + 1, len(cum_dist))):
                        if cum_dist[ai] - cum_dist[t_start] >= LOCAL_TRIM_DIST:
                            ahead_idx = ai
                            break
                    if ahead_idx > t_start:
                        local_dist = cum_dist[ahead_idx] - cum_dist[t_start]
                        local_ele = smoothed_ele[ahead_idx] - smoothed_ele[t_start]
                        if local_dist > 0 and (local_ele / local_dist * 100) >= LOCAL_TRIM_GRAD:
                            seg_start_idx = t_start
                            break
            elif not ascending:
                end_chunk = low_mark_chunk
                for t in range(i, min(end_chunk, len(chunks))):
                    t_start = chunks[t]["si"]
                    ahead_idx = t_start
                    for ai in range(t_start + 1, min(chunks[end_chunk]["ei"] + 1, len(cum_dist))):
                        if cum_dist[ai] - cum_dist[t_start] >= LOCAL_TRIM_DIST:
                            ahead_idx = ai
                            break
                    if ahead_idx > t_start:
                        local_dist = cum_dist[ahead_idx] - cum_dist[t_start]
                        local_ele = smoothed_ele[ahead_idx] - smoothed_ele[t_start]
                        if local_dist > 0 and (local_ele / local_dist * 100) <= -LOCAL_TRIM_GRAD:
                            seg_start_idx = t_start
                            break
            
            seg_dist = cum_dist[seg_end_idx] - cum_dist[seg_start_idx]
            seg_ele = smoothed_ele[seg_end_idx] - smoothed_ele[seg_start_idx]
            
            # Check minimum criteria
            if seg_dist >= min_distance and abs(seg_ele) >= 50:
                avg_gradient = (seg_ele / seg_dist) * 100 if seg_dist > 0 else 0
                
                if (ascending and avg_gradient >= min_gradient) or \
                   (not ascending and avg_gradient <= -min_gradient):
                    
                    position_km = round(cum_dist[seg_start_idx] / 1000, 1)
                    distance_km = round(seg_dist / 1000, 1)
                    elevation_m = round(abs(seg_ele))
                    signed_elevation_m = elevation_m if ascending else -elevation_m
                    
                    segment = {
                        "position_km": position_km,
                        "distance_km": distance_km,
                        "elevation_m": signed_elevation_m,
                        "avg_gradient_pct": round(abs(avg_gradient), 1),
                        "start_coords": [round(trackpoints[seg_start_idx]["lat"], 5),
                                         round(trackpoints[seg_start_idx]["lon"], 5)],
                        "end_coords": [round(trackpoints[seg_end_idx]["lat"], 5),
                                       round(trackpoints[seg_end_idx]["lon"], 5)],
                        "display": {
                            "position": self._to_display(position_km, "distance", athlete_units),
                            "distance": self._to_display(distance_km, "distance", athlete_units),
                            "elevation": self._to_display(signed_elevation_m, "elevation", athlete_units),
                        }
                    }
                    
                    if ascending:
                        # Max gradient over 200m subsections
                        max_grad = 0.0
                        for k in range(seg_start_idx, seg_end_idx):
                            for m in range(k + 1, seg_end_idx + 1):
                                sub_dist = cum_dist[m] - cum_dist[k]
                                if sub_dist >= 200:
                                    sub_grad = abs((smoothed_ele[m] - smoothed_ele[k]) / sub_dist * 100)
                                    max_grad = max(max_grad, sub_grad)
                                    break
                        segment["max_gradient_pct"] = round(max_grad, 1) if max_grad > 0 else segment["avg_gradient_pct"]
                        
                        # UCI-derived climb category
                        if elevation_m >= 1000:
                            segment["category"] = "HC"
                        elif elevation_m >= 650:
                            segment["category"] = "Cat 1"
                        elif elevation_m >= 400:
                            segment["category"] = "Cat 2"
                        elif elevation_m >= 200:
                            segment["category"] = "Cat 3"
                        elif elevation_m >= 100:
                            segment["category"] = "Cat 4"
                        else:
                            segment["category"] = None  # uncategorized — below Cat 4 threshold
                    else:
                        segment["avg_gradient_pct"] = -segment["avg_gradient_pct"]
                    
                    segments.append(segment)
            
            # Advance past this segment
            if ascending:
                i = high_mark_chunk + 1
            else:
                i = low_mark_chunk + 1
        
        return segments
    
    def _fetch_today_wellness(self) -> Dict:
        """
        Fetch today's wellness data which contains:
        - CTL, ATL, rampRate (but these include planned workouts!)
        - sportInfo with eFTP, W', P-max (accurate live estimates)
        - VO2max, sleep quality/hours, etc.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            data = self._intervals_get(f"wellness/{today}")
            return data
        except Exception as e:
            if self.debug:
                print(f"  Could not fetch today's wellness: {e}")
            return {}
    
    def _extract_power_model_from_wellness(self, wellness_data: Dict) -> Dict:
        """
        Extract eFTP, W', P-max from wellness.sportInfo.
        These are the accurate live estimates that match the Intervals.icu UI.
        """
        sport_info = wellness_data.get("sportInfo", [])
        
        # Find cycling sport info
        cycling_info = None
        for sport in sport_info:
            if sport.get("type") == "Ride":
                cycling_info = sport
                break
        
        if not cycling_info:
            return {
                "eftp": None,
                "w_prime": None,
                "w_prime_kj": None,
                "p_max": None,
                "source": "unavailable"
            }
        
        eftp = cycling_info.get("eftp")
        w_prime = cycling_info.get("wPrime")
        p_max = cycling_info.get("pMax")
        
        if self.debug and eftp:
            print(f"  eFTP: {round(eftp)}W, W': {round(w_prime) if w_prime else 'N/A'}J, P-max: {round(p_max) if p_max else 'N/A'}W")
        
        return {
            "eftp": round(eftp, 1) if eftp else None,
            "w_prime": round(w_prime) if w_prime else None,
            "w_prime_kj": round(w_prime / 1000, 1) if w_prime else None,
            "p_max": round(p_max) if p_max else None,
            "source": "wellness.sportInfo"
        }
    
    def _load_ftp_history(self) -> Dict[str, Dict[str, int]]:
        """
        Load FTP history from local JSON file.
        
        Returns dict with structure:
        {
            "indoor": {"2026-01-01": 270, "2026-02-01": 275},
            "outdoor": {"2026-01-01": 280, "2026-02-01": 287}
        }
        """
        ftp_history_path = self.data_dir / self.FTP_HISTORY_FILE
        
        if ftp_history_path.exists():
            try:
                with open(ftp_history_path, 'r') as f:
                    data = json.load(f)
                    # Handle legacy format (flat dict) -> convert to new format
                    if data and not ("indoor" in data or "outdoor" in data):
                        if self.debug:
                            print(f"  Converting legacy FTP history format...")
                        return {"indoor": {}, "outdoor": data}
                    return data
            except Exception as e:
                if self.debug:
                    print(f"  Could not load FTP history: {e}")
                return {"indoor": {}, "outdoor": {}}
        return {"indoor": {}, "outdoor": {}}
    
    def _save_ftp_history(self, history: Dict[str, Dict[str, int]], 
                          current_ftp_indoor: int, current_ftp_outdoor: int) -> Dict[str, Dict[str, int]]:
        """
        Save current FTPs to history file.
        Tracks indoor and outdoor FTP separately.
        Only adds entry if FTP changed from most recent entry.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Ensure structure exists
        if "indoor" not in history:
            history["indoor"] = {}
        if "outdoor" not in history:
            history["outdoor"] = {}
        
        # Update indoor FTP if changed
        if current_ftp_indoor:
            indoor_history = history["indoor"]
            if indoor_history:
                sorted_dates = sorted(indoor_history.keys(), reverse=True)
                most_recent = indoor_history[sorted_dates[0]]
                if current_ftp_indoor != most_recent:
                    history["indoor"][today] = current_ftp_indoor
                    if self.debug:
                        print(f"  Indoor FTP changed: {most_recent} → {current_ftp_indoor}")
            else:
                history["indoor"][today] = current_ftp_indoor
                if self.debug:
                    print(f"  Indoor FTP recorded: {current_ftp_indoor}")
        
        # Update outdoor FTP if changed
        if current_ftp_outdoor:
            outdoor_history = history["outdoor"]
            if outdoor_history:
                sorted_dates = sorted(outdoor_history.keys(), reverse=True)
                most_recent = outdoor_history[sorted_dates[0]]
                if current_ftp_outdoor != most_recent:
                    history["outdoor"][today] = current_ftp_outdoor
                    if self.debug:
                        print(f"  Outdoor FTP changed: {most_recent} → {current_ftp_outdoor}")
            else:
                history["outdoor"][today] = current_ftp_outdoor
                if self.debug:
                    print(f"  Outdoor FTP recorded: {current_ftp_outdoor}")
        
        # Save to file
        ftp_history_path = self.data_dir / self.FTP_HISTORY_FILE
        try:
            with open(ftp_history_path, 'w') as f:
                json.dump(history, f, indent=2, sort_keys=True)
            if self.debug:
                print(f"  FTP history saved to {ftp_history_path}")
        except Exception as e:
            if self.debug:
                print(f"  Could not save FTP history: {e}")
        
        return history
    
    def _calculate_benchmark_index(self, current_ftp: int, ftp_history: Dict[str, int], 
                                    ftp_type: str = "indoor") -> Tuple[Optional[float], Optional[int]]:
        """
        Calculate Benchmark Index = (FTP_current / FTP_8_weeks_ago) - 1
        
        Returns (benchmark_index, ftp_8_weeks_ago)
        """
        if not current_ftp or not ftp_history:
            return None, None
        
        # Find FTP from ~8 weeks ago (56 days, with ±7 day tolerance)
        target_date = datetime.now() - timedelta(days=56)
        earliest_acceptable = target_date - timedelta(days=7)
        latest_acceptable = target_date + timedelta(days=7)
        
        # Find the closest FTP entry to 8 weeks ago
        best_match_date = None
        best_match_diff = float('inf')
        
        for date_str, ftp in ftp_history.items():
            try:
                entry_date = datetime.strptime(date_str, "%Y-%m-%d")
                
                if earliest_acceptable <= entry_date <= latest_acceptable:
                    diff = abs((entry_date - target_date).days)
                    if diff < best_match_diff:
                        best_match_diff = diff
                        best_match_date = date_str
            except:
                continue
        
        if best_match_date:
            ftp_8_weeks_ago = ftp_history[best_match_date]
            benchmark_index = round((current_ftp / ftp_8_weeks_ago) - 1, 3)
            
            if self.debug:
                print(f"  Benchmark Index ({ftp_type}): {benchmark_index:+.1%} (FTP {ftp_8_weeks_ago} → {current_ftp})")
            
            return benchmark_index, ftp_8_weeks_ago
        
        # No data from 8 weeks ago
        if self.debug:
            sorted_dates = sorted(ftp_history.keys())
            if sorted_dates:
                oldest_date = datetime.strptime(sorted_dates[0], "%Y-%m-%d")
                days_of_history = (datetime.now() - oldest_date).days
                print(f"  Benchmark Index ({ftp_type}) unavailable: only {days_of_history} days of history (need ~56)")
        
        return None, None
    
    def _years_since(self, date_str: Optional[str]) -> Optional[int]:
        """Compute complete years between an ISO YYYY-MM-DD date and today.
        Returns None if missing/malformed. Used for both age (from DOB) and
        platform tenure (from activation date)."""
        if not date_str:
            return None
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
            today = datetime.now()
            return today.year - d.year - ((today.month, today.day) < (d.month, d.day))
        except (ValueError, TypeError):
            return None
    
    def _compose_location(self, city: Optional[str], state: Optional[str],
                          country: Optional[str]) -> Optional[str]:
        """Join city/state/country into a display string, stripping trailing spaces
        (Intervals.icu returns 'Aalborg ' / 'Nordjylland ' with trailing whitespace).
        Returns None if all parts are empty/None."""
        parts = [p.strip() for p in (city, state, country) if p and p.strip()]
        return ", ".join(parts) if parts else None
    
    def collect_training_data(self, days_back: int = 7) -> Dict:
        """Collect all training data for LLM analysis"""
        # Extended range for ACWR calculation (need 28 days minimum)
        days_for_acwr = 28
        oldest_extended = (datetime.now() - timedelta(days=days_for_acwr - 1)).strftime("%Y-%m-%d")
        oldest_display = (datetime.now() - timedelta(days=days_back - 1)).strftime("%Y-%m-%d")
        newest = datetime.now().strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        
        print("Fetching athlete data...")
        athlete = self._intervals_get("")
        
        # Athlete profile (stable identity fields from athlete endpoint) — v3.103
        # SECURITY: explicit-allow only. Never serialize the raw athlete dict —
        # it contains icu_api_key, icu_friend_invite_token, and other secrets.
        dob = athlete.get("icu_date_of_birth")
        platform_activated_raw = athlete.get("icu_activated")  # ISO 8601 with time
        platform_activated = platform_activated_raw[:10] if platform_activated_raw else None
        years_on_platform = self._years_since(platform_activated)
        # Normalized unit dict — source of truth for display conversions across
        # all narrative-bearing fields (v3.109). Built before athlete_profile so
        # it can populate athlete_profile.display_preferences and feed
        # _to_display() at every emission site below.
        athlete_units = self._athlete_units_from_dict(athlete)
        
        height_m = athlete.get("height")
        athlete_profile = {
            "date_of_birth": dob,
            "age": self._years_since(dob),
            "height_m": height_m,
            "display": {
                "height": self._to_display(height_m, "height", athlete_units),
            },
            "display_preferences": athlete_units,
            "sex": athlete.get("sex"),
            "location": self._compose_location(
                athlete.get("city"), athlete.get("state"), athlete.get("country")
            ),
            "timezone": athlete.get("timezone"),
            "platform_activated": platform_activated,
            "years_on_platform": years_on_platform,
        }
        athlete_notes = athlete.get("icu_notes")  # raw string passthrough; mini-dossier later
        
        # Per-field unit labels for recent_activities (v3.103)
        # Temp/wind: API returns values in athlete's account unit — label reflects that.
        # Speed: sync.py force-converts m/s → km/h at format time → always "KPH".
        # avg_speed_unit/max_speed_unit retained for backward compatibility; the new
        # display.speed block (v3.109) is the authoritative narration source.
        temp_unit = "F" if athlete.get("fahrenheit") else "C"
        wind_unit = athlete.get("wind_speed") or "MPS"
        speed_unit = "KPH"
        
        # Load previous latest.json — used as persistent state for terrain &
        # weather copy-forward. Empty dict on first sync / fresh data dir.
        previous_latest_lookup = self._load_previous_latest()
        
        # Extract per-sport-family thesholds from user settings
        sport_settings = self._build_sport_thresholds(athlete)
        
        # Fetch extended activity range for ACWR
        print(f"Fetching activities (extended {days_for_acwr} days for ACWR)...")
        activities_extended = self._intervals_get("activities", {"oldest": oldest_extended, "newest": newest})
        
        # Filter to display range for recent_activities
        activities_display = [a for a in activities_extended 
                             if a.get("start_date_local", "")[:10] >= oldest_display]
        
        print("Fetching wellness data...")
        wellness = self._intervals_get("wellness", {"oldest": oldest_display, "newest": newest})
        
        # Extended wellness for baselines (use full 28 days if available)
        wellness_extended = self._intervals_get("wellness", {"oldest": oldest_extended, "newest": newest})
        
        # Fetch today's wellness for live estimates (eFTP, W', P-max, VO2max, etc.)
        print("Fetching today's wellness (eFTP, W', P-max, VO2max)...")
        today_wellness = self._fetch_today_wellness()
        
        # Extract power model from wellness (accurate live estimates)
        power_model = self._extract_power_model_from_wellness(today_wellness)
        
        # Extract additional metrics from today's wellness
        vo2max = today_wellness.get("vo2max")
        
        # Get API values for fitness metrics (these include planned workouts!)
        api_ctl = today_wellness.get("ctl")
        api_atl = today_wellness.get("atl")
        api_ramp_rate = today_wellness.get("rampRate")
        
        # Fetch yesterday's wellness for decay fallback
        print("Fetching fitness metrics...")
        try:
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            yesterday_wellness = self._intervals_get("wellness", {"oldest": yesterday, "newest": yesterday})
            yesterday_data = yesterday_wellness[0] if yesterday_wellness else {}
            
            # PMC decay constants
            ctl_decay = math.exp(-1/42)  # ~0.9765
            atl_decay = math.exp(-1/7)   # ~0.8668
            
            yesterday_ctl = yesterday_data.get("ctl")
            yesterday_atl = yesterday_data.get("atl")
            yesterday_ramp = yesterday_data.get("rampRate")
            
            # Decayed values = what fitness looks like with zero training today
            decayed_ctl = round(yesterday_ctl * ctl_decay, 2) if yesterday_ctl else None
            decayed_atl = round(yesterday_atl * atl_decay, 2) if yesterday_atl else None
            decayed_ramp = round(yesterday_ramp * ctl_decay, 2) if yesterday_ramp else None
        except:
            decayed_ctl = None
            decayed_atl = None
            decayed_ramp = None
            yesterday_ramp = None
        
        latest_wellness = wellness[-1] if wellness else {}
        
        # Fetch planned workouts (EXTENDED: include past 7 days for Consistency Index, 90 days ahead for race calendar)
        print("Fetching planned workouts (past + future for Consistency Index + race calendar)...")
        oldest_events = (datetime.now() - timedelta(days=days_back - 1)).strftime("%Y-%m-%d")
        newest_ahead = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        events = self._intervals_get("events", {"oldest": oldest_events, "newest": newest_ahead, "resolve": "true"})
        
        # Split events into past (for consistency), near future (for planned workouts display), and all future (for race calendar)
        past_events = [e for e in events if e.get("start_date_local", "")[:10] <= today]
        future_events = [e for e in events if e.get("start_date_local", "")[:10] >= today]
        near_future_events = [e for e in future_events if e.get("start_date_local", "")[:10] <= (datetime.now() + timedelta(days=42)).strftime("%Y-%m-%d")]
        
        # Smart fitness metrics: same logic for CTL, ATL, TSB, and ramp rate
        # API values include planned workouts → inflated if not yet completed
        # Decayed values = yesterday × decay → accurate baseline before any training today
        todays_planned = [e for e in events if e.get("start_date_local", "")[:10] == today]
        todays_activities = [a for a in activities_display if a.get("start_date_local", "")[:10] == today]
        
        if todays_planned and not todays_activities:
            # Planned workouts exist but nothing completed → decay (API values are inflated)
            ctl = decayed_ctl
            atl = decayed_atl
            smart_ramp_rate = decayed_ramp if decayed_ramp else api_ramp_rate
            fitness_source = "Decayed from yesterday (today's planned workouts not yet completed)"
        else:
            # No planned workouts OR workouts completed → API values are accurate
            ctl = round(api_ctl, 2) if api_ctl else decayed_ctl
            atl = round(api_atl, 2) if api_atl else decayed_atl
            smart_ramp_rate = round(api_ramp_rate, 2) if api_ramp_rate else decayed_ramp
            fitness_source = "From Intervals.icu API (reflects completed workouts)"
        
        tsb = round(ctl - atl, 2) if (ctl is not None and atl is not None) else None
        
        # Get both FTP values for cycling (user-set, not estimated)
        cycling = sport_settings.get("cycling", {})
        current_ftp_indoor = cycling.get("ftp_indoor")
        current_ftp_outdoor = cycling.get("ftp")
        
        # Load and update FTP history (tracks both indoor and outdoor)
        print("Updating FTP history...")
        ftp_history = self._load_ftp_history()
        ftp_history = self._save_ftp_history(ftp_history, current_ftp_indoor, current_ftp_outdoor)
        
        # Calculate Benchmark Index for both
        benchmark_index_indoor, ftp_8_weeks_ago_indoor = self._calculate_benchmark_index(
            current_ftp_indoor, ftp_history.get("indoor", {}), "indoor"
        )
        benchmark_index_outdoor, ftp_8_weeks_ago_outdoor = self._calculate_benchmark_index(
            current_ftp_outdoor, ftp_history.get("outdoor", {}), "outdoor"
        )
        
        # Generate routes.json from GPX/TCX attachments (v3.93)
        print("Scanning events for route attachments...")
        terrain_event_ids = self._generate_terrain(events, athlete_units=athlete_units)
        self._terrain_event_ids = terrain_event_ids
        if terrain_event_ids:
            print(f"   🗺️  Route data for {len(terrain_event_ids)} event(s)")
        
        # Build race calendar (v3.5.0) — moved before derived metrics for phase detection
        print("Building race calendar...")
        race_calendar = self._build_race_calendar(
            future_events=future_events,
            current_ctl=ctl,
            current_atl=atl,
            current_tsb=tsb,
            activities_7d=activities_display,
            today=today,
            athlete_units=athlete_units
        )
        
        # Format planned workouts — used by both phase detection and output
        formatted_planned_workouts = self._format_events(near_future_events, today=today)
        
        # Fetch power curves for delta analysis (two 28-day windows)
        print("Fetching power curves...")
        power_curve_data = None
        pc_dates = None
        try:
            pc_end1 = today
            pc_start1 = (datetime.now() - timedelta(days=27)).strftime("%Y-%m-%d")
            pc_end2 = (datetime.now() - timedelta(days=28)).strftime("%Y-%m-%d")
            pc_start2 = (datetime.now() - timedelta(days=55)).strftime("%Y-%m-%d")
            pc_dates = (pc_start1, pc_end1, pc_start2, pc_end2)
            power_curve_data = self._intervals_get("power-curves", {
                "type": "Ride",
                "curves": f"r.{pc_start1}.{pc_end1},r.{pc_start2}.{pc_end2}"
            })
        except Exception as e:
            if self.debug:
                print(f"  ⚠️  Power curve fetch failed: {e}")
        
        # Fetch HR curves for delta analysis (same windows, no sport filter)
        print("Fetching HR curves...")
        hr_curve_data = None
        try:
            hr_curve_data = self._intervals_get("hr-curves", {
                "curves": f"r.{pc_dates[0]}.{pc_dates[1]},r.{pc_dates[2]}.{pc_dates[3]}"
            }) if pc_dates else None
        except Exception as e:
            if self.debug:
                print(f"  ⚠️  HR curve fetch failed: {e}")
        
        # Fetch sustainability curves (v3.91) — sport-filtered power + HR, single 42d window
        print("Fetching sustainability curves...")
        sustainability_curves = {}
        sus_end = today
        sus_start = (datetime.now() - timedelta(days=self.SUSTAINABILITY_WINDOW_DAYS - 1)).strftime("%Y-%m-%d")
        sus_window = (sus_start, sus_end)
        
        # Determine which sport families have recent activity data
        active_sport_families = set()
        for a in activities_extended:
            sf = self.SPORT_FAMILIES.get(a.get("type", ""), None)
            if sf and sf in self.SUSTAINABILITY_ANCHORS:
                active_sport_families.add(sf)
        
        for sport_family in active_sport_families:
            sport_curves = {"power": {}, "hr": {}}
            
            # Power curves — one fetch per activity type (cycling: Ride + VirtualRide)
            power_types = self.SUSTAINABILITY_POWER_TYPES.get(sport_family, [])
            for ptype in power_types:
                try:
                    data = self._intervals_get("power-curves", {
                        "type": ptype,
                        "curves": f"r.{sus_start}.{sus_end}"
                    })
                    sport_curves["power"][ptype] = data
                except Exception as e:
                    if self.debug:
                        print(f"  ⚠️  Sustainability power-curves ({ptype}) failed: {e}")
            
            # HR curves — one fetch per activity type
            hr_types = self.SUSTAINABILITY_HR_TYPES.get(sport_family, [])
            for htype in hr_types:
                try:
                    data = self._intervals_get("hr-curves", {
                        "type": htype,
                        "curves": f"r.{sus_start}.{sus_end}"
                    })
                    sport_curves["hr"][htype] = data
                except Exception as e:
                    if self.debug:
                        print(f"  ⚠️  Sustainability hr-curves ({htype}) failed: {e}")
            
            sustainability_curves[sport_family] = sport_curves
        
        if sustainability_curves:
            print(f"  📊 Sustainability curves fetched for: {', '.join(sorted(sustainability_curves.keys()))}")
        else:
            print("  📊 No sport families with sustainability data")
        
        # Generate interval-level data (v3.82, expanded v3.99)
        # Uses the already-fetched activity list — no extra listing API calls.
        # Pre-filters by sport family whitelist; no longer requires interval_summary.
        # Incremental: only fetches intervals for new qualifying activities.
        # MUST run before _calculate_derived_metrics so self._intervals_data is
        # populated when _calculate_dfa_a1_profile reads it (v3.99 fix).
        print("Checking for interval data...")
        interval_activity_ids = self._generate_intervals(activities_display)
        if interval_activity_ids:
            print(f"  📊 {len(interval_activity_ids)} activit{'y' if len(interval_activity_ids) == 1 else 'ies'} with interval data")
        
        # Calculate derived metrics for Section 11 compliance
        print("Calculating derived metrics...")
        derived_metrics = self._calculate_derived_metrics(
            activities_7d=activities_display,
            activities_28d=activities_extended,
            wellness_7d=wellness,
            wellness_extended=wellness_extended,
            current_ctl=ctl,
            current_atl=atl,
            current_tsb=tsb,
            past_events=past_events,
            activities_for_consistency=activities_display,
            power_model=power_model,
            benchmark_indoor=(benchmark_index_indoor, ftp_8_weeks_ago_indoor, current_ftp_indoor),
            benchmark_outdoor=(benchmark_index_outdoor, ftp_8_weeks_ago_outdoor, current_ftp_outdoor),
            vo2max=vo2max,
            formatted_planned_workouts=formatted_planned_workouts,
            race_calendar=race_calendar,
            power_curve_data=power_curve_data,
            power_curve_dates=pc_dates,
            hr_curve_data=hr_curve_data,
            sustainability_curves=sustainability_curves,
            sustainability_window=sus_window,
            sport_settings=sport_settings,
            icu_weight=athlete.get("icu_weight")
        )
        
        # Generate alerts array (v3.3.0)
        print("Evaluating alert thresholds...")
        alerts = self._generate_alerts(
            derived_metrics=derived_metrics,
            wellness_7d=wellness,
            tss_7d_total=derived_metrics.get("tss_7d_total", 0),
            tss_28d_total=derived_metrics.get("tss_28d_total", 0)
        )
        
        if alerts:
            alarm_count = sum(1 for a in alerts if a["severity"] == "alarm")
            warning_count = sum(1 for a in alerts if a["severity"] == "warning")
            print(f"  ⚠️  {len(alerts)} alerts: {alarm_count} alarm, {warning_count} warning")
        else:
            print("  ✅ No alerts — green light")
        
        # Add race-specific alerts
        race_alerts = self._generate_race_alerts(race_calendar)
        if race_alerts:
            alerts.extend(race_alerts)
            print(f"  🏁 {len(race_alerts)} race alert(s) added")
        
        if race_calendar.get("race_week", {}).get("active"):
            rw = race_calendar["race_week"]
            print(f"  🏁 Race week ACTIVE: {rw['current_day']} of '{rw['event_name']}'")
        elif race_calendar.get("taper_alert", {}).get("active"):
            nr = race_calendar.get("next_race", {})
            print(f"  🏁 Taper alert: '{nr.get('name', '?')}' in {nr.get('days_until', '?')} days")
        elif race_calendar.get("next_race"):
            nr = race_calendar["next_race"]
            print(f"  🏁 Next race: '{nr.get('name', '?')}' in {nr.get('days_until', '?')} days")
        else:
            print("  🏁 No races in 90-day window")
        
        # Compute readiness decision (v3.72)
        print("Computing readiness decision...")
        readiness_decision = self._compute_readiness_decision(
            derived_metrics=derived_metrics,
            alerts=alerts,
            latest_wellness=latest_wellness,
            activities=activities_extended,
            race_calendar=race_calendar,
            current_tsb=tsb
        )
        rd_rec = readiness_decision["recommendation"].upper()
        rd_pri = readiness_decision["priority"]
        print(f"  {'🟢' if rd_rec == 'GO' else '🟡' if rd_rec == 'MODIFY' else '🔴'} Readiness: {rd_rec} (P{rd_pri})")
        
        # History confidence (v3.3.0)
        history_info = self._get_history_confidence()
        
        data = {
            "READ_THIS_FIRST": {
                "instruction_for_ai": "DO NOT calculate totals from individual activities. Use the pre-calculated values in 'summary', 'weekly_summary', and 'derived_metrics' sections below. These are already computed accurately from the API data.",
                "display_formatting": "For durations and sleep, always display the '_formatted' fields (e.g., sleep_formatted, duration_formatted, total_training_formatted) instead of converting decimal '_hours' values. The formatted fields are pre-calculated from raw seconds and avoid rounding errors.",
                "data_period": f"Last {days_back} days (including today)",
                "extended_data_note": f"ACWR and baselines calculated from {days_for_acwr} days of data",
                "capability_metrics_note": "The 'capability' block in derived_metrics contains durability trend (aggregate decoupling 7d/28d), efficiency factor trend (aggregate EF 7d/28d), HRRc trend (heart rate recovery 7d/28d), TID comparison (7d vs 28d distribution drift), power curve delta (MMP shift at anchor durations across 28d windows — energy system adaptation direction), HR curve delta (max sustained HR shift at anchor durations — cardiac adaptation, cross-sport), sustainability profile (per-sport power/HR sustainability table for race estimation — 42d window, sport-filtered), and DFA a1 profile (per-session non-linear HRV index from AlphaHRV Connect IQ field — latest_session + trailing_by_sport with crossing-band LT1/LT2 estimates). These measure HOW the athlete expresses fitness, not just load. Use these for coaching context alongside traditional load metrics. Durability and EF trend direction matters more than absolute values. HRRc is display only — higher = better parasympathetic recovery. Power curve delta rotation_index reveals whether gains are sprint-biased (positive) or endurance-biased (negative). HR curve delta is ambiguous — rising max sustained HR may indicate fitness or fatigue; cross-reference with resting HRV/HR and RPE. Sustainability profile provides race estimation lookup: actual MMP, Coggan predicted (cycling only), CP/W' model (cycling only), model_divergence_pct (actual vs CP — divergence IS the coaching signal). CP/W' is primary for durations ≤20min; Coggan duration factors are the established reference for ≥60min. Source flag (observed_outdoor/observed_indoor) matters for cycling race estimation — indoor MMP is typically 3-5% lower. DFA a1 profile: thresholds (1.0 ≈ LT1, 0.5 ≈ LT2) cycling-validated only — non-cycling sports get rollups but validated=False. Crossing-band estimates: HR is pooled across all sessions; watts are split by environment for cycling (watts_outdoor, watts_indoor with per-environment n_sessions) — compare watts_outdoor against ftp, watts_indoor against ftp_indoor. Non-cycling sports keep pooled watts. Estimates are provisional at confidence='low' (suppressed for calibration delta surfacing) and usable at 'moderate' or 'high'. DFA a1 is a Tier-2 interpretive signal — does NOT enter readiness P0–P3 ladder, does NOT auto-update dossier zones; surfaces calibration deltas only. Quality gate: refuse to interpret when latest_session.sufficient=false or trailing confidence=null. See SECTION_11.md DFA a1 Protocol for full interpretation rules.",
                "readiness_decision_note": "The 'readiness_decision' block contains a pre-computed go/modify/skip recommendation with priority level (P0=safety, P1=overload, P2=fatigue, P3=green), individual signal statuses, phase-adjusted thresholds, and structured modification guidance. Use this as the baseline for pre-workout recommendations. Override with explanation in the coach note if the AI's contextual judgment disagrees.",
                "zone_preference": self.zone_preference if self.zone_preference else "default (power preferred, HR fallback)",
                "wellness_field_scales": {
                    "note": "All categorical wellness fields use a 1-4 positional scale where 1 = best state, 4 = worst state. Labels differ per field but direction is consistent. Fields are null when not reported.",
                    "sleep_quality": {"1": "GREAT", "2": "OK", "3": "POOR", "4": "WORST"},
                    "fatigue": {"1": "None", "2": "Some", "3": "High", "4": "Extreme", "ui_note": "Labeled 'Pre training' in Intervals.icu"},
                    "soreness": {"1": "None", "2": "Some", "3": "High", "4": "Extreme", "ui_note": "Labeled 'Pre training' in Intervals.icu"},
                    "stress": {"1": "LOW", "2": "AVG", "3": "HIGH", "4": "EXTREME"},
                    "mood": {"1": "GREAT", "2": "GOOD", "3": "OK", "4": "GRUMPY"},
                    "motivation": {"1": "EXTREME", "2": "HIGH", "3": "AVG", "4": "LOW"},
                    "injury": {"1": "NONE", "2": "NIGGLE", "3": "POOR", "4": "INJURED"},
                    "hydration": {"1": "GOOD", "2": "OK", "3": "POOR", "4": "BAD"},
                    "menstrual": "menstrual_phase and menstrual_phase_predicted are not on the 1-4 scale. Values: PERIOD, FOLLICULAR, OVULATION, LUTEAL, etc."
                },
                "quick_stats": {
                    "total_training_hours": round(sum(act.get("moving_time", 0) for act in activities_display) / 3600, 2),
                    "total_training_formatted": self._format_duration(int(sum(act.get("moving_time", 0) for act in activities_display)) // 60 * 60),
                    "total_activities": len(activities_display),
                    "total_tss": round(sum(act.get("icu_training_load", 0) for act in activities_display if act.get("icu_training_load")), 0)
                }
            },
            "metadata": {
                "athlete_id": "REDACTED",
                "last_updated": datetime.now().isoformat(),
                "data_range_days": days_back,
                "extended_range_days": days_for_acwr,
                "version": self.VERSION
            },
            "athlete_profile": athlete_profile,
            "athlete_notes": athlete_notes,
            "alerts": alerts,
            "readiness_decision": readiness_decision,
            "history": history_info,
            "summary": self._compute_activity_summary(activities_display, days_back, athlete_units),
            "current_status": {
                "fitness": {
                    "ctl": ctl,
                    "atl": atl,
                    "tsb": tsb,
                    "ramp_rate": smart_ramp_rate,
                    "fitness_source": fitness_source
                },
                "thresholds": {
                    "eftp": power_model.get("eftp"),
                    "w_prime": power_model.get("w_prime"),
                    "w_prime_kj": power_model.get("w_prime_kj"),
                    "p_max": power_model.get("p_max"),
                    "vo2max": vo2max,                    
                    "sports": sport_settings
                },
                "current_metrics": {
                    "weight_kg": latest_wellness.get("weight") or athlete.get("icu_weight"),
                    "display": {
                        "weight": self._to_display(
                            latest_wellness.get("weight") or athlete.get("icu_weight"),
                            "weight", athlete_units
                        ),
                    },
                    "resting_hr": latest_wellness.get("restingHR") or athlete.get("icu_resting_hr"),
                    "hrv": latest_wellness.get("hrv"),
                    "sleep_quality": latest_wellness.get("sleepQuality"),
                    "sleep_hours": round(latest_wellness.get("sleepSecs", 0) / 3600, 2) if latest_wellness.get("sleepSecs") else None,
                    "sleep_formatted": self._format_duration(int(latest_wellness.get("sleepSecs", 0)) // 60 * 60) if latest_wellness.get("sleepSecs") else None,
                    "sleep_score": latest_wellness.get("sleepScore"),
                    # Subjective state (categorical 1-4, see wellness_field_scales in READ_THIS_FIRST)
                    "fatigue": latest_wellness.get("fatigue"),
                    "soreness": latest_wellness.get("soreness"),
                    "stress": latest_wellness.get("stress"),
                    "mood": latest_wellness.get("mood"),
                    "motivation": latest_wellness.get("motivation"),
                    "injury": latest_wellness.get("injury"),
                    "hydration": latest_wellness.get("hydration"),
                    # Vitals
                    "spO2": latest_wellness.get("spO2"),
                    "blood_glucose": latest_wellness.get("bloodGlucose"),
                    "systolic": latest_wellness.get("systolic"),
                    "diastolic": latest_wellness.get("diastolic"),
                    "baevsky_si": latest_wellness.get("baevskySI"),
                    "lactate": latest_wellness.get("lactate"),
                    "respiration": latest_wellness.get("respiration"),
                    # Body composition
                    "body_fat_pct": latest_wellness.get("bodyFat"),
                    "abdomen_cm": latest_wellness.get("abdomen"),
                    # Lifestyle / nutrition
                    "steps": latest_wellness.get("steps"),
                    "hydration_volume_l": latest_wellness.get("hydrationVolume"),
                    "kcal_consumed": latest_wellness.get("kcalConsumed"),
                    "carbohydrates_g": latest_wellness.get("carbohydrates"),
                    "protein_g": latest_wellness.get("protein"),
                    "fat_g": latest_wellness.get("fatTotal"),
                    # Cycle
                    "menstrual_phase": latest_wellness.get("menstrualPhase"),
                    "menstrual_phase_predicted": latest_wellness.get("menstrualPhasePredicted"),
                    # Platform
                    "readiness": latest_wellness.get("readiness")
                }
            },
            "derived_metrics": derived_metrics,
            "recent_activities": self._format_activities(
                activities_extended, interval_activity_ids,
                temp_unit=temp_unit, wind_unit=wind_unit, speed_unit=speed_unit,
                previous_latest_lookup=previous_latest_lookup,
                athlete_units=athlete_units
            ),
            "wellness_data": self._format_wellness(wellness, athlete_units),
            "planned_workouts": formatted_planned_workouts,
            "workout_summary_stats": getattr(self, '_summary_stats', {}),
            "weekly_summary": self._compute_weekly_summary(activities_display, wellness),
            "race_calendar": race_calendar
        }

        # Body weight signal (v3.112) — gated W/kg + weekly weight trend.
        # None when no field qualifies; AI omits the report section silently.
        weight_signal = self._build_weight_signal(
            wellness_extended, sport_settings, power_model, athlete_units
        )
        if weight_signal:
            data["current_status"]["weight"] = weight_signal

        return data

    def _build_sport_thresholds(self, athlete: dict) -> dict:
        """
        Build per-sport-family threshold map from athlete sportSettings.
        Returns a dict keyed by sport family (e.g. {"cycling": {...}, "run": {...}})
        """
        candidates: dict[str, tuple[dict, int, str]] = {}

        for sport in athlete.get("sportSettings", []):
            for sport_type in sport.get("types", []):
                family = self.SPORT_FAMILIES.get(sport_type)
                if not family:
                    continue

                raw_pace = sport.get("threshold_pace")
                threshold_pace = raw_pace if (raw_pace is not None and raw_pace != 0) else None
                pace_units = sport.get("pace_units") if threshold_pace is not None else None

                entry = {
                    "lthr": sport.get("lthr"),
                    "max_hr": sport.get("max_hr"),
                    "threshold_pace": threshold_pace,
                    "pace_units": pace_units,
                    "ftp": sport.get("ftp") or None,
                    "ftp_indoor": sport.get("indoor_ftp") or None,
                }

                populated = sum(1 for v in entry.values() if v is not None)

                if family not in candidates or populated > candidates[family][1] or \
                   (populated == candidates[family][1] and sport_type < candidates[family][2]):
                    candidates[family] = (entry, populated, sport_type)

        return {family: data for family, (data, _, _) in candidates.items()}

    def _build_weight_signal(self, wellness_extended: List[Dict],
                              sport_settings: Dict, power_model: Dict,
                              athlete_units: Optional[Dict[str, str]] = None) -> Optional[Dict]:
        """
        Build current_status.weight block — gated weight signals for block
        (W/kg) and weekly (trend) reports. (v3.112)

        Architecture: every metric below is computed here; the AI layer
        interprets only. Failed-gate fields are ABSENT from the dict (not
        null) so the AI can treat absence as the "omit section" signal —
        no "insufficient data" boilerplate.

        Display fields (per Display Unit Semantics): narrated weights ship
        with a `display` sub-dict carrying {value, unit} pairs in the
        athlete's preferred unit. W/kg stays unit-universal — no display
        block on wkg_* fields. Slope display preserves 3dp precision and
        emits a unit code suffixed with "/week".

        Gates:
          - weight_latest_kg / weight_latest_date:
              latest weigh-in age <= 14 days
          - wkg_current + wkg_ftp_source [+ ftp_setting_date]:
              weight_latest present + FTP source available.
              Tested cycling FTP from sportSettings preferred, eFTP fallback.
              eFTP is not suppressed for stale tested FTP — staleness rides
              on the source tag via ftp_setting_date. The date reflects the
              FTP setting change recorded in ftp_history.json (Intervals
              does not expose a formal test date).
          - wkg_block_start / wkg_block_end / wkg_block_delta:
              >=1 weigh-in within the FIRST 4 days of the trailing 28d
              window (days [today-27, today-24]) AND >=1 weigh-in within
              the LAST 4 days (days [today-3, today]). v1 block-window
              proxy — Section 11 does not yet track explicit block
              boundaries. Both endpoints use the current FTP, so the delta
              reflects weight change across the window only.
          - weight_7d_avg_kg:
              >= 4 weigh-ins in trailing 7d
          - weight_28d_slope_kg_per_week:
              >= 14 weigh-ins in trailing 28d (linear slope)

        Returns None when no field qualifies — caller omits the `weight`
        key from current_status entirely.
        """
        BLOCK_WINDOW_DAYS = 28
        BOUNDARY_WIDTH_DAYS = 4
        today = datetime.now().date()
        block: Dict = {}
        display: Dict = {}

        # --- Collect dated weight entries (newest-first) ---
        entries: List[Tuple] = []
        for w in (wellness_extended or []):
            wt = w.get("weight")
            if wt is None or wt == 0:
                continue
            date_str = w.get("id", "")
            if not date_str:
                continue
            try:
                d = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
            except Exception:
                continue
            entries.append((d, float(wt)))

        if not entries:
            return None

        entries.sort(key=lambda x: x[0], reverse=True)

        # --- weight_latest_kg / weight_latest_date (gate: <=14d age) ---
        latest_date, latest_weight = entries[0]
        latest_age_days = (today - latest_date).days
        if 0 <= latest_age_days <= 14:
            block["weight_latest_kg"] = round(latest_weight, 1)
            block["weight_latest_date"] = latest_date.isoformat()
            display["weight_latest"] = self._to_display(
                latest_weight, "weight", athlete_units
            )

        # --- Resolve FTP source (tested preferred, eFTP fallback) ---
        cycling = (sport_settings or {}).get("cycling", {})
        tested_ftp = cycling.get("ftp")
        eftp = (power_model or {}).get("eftp")

        ftp_used: Optional[float] = None
        ftp_source: Optional[str] = None
        ftp_setting_date: Optional[str] = None

        if tested_ftp:
            ftp_used = float(tested_ftp)
            ftp_source = "tested"
            try:
                ftp_history = self._load_ftp_history()
                outdoor_dates = sorted(ftp_history.get("outdoor", {}).keys(), reverse=True)
                indoor_dates = sorted(ftp_history.get("indoor", {}).keys(), reverse=True)
                if outdoor_dates:
                    ftp_setting_date = outdoor_dates[0]
                elif indoor_dates:
                    ftp_setting_date = indoor_dates[0]
            except Exception:
                ftp_setting_date = None
        elif eftp:
            ftp_used = float(eftp)
            ftp_source = "eftp"

        # --- wkg_current (depends on weight_latest_kg + FTP source) ---
        if "weight_latest_kg" in block and ftp_used and block["weight_latest_kg"] > 0:
            block["wkg_current"] = round(ftp_used / block["weight_latest_kg"], 2)
            block["wkg_ftp_source"] = ftp_source
            if ftp_setting_date:
                block["ftp_setting_date"] = ftp_setting_date

        # --- Block trajectory: first-4 / last-4 boundary windows ---
        # First 4 days of trailing 28d window: [today-27, today-24]
        # Last 4 days of trailing 28d window:  [today-3,  today]
        first4_high = today - timedelta(days=BLOCK_WINDOW_DAYS - BOUNDARY_WIDTH_DAYS)  # today-24
        first4_low = today - timedelta(days=BLOCK_WINDOW_DAYS - 1)                     # today-27
        last4_low = today - timedelta(days=BOUNDARY_WIDTH_DAYS - 1)                    # today-3
        last4_high = today                                                              # today

        def _nearest_in_range(low, high, anchor):
            """Pick the weigh-in within [low, high] closest to anchor."""
            best = None
            best_dist = None
            for d, w in entries:
                if low <= d <= high:
                    dist = abs((d - anchor).days)
                    if best_dist is None or dist < best_dist:
                        best = w
                        best_dist = dist
            return best

        block_start_anchor = first4_low                # day -27
        block_end_anchor = today                       # day 0
        weight_at_start = _nearest_in_range(first4_low, first4_high, block_start_anchor)
        weight_at_end = _nearest_in_range(last4_low, last4_high, block_end_anchor)

        if weight_at_start and weight_at_end and ftp_used:
            block["wkg_block_start"] = round(ftp_used / weight_at_start, 2)
            block["wkg_block_end"] = round(ftp_used / weight_at_end, 2)
            block["wkg_block_delta"] = round(
                block["wkg_block_end"] - block["wkg_block_start"], 2
            )

        # --- weight_7d_avg_kg (gate: >=4 entries in trailing 7d) ---
        seven_d_cutoff = today - timedelta(days=6)
        seven_d_weights = [w for d, w in entries if d >= seven_d_cutoff]
        if len(seven_d_weights) >= 4:
            avg_kg = sum(seven_d_weights) / len(seven_d_weights)
            block["weight_7d_avg_kg"] = round(avg_kg, 1)
            display["weight_7d_avg"] = self._to_display(avg_kg, "weight", athlete_units)

        # --- weight_28d_slope_kg_per_week (gate: >=14 entries in trailing 28d) ---
        twenty_eight_d_cutoff = today - timedelta(days=BLOCK_WINDOW_DAYS - 1)
        slope_pairs = [(d, w) for d, w in entries if d >= twenty_eight_d_cutoff]
        if len(slope_pairs) >= 14:
            xs = [(d - twenty_eight_d_cutoff).days for d, _ in slope_pairs]
            ys = [w for _, w in slope_pairs]
            n = len(xs)
            mean_x = sum(xs) / n
            mean_y = sum(ys) / n
            num = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
            den = sum((xs[i] - mean_x) ** 2 for i in range(n))
            if den > 0:
                slope_kg_per_week = (num / den) * 7
                block["weight_28d_slope_kg_per_week"] = round(slope_kg_per_week, 3)
                # Manual display build: preserves 3dp + appends "/week" to unit code.
                # _to_display rounds to 1dp (correct for absolute weights, too coarse
                # for slopes) — we mirror its conversion logic here instead.
                weight_pref = (athlete_units or {}).get("weight")
                if weight_pref == "lb":
                    slope_display_value = round(slope_kg_per_week * 2.20462, 3)
                    slope_display_unit = "lb/week"
                else:
                    slope_display_value = round(slope_kg_per_week, 3)
                    slope_display_unit = "kg/week"
                display["weight_28d_slope_per_week"] = {
                    "value": slope_display_value,
                    "unit": slope_display_unit,
                }

        if not block:
            return None
        if display:
            block["display"] = display
        return block

    def _calculate_derived_metrics(self, activities_7d: List[Dict], activities_28d: List[Dict],
                                    wellness_7d: List[Dict], wellness_extended: List[Dict],
                                    current_ctl: float, current_atl: float, current_tsb: float,
                                    past_events: List[Dict], activities_for_consistency: List[Dict],
                                    power_model: Dict,
                                    benchmark_indoor: Tuple[Optional[float], Optional[int], Optional[int]],
                                    benchmark_outdoor: Tuple[Optional[float], Optional[int], Optional[int]],
                                    vo2max: float,
                                    formatted_planned_workouts: List[Dict] = None,
                                    race_calendar: Dict = None,
                                    power_curve_data: Dict = None,
                                    power_curve_dates: Tuple = None,
                                    hr_curve_data: Dict = None,
                                    sustainability_curves: Dict = None,
                                    sustainability_window: Tuple = None,
                                    sport_settings: Dict = None,
                                    icu_weight: float = None) -> Dict:
        """
        Calculate Section 11 derived metrics.
        
        Tier 1 (Primary): RI, baselines
        Tier 2 (Secondary): ACWR, Monotony, Strain, Stress Tolerance, Load-Recovery Ratio
        Tier 3 (Tertiary): Zone distribution, Polarisation, Phase Detection, Consistency, Benchmark
        
        Args:
            benchmark_indoor: (benchmark_index, ftp_8_weeks_ago, current_ftp) for indoor
            benchmark_outdoor: (benchmark_index, ftp_8_weeks_ago, current_ftp) for outdoor
        """
        
        # Defaults for phase detection inputs
        if formatted_planned_workouts is None:
            formatted_planned_workouts = []
        if race_calendar is None:
            race_calendar = {"next_race": None, "all_races": [], "taper_alert": {"active": False}, "race_week": {"active": False}}
        
        # Unpack benchmark tuples
        benchmark_index_indoor, ftp_8_weeks_ago_indoor, current_ftp_indoor = benchmark_indoor
        benchmark_index_outdoor, ftp_8_weeks_ago_outdoor, current_ftp_outdoor = benchmark_outdoor
        
        # === DAILY TSS AGGREGATION ===
        daily_tss_7d = self._get_daily_tss(activities_7d, days=7)
        daily_tss_28d = self._get_daily_tss(activities_28d, days=28)
        
        tss_7d_total = sum(daily_tss_7d)
        tss_28d_total = sum(daily_tss_28d)
        
        # === ACWR (Acute:Chronic Workload Ratio) ===
        # Formula: (7-day avg TSS) / (28-day avg TSS)
        # Reference: Gabbett (2016) - "sweet spot" is 0.8-1.3
        acute_load = tss_7d_total / 7 if tss_7d_total else 0
        chronic_load = tss_28d_total / 28 if tss_28d_total else 0
        acwr = round(acute_load / chronic_load, 2) if chronic_load > 0 else None
        
        # === MONOTONY (Total) ===
        # Formula: mean(daily_tss) / stdev(daily_tss)
        # Reference: Foster (1998) - values >2.0 indicate increased illness risk
        if len(daily_tss_7d) > 1 and any(daily_tss_7d):
            mean_tss = statistics.mean(daily_tss_7d)
            try:
                stdev_tss = statistics.stdev(daily_tss_7d)
                monotony = round(mean_tss / stdev_tss, 2) if stdev_tss > 0 else None
            except:
                monotony = None
        else:
            monotony = None
            mean_tss = 0

        # === PRIMARY SPORT MONOTONY (v3.3.3) ===
        # Multi-sport athletes get inflated total monotony when cross-training
        # adds a consistent TSS floor across days. Per-sport monotony isolates
        # the actual load variation within each modality.
        daily_tss_by_sport = self._get_daily_tss_by_sport(activities_7d, days=7)
        primary_sport = None
        primary_sport_monotony = None
        primary_sport_tss_7d = None

        if daily_tss_by_sport:
            # Primary sport = highest 7-day TSS total
            sport_totals = {sport: sum(days) for sport, days in daily_tss_by_sport.items()}
            primary_sport = max(sport_totals, key=sport_totals.get) if sport_totals else None

            if primary_sport:
                primary_days = daily_tss_by_sport[primary_sport]
                primary_sport_tss_7d = round(sum(primary_days), 0)
                # Require ≥3 active days for meaningful monotony
                active_days = sum(1 for d in primary_days if d > 0)
                if active_days >= 3 and len(primary_days) > 1:
                    try:
                        ps_mean = statistics.mean(primary_days)
                        ps_stdev = statistics.stdev(primary_days)
                        primary_sport_monotony = round(ps_mean / ps_stdev, 2) if ps_stdev > 0 else None
                    except:
                        primary_sport_monotony = None

                if self.debug:
                    print(f"  Primary sport: {primary_sport} (TSS: {primary_sport_tss_7d})")
                    print(f"  Primary sport monotony: {primary_sport_monotony}")
                    print(f"  Total monotony: {monotony}")
                    if primary_sport_monotony and monotony and primary_sport_monotony < monotony:
                        print(f"  → Multi-sport inflation detected ({monotony} total vs {primary_sport_monotony} primary)")

        # Determine effective monotony for alerts:
        # Use primary sport monotony when available and multi-sport detected,
        # fall back to total monotony otherwise
        is_multi_sport = len(daily_tss_by_sport) > 1
        effective_monotony = primary_sport_monotony if (is_multi_sport and primary_sport_monotony is not None) else monotony

        # === STRAIN ===
        # Formula: 7-day total TSS × Monotony
        # Reference: Foster (1998) - values >3500-4000 associated with overtraining
        strain = round(tss_7d_total * monotony, 0) if monotony else None
        
        # === BASELINES (7-day and extended) ===
        hrv_values_7d = [w.get("hrv") for w in wellness_7d if self._is_valid_hrv(w.get("hrv"))]
        rhr_values_7d = [w.get("restingHR") for w in wellness_7d if w.get("restingHR")]
        
        hrv_baseline_7d = round(statistics.mean(hrv_values_7d), 1) if hrv_values_7d else None
        rhr_baseline_7d = round(statistics.mean(rhr_values_7d), 1) if rhr_values_7d else None
        
        # Extended baselines (for more stable reference)
        hrv_values_ext = [w.get("hrv") for w in wellness_extended if self._is_valid_hrv(w.get("hrv"))]
        rhr_values_ext = [w.get("restingHR") for w in wellness_extended if w.get("restingHR")]
        
        hrv_baseline_28d = round(statistics.mean(hrv_values_ext), 1) if hrv_values_ext else None
        rhr_baseline_28d = round(statistics.mean(rhr_values_ext), 1) if rhr_values_ext else None
        
        # === RECOVERY INDEX (RI) ===
        # Formula: (HRV_today / HRV_baseline) ÷ (RHR_today / RHR_baseline)
        # Interpretation: >1.0 = good recovery, <1.0 = poor recovery
        latest_hrv_raw = wellness_7d[-1].get("hrv") if wellness_7d else None
        latest_hrv = latest_hrv_raw if self._is_valid_hrv(latest_hrv_raw) else None
        latest_rhr = wellness_7d[-1].get("restingHR") if wellness_7d else None
        
        if latest_hrv and latest_rhr and hrv_baseline_7d and rhr_baseline_7d:
            hrv_ratio = latest_hrv / hrv_baseline_7d
            rhr_ratio = latest_rhr / rhr_baseline_7d
            ri = round(hrv_ratio / rhr_ratio, 2) if rhr_ratio > 0 else None
        else:
            ri = None

        # Yesterday's RI — same formula, wellness_7d[-2] against same 7d baseline.
        # Used for RI amber persistence check in readiness_decision (2-day rule).
        ri_yesterday = None
        if len(wellness_7d) >= 2:
            y_hrv_raw = wellness_7d[-2].get("hrv")
            y_hrv = y_hrv_raw if self._is_valid_hrv(y_hrv_raw) else None
            y_rhr = wellness_7d[-2].get("restingHR")
            if y_hrv and y_rhr and hrv_baseline_7d and rhr_baseline_7d:
                y_hrv_ratio = y_hrv / hrv_baseline_7d
                y_rhr_ratio = y_rhr / rhr_baseline_7d
                ri_yesterday = round(y_hrv_ratio / y_rhr_ratio, 2) if y_rhr_ratio > 0 else None
        
        # === STRESS TOLERANCE ===
        # Formula: (Strain ÷ Monotony) ÷ 100
        stress_tolerance = round((strain / monotony) / 100, 1) if strain and monotony else None
        
        # === LOAD-RECOVERY RATIO ===
        # Formula: 7-day Load ÷ (RI × 100)
        load_recovery_ratio = round(tss_7d_total / (ri * 100), 1) if ri and ri > 0 else None
        
        # === ZONE AGGREGATION ===
        zone_totals = self._aggregate_zones(activities_7d)
        
        total_zone_time = zone_totals["total_time"]
        z1_time = zone_totals["z1_time"]
        z2_time = zone_totals["z2_time"]
        z3_time = zone_totals["z3_time"]
        z4_plus_time = zone_totals["z4_plus_time"]
        zone_basis_7d = zone_totals["zone_basis"]
        
        # === GREY ZONE PERCENTAGE (Z3 - to be minimized in polarized training) ===
        # Reference: Seiler - "too much pain for too little gain"
        grey_zone_percentage = round((z3_time / total_zone_time) * 100, 1) if total_zone_time > 0 else None
        
        # === QUALITY INTENSITY PERCENTAGE (Z4+ per Seiler's model) ===
        # Reference: Seiler's Zone 3 = above LT2 = Z4+ in 7-zone model
        # This is the "hard" work that should be ~20% in polarized training
        quality_intensity_percentage = round((z4_plus_time / total_zone_time) * 100, 1) if total_zone_time > 0 else None
        
        # === EASY TIME RATIO ===
        # Formula: (Z1 + Z2) / Total - measures how much time is "easy"
        # Target: ~80% for polarized training
        easy_time_ratio = round((z1_time + z2_time) / total_zone_time, 2) if total_zone_time > 0 else None
        
        # === SEILER TID (Training Intensity Distribution) ===
        # Dual calculation: all-sport and primary-sport (like monotony)
        # Uses correct 7→3 zone mapping per Treff et al. 2019
        seiler_tid_all = self._build_seiler_tid(activities_7d)

        seiler_tid_primary = None
        if primary_sport:
            seiler_tid_primary = self._build_seiler_tid(
                activities_7d, sport_family_filter=primary_sport
            )
            seiler_tid_primary["sport"] = primary_sport

        if self.debug:
            pi_all = seiler_tid_all.get("polarization_index")
            cls_all = seiler_tid_all.get("classification")
            print(f"  Seiler TID (all): {cls_all}, PI={pi_all}")
            if seiler_tid_primary:
                pi_ps = seiler_tid_primary.get("polarization_index")
                cls_ps = seiler_tid_primary.get("classification")
                print(f"  Seiler TID ({primary_sport}): {cls_ps}, PI={pi_ps}")

        # === SEILER TID 28d (Chronic Training Intensity Distribution) ===
        # Same method, wider window — for acute vs chronic TID comparison
        seiler_tid_28d_all = self._build_seiler_tid(activities_28d)

        seiler_tid_28d_primary = None
        if primary_sport:
            seiler_tid_28d_primary = self._build_seiler_tid(
                activities_28d, sport_family_filter=primary_sport
            )
            seiler_tid_28d_primary["sport"] = primary_sport

        if self.debug:
            pi_28d = seiler_tid_28d_all.get("polarization_index")
            cls_28d = seiler_tid_28d_all.get("classification")
            print(f"  Seiler TID 28d (all): {cls_28d}, PI={pi_28d}")

        # === TID COMPARISON (7d vs 28d drift detection) ===
        tid_comparison = self._calculate_tid_comparison(seiler_tid_all, seiler_tid_28d_all)

        # === DURABILITY TREND (aggregate decoupling) ===
        durability = self._calculate_durability(activities_7d, activities_28d)
        efficiency_factor = self._calculate_efficiency_factor(activities_7d, activities_28d)
        hrrc_trend = self._calculate_hrrc_trend(activities_7d, activities_28d)

        # === POWER CURVE DELTA (energy system adaptation trend) ===
        power_curve_delta = self._calculate_power_curve_delta(power_curve_data, power_curve_dates)

        # === HR CURVE DELTA (cardiac adaptation trend) ===
        hr_curve_delta = self._calculate_hr_curve_delta(hr_curve_data, power_curve_dates)

        # === SUSTAINABILITY PROFILE (race estimation lookup table, v3.91) ===
        sustainability_profile = self._calculate_sustainability_profile(
            sustainability_curves=sustainability_curves or {},
            sustainability_window=sustainability_window,
            power_model=power_model,
            sport_settings=sport_settings or {},
            wellness_7d=wellness_7d,
            wellness_extended=wellness_extended,
            icu_weight=icu_weight
        )

        # === DFA a1 PROFILE (v3.99) ===
        # Reads from self._intervals_data populated by _generate_intervals().
        # Returns None when no AlphaHRV-equipped sessions exist in the 14d window.
        dfa_a1_profile = self._calculate_dfa_a1_profile()

        # === CONSISTENCY INDEX ===
        consistency_index, consistency_details = self._calculate_consistency_index(
            activities_for_consistency, past_events
        )
        
        # === PHASE DETECTION v2 (dual-stream) ===
        today = datetime.now().strftime("%Y-%m-%d")
        
        # === LIVE WEEKLY ROWS FROM activities_28d (v3.94) ===
        # Replaces v3.89 single-week overlay. Computes all 4 weekly rows
        # (TSS, primary_sport_tss, hard_days) live from activities_28d,
        # eliminating the entire class of stale-row bugs. CTL/ATL enriched
        # from history.json where available (stable background data).
        now_dt = datetime.now()
        days_since_ws = (now_dt.weekday() - self.week_start_day) % 7
        current_ws_dt = now_dt - timedelta(days=days_since_ws)
        
        # Build 4 week boundaries (newest first, then reversed to chronological)
        week_boundaries = []
        for i in range(4):
            ws_dt = current_ws_dt - timedelta(weeks=i)
            we_dt = ws_dt + timedelta(days=6)
            week_boundaries.append((ws_dt.strftime("%Y-%m-%d"), we_dt.strftime("%Y-%m-%d")))
        week_boundaries.reverse()  # chronological: oldest first
        
        # Bucket activities_28d by week and compute TSS + hard_days per week
        weekly_rows = []
        for ws, we in week_boundaries:
            week_acts = [a for a in activities_28d
                         if ws <= (a.get("start_date_local", "")[:10]) <= we]
            
            w_tss = sum((a.get("icu_training_load", 0) or 0) for a in week_acts)
            w_primary_tss = sum(
                (a.get("icu_training_load", 0) or 0) for a in week_acts
                if self.SPORT_FAMILIES.get(a.get("type", ""), None) == primary_sport
            )
            
            # Hard days: group by date, classify each day
            acts_by_date = {}
            for a in week_acts:
                a_date = a.get("start_date_local", "")[:10]
                if a_date not in acts_by_date:
                    acts_by_date[a_date] = []
                acts_by_date[a_date].append(a)
            
            w_hard_days = 0
            for date_str, day_acts in acts_by_date.items():
                day_zones_by_basis = {}
                for a in day_acts:
                    sf = self.SPORT_FAMILIES.get(a.get("type", ""), None)
                    zones, basis = self._get_activity_zones(a, sport_family=sf)
                    if zones and basis:
                        if basis not in day_zones_by_basis:
                            day_zones_by_basis[basis] = {}
                        for zid, secs in zones.items():
                            day_zones_by_basis[basis][zid] = day_zones_by_basis[basis].get(zid, 0) + secs
                is_hard, _basis = self._classify_hard_day(day_zones_by_basis)
                if is_hard:
                    w_hard_days += 1
            
            weekly_rows.append({
                "week_start": ws,
                "total_tss": round(w_tss, 0),
                "primary_sport_tss": round(w_primary_tss, 0),
                "primary_sport": primary_sport,
                "hard_days": w_hard_days,
                "activity_count": len(week_acts),
            })
        
        # Current week gets live CTL/ATL/ACWR/monotony (already computed this run)
        weekly_rows[-1]["ctl_end"] = round(current_ctl, 1) if current_ctl else None
        weekly_rows[-1]["atl_end"] = round(current_atl, 1) if current_atl else None
        weekly_rows[-1]["acwr"] = acwr
        weekly_rows[-1]["monotony"] = monotony
        
        # Enrich older weeks with CTL/ATL from history.json (stable background)
        history_rows = self._load_weekly_rows_for_phase()
        history_by_ws = {r.get("week_start"): r for r in history_rows}
        for row in weekly_rows[:-1]:  # skip current week (already enriched)
            hist = history_by_ws.get(row["week_start"])
            if hist:
                for field in ("ctl_end", "atl_end", "acwr", "monotony"):
                    if field not in row or row[field] is None:
                        row[field] = hist.get(field)
        
        # hard_days_this_week: current week's value (used in return dict)
        hard_days_this_week = weekly_rows[-1]["hard_days"]
        
        # previous_phase from [-2] (last completed week).
        # History rows may have phase_detected; fresh rows won't.
        # Enrich completed rows with phase_detected from history where available.
        for row in weekly_rows[:-1]:
            hist = history_by_ws.get(row["week_start"])
            if hist and "phase_detected" in hist:
                row["phase_detected"] = hist["phase_detected"]
        
        previous_phase = None
        if len(weekly_rows) >= 2:
            previous_phase = weekly_rows[-2].get("phase_detected")
        
        phase_result = self._detect_phase_v2(
            weekly_rows=weekly_rows,
            planned_workouts=formatted_planned_workouts,
            race_calendar=race_calendar,
            previous_phase=previous_phase,
            today=today,
            primary_sport=primary_sport
        )
        phase_detected = phase_result["phase"]
        
        # Legacy compatibility: extract trigger-style info for existing consumers
        phase_triggers = phase_result["reason_codes"]
        
        # === SEASONAL CONTEXT ===
        seasonal_context = self._determine_seasonal_context()
        
        # === BENCHMARK SEASONAL EXPECTATION ===
        benchmark_expected_indoor = self._is_benchmark_expected(benchmark_index_indoor, seasonal_context)
        benchmark_expected_outdoor = self._is_benchmark_expected(benchmark_index_outdoor, seasonal_context)
        
        return {
            # Tier 1: Primary Readiness
            "recovery_index": ri,
            "recovery_index_yesterday": ri_yesterday,
            "hrv_baseline_7d": hrv_baseline_7d,
            "rhr_baseline_7d": rhr_baseline_7d,
            "hrv_baseline_28d": hrv_baseline_28d,
            "rhr_baseline_28d": rhr_baseline_28d,
            "latest_hrv": latest_hrv,
            "latest_rhr": latest_rhr,
            
            # Tier 2: Secondary Load Metrics
            "acwr": acwr,
            "acwr_interpretation": self._interpret_acwr(acwr),
            "monotony": monotony,
            "monotony_interpretation": self._interpret_monotony(monotony, effective_monotony, is_multi_sport),
            "primary_sport": primary_sport,
            "primary_sport_monotony": primary_sport_monotony,
            "primary_sport_tss_7d": primary_sport_tss_7d,
            "effective_monotony": effective_monotony,
            "multi_sport_detected": is_multi_sport,
            "strain": strain,
            "stress_tolerance": stress_tolerance,
            "load_recovery_ratio": load_recovery_ratio,
            "tss_7d_total": round(tss_7d_total, 0),
            "tss_28d_total": round(tss_28d_total, 0),
            
            # Tier 3: Zone Distribution (Seiler's Polarized Model)
            "zone_distribution_7d": {
                "z1_hours": round(z1_time / 3600, 2),
                "z2_hours": round(z2_time / 3600, 2),
                "z3_hours": round(z3_time / 3600, 2),
                "z4_plus_hours": round(z4_plus_time / 3600, 2),
                "total_hours": round(total_zone_time / 3600, 2),
                "zone_basis": zone_basis_7d
            },
            "grey_zone_percentage": grey_zone_percentage,
            "grey_zone_note": "Gray Zone % (Z3/tempo) - minimize in polarized training",
            "quality_intensity_percentage": quality_intensity_percentage,
            "quality_intensity_note": "Quality Intensity % (Z4+/threshold+) - target ~20% in polarized training",
            "easy_time_ratio": easy_time_ratio,
            "easy_time_ratio_note": "Easy time (Z1+Z2) / Total - target ~80% in polarized training",
            "hard_days_this_week": hard_days_this_week,
            "hard_days_note": "Power ladder: z3+ >= 30min, z4+ >= 10min, z5+ >= 5min, z6+ >= 2min, z7 >= 1min. HR fallback (when no power): z4+ >= 10min, z5+ >= 5min. Per Seiler 3-zone model + Foster. HR-based days flagged with intensity_basis: hr",
            
            # Tier 3: Seiler TID (Training Intensity Distribution)
            "seiler_tid_7d": seiler_tid_all,
            "seiler_tid_7d_primary": seiler_tid_primary,
            "seiler_tid_28d": seiler_tid_28d_all,
            "seiler_tid_28d_primary": seiler_tid_28d_primary,
            
            # Capability metrics (how fitness is expressed, not just load)
            "capability": {
                "durability": durability,
                "efficiency_factor": efficiency_factor,
                "hrrc": hrrc_trend,
                "tid_comparison": tid_comparison,
                "power_curve_delta": power_curve_delta,
                "hr_curve_delta": hr_curve_delta,
                "sustainability_profile": sustainability_profile,
                "dfa_a1_profile": dfa_a1_profile,
            },
            
            # Tier 3: Consistency & Compliance
            "consistency_index": consistency_index,
            "consistency_details": consistency_details,
            
            # Phase & Context
            "phase_detection": phase_result,
            "phase_detected": phase_detected,  # top-level shortcut for backward compat
            "phase_triggers": phase_triggers,   # backward compat
            "seasonal_context": seasonal_context,
            
            # Benchmark & FTP Progression (Indoor)
            "benchmark_indoor": {
                "current_ftp": current_ftp_indoor,
                "ftp_8_weeks_ago": ftp_8_weeks_ago_indoor,
                "benchmark_index": benchmark_index_indoor,
                "benchmark_percentage": f"{benchmark_index_indoor:+.1%}" if benchmark_index_indoor is not None else None,
                "seasonal_expected": benchmark_expected_indoor
            },
            # Benchmark & FTP Progression (Outdoor)
            "benchmark_outdoor": {
                "current_ftp": current_ftp_outdoor,
                "ftp_8_weeks_ago": ftp_8_weeks_ago_outdoor,
                "benchmark_index": benchmark_index_outdoor,
                "benchmark_percentage": f"{benchmark_index_outdoor:+.1%}" if benchmark_index_outdoor is not None else None,
                "seasonal_expected": benchmark_expected_outdoor
            },
            
            # Power Model (from API - accurate live estimates)
            "eftp": power_model.get("eftp"),
            "w_prime": power_model.get("w_prime"),
            "w_prime_kj": power_model.get("w_prime_kj"),
            "p_max": power_model.get("p_max"),
            "power_model_source": power_model.get("source"),
            
            # Additional wellness metrics (from API)
            "vo2max": vo2max,
            
            # Validation metadata
            "calculation_timestamp": datetime.now().isoformat(),
            "data_quality": {
                "hrv_data_points": len(hrv_values_7d),
                "rhr_data_points": len(rhr_values_7d),
                "activities_7d": len(activities_7d),
                "activities_28d": len(activities_28d),
                "planned_workouts_7d": len(past_events),
                "ftp_history_days": self._get_ftp_history_span()
            }
        }
    
    def _interpret_acwr(self, acwr: float) -> Optional[str]:
        """Interpret ACWR value per Gabbett guidelines"""
        if acwr is None:
            return None
        if acwr < 0.8:
            return "undertraining"
        elif acwr < 1.3:
            return "optimal"
        elif acwr < 1.5:
            return "caution"
        else:
            return "danger"

    def _interpret_monotony(self, total_monotony: float, effective_monotony: float, is_multi_sport: bool) -> Optional[str]:
        """
        Interpret monotony with multi-sport awareness.
        When multi-sport training inflates total monotony, the interpretation
        reflects the effective (primary sport) value instead.
        """
        if effective_monotony is None:
            return None
        if is_multi_sport and total_monotony and effective_monotony < total_monotony:
            # Multi-sport inflation detected
            if effective_monotony > 2.0:
                return f"elevated (primary sport {effective_monotony}, total {total_monotony} inflated by multi-sport)"
            else:
                return f"normal (primary sport {effective_monotony}, total {total_monotony} inflated by multi-sport)"
        else:
            if effective_monotony > 2.0:
                return "elevated"
            else:
                return "normal"

    def _classify_effort_response(self, if_value: Optional[float],
                                    rpe: Optional[float]) -> Optional[str]:
        """
        Classify effort response per the v11.34 RPE Expectation Bands.

        Reads session IF (icu_intensity, stored as percentage 0-100+) and reported RPE
        (icu_rpe, 1-10). Normalizes IF to decimal at entry to match the canonical band
        table in SECTION_11.md §RPE Expectation Bands.

        Returns:
            "positive" - RPE below the expected band (fitness/freshness tell)
            "neutral"  - RPE within the expected band
            "negative" - RPE above the expected band (fatigue/under-recovery tell)
            None       - IF absent, RPE absent or <= 0, or IF < 0.65 (out of coverage)

        The IF < 0.65 null is a deliberate design gap, not missing data — recovery rides
        and aborted sessions fall outside the bands' calibration range, and fabricating a
        band there would produce noise on the sessions least worth flagging.

        Interpretive overlay only. Does NOT alter Feel/RPE Override rules (v11.14) and
        does NOT enter the readiness P0-P3 ladder.
        """
        if if_value is None or rpe is None or rpe <= 0:
            return None
        if_decimal = if_value / 100.0
        if if_decimal < 0.65:
            return None
        if if_decimal < 0.75:
            band_low, band_high = 2, 4
        elif if_decimal < 0.85:
            band_low, band_high = 4, 6
        elif if_decimal < 0.95:
            band_low, band_high = 6, 8
        elif if_decimal < 1.05:
            band_low, band_high = 8, 9
        else:
            band_low, band_high = 9, 10
        if rpe < band_low:
            return "positive"
        if rpe > band_high:
            return "negative"
        return "neutral"

    def _calculate_consistency_index(self, activities: List[Dict], 
                                      past_events: List[Dict]) -> Tuple[Optional[float], Dict]:
        """
        Calculate Consistency Index = Completed Workout Days / Planned Workout Days
        
        Matches by date (not individual workouts) since multiple workouts can be planned per day.
        """
        # Get unique dates with planned workouts (only WORKOUT type)
        planned_dates = set()
        for event in past_events:
            if event.get("category") == "WORKOUT":
                date_str = event.get("start_date_local", "")[:10]
                if date_str:
                    planned_dates.add(date_str)
        
        # Get unique dates with completed activities (cycling only for fair comparison)
        completed_dates = set()
        cycling_types = {"Ride", "VirtualRide", "MountainBikeRide", "GravelRide"}
        
        for activity in activities:
            if activity.get("type") in cycling_types:
                date_str = activity.get("start_date_local", "")[:10]
                if date_str:
                    completed_dates.add(date_str)
        
        # Calculate overlap
        matched_dates = planned_dates & completed_dates
        
        if not planned_dates:
            return None, {
                "planned_days": 0,
                "completed_days": len(completed_dates),
                "matched_days": 0,
                "note": "No planned workouts in period"
            }
        
        consistency_index = round(len(matched_dates) / len(planned_dates), 2)
        
        return consistency_index, {
            "planned_days": len(planned_dates),
            "completed_days": len(completed_dates),
            "matched_days": len(matched_dates),
            "planned_dates": sorted(list(planned_dates)),
            "completed_dates": sorted(list(completed_dates))
        }
    
    def _is_benchmark_expected(self, benchmark_index: Optional[float], 
                                seasonal_context: str) -> Optional[bool]:
        """
        Determine if the benchmark index is within expected range for the season.
        """
        if benchmark_index is None:
            return None
        
        expectations = {
            "Off-season / Transition": (-0.05, -0.02),
            "Early Base": (-0.02, 0.01),
            "Late Base / Build": (0.02, 0.05),
            "Build / Early Race Season": (0.01, 0.04),
            "Peak Race Season": (0.01, 0.03),
            "Late Season / Transition": (-0.03, 0.00),
        }
        
        if seasonal_context in expectations:
            low, high = expectations[seasonal_context]
            return low <= benchmark_index <= high
        
        return None
    
    def _get_ftp_history_span(self) -> Dict[str, int]:
        """Get the number of days of FTP history available for indoor and outdoor"""
        ftp_history = self._load_ftp_history()
        
        result = {"indoor": 0, "outdoor": 0}
        
        for ftp_type in ["indoor", "outdoor"]:
            history = ftp_history.get(ftp_type, {})
            if not history:
                continue
            
            sorted_dates = sorted(history.keys())
            if len(sorted_dates) < 2:
                continue
            
            try:
                oldest = datetime.strptime(sorted_dates[0], "%Y-%m-%d")
                newest = datetime.strptime(sorted_dates[-1], "%Y-%m-%d")
                result[ftp_type] = (newest - oldest).days
            except:
                continue
        
        return result
    
    def _get_daily_tss(self, activities: List[Dict], days: int) -> List[float]:
        """Aggregate TSS by day for the specified number of days"""
        daily_tss = defaultdict(float)
        
        for act in activities:
            date_str = act.get("start_date_local", "")[:10]
            tss = act.get("icu_training_load") or 0
            daily_tss[date_str] += tss
        
        # Create array for last N days (including days with 0 TSS)
        result = []
        for i in range(days - 1, -1, -1):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            result.append(daily_tss.get(date, 0))
        
        return result

    def _get_daily_tss_by_sport(self, activities: List[Dict], days: int) -> Dict[str, List[float]]:
        """
        Aggregate TSS by day AND sport family for per-sport monotony calculation.
        Returns dict of sport_family → [daily_tss_day1, daily_tss_day2, ...] (N elements).
        Only includes sport families that have at least one activity with TSS > 0.
        Sport families are mapped via SPORT_FAMILIES class constant.
        Unmapped activity types are grouped as "other".
        """
        # Collect all sport families present and their daily TSS
        sport_daily_tss = defaultdict(lambda: defaultdict(float))

        for act in activities:
            date_str = act.get("start_date_local", "")[:10]
            tss = act.get("icu_training_load") or 0
            if tss <= 0:
                continue
            activity_type = act.get("type", "Unknown")
            sport_family = self.SPORT_FAMILIES.get(activity_type, "other")
            sport_daily_tss[sport_family][date_str] += tss

        # Build daily arrays for each sport family (including 0 days)
        result = {}
        for sport_family, daily_dict in sport_daily_tss.items():
            daily_array = []
            for i in range(days - 1, -1, -1):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                daily_array.append(daily_dict.get(date, 0))
            result[sport_family] = daily_array

        return result

    # === ZONE EXTRACTION & HARD DAY CLASSIFICATION ===
    # Shared helpers used by _aggregate_zones, derived metrics, and all tier builders.
    # Power zones (icu_zone_times) preferred; HR zones (icu_hr_zone_times) as fallback.
    # HR and power zones are NOT interchangeable — different widths, lag characteristics,
    # and physiological meaning. They are kept in separate accumulators.

    def _get_activity_zones(self, activity: Dict, sport_family: str = None) -> tuple:
        """
        Extract zone times from a single activity.
        
        Returns (zones_dict, basis) where:
        - zones_dict: {"z1": secs, "z2": secs, ...} 
        - basis: "power" | "hr" | None
        
        Power zones (icu_zone_times): list of {"id": "Z3", "secs": 600}
        HR zones (icu_hr_zone_times): flat array of seconds [0, 120, 300, 180, 60]
        
        Default: power preferred, HR fallback.
        When zone_preference is configured for the sport_family, respects that
        preference (e.g. run:hr → HR preferred for running, power fallback).
        HR zones typically 5-zone (indices 0-4 → z1-z5), sometimes 7.
        """
        # Determine preference for this sport family
        prefer_hr = (sport_family and 
                     self.zone_preference.get(sport_family) == "hr")
        
        # Extract both zone sets
        power_zones = None
        icu_zone_times = activity.get("icu_zone_times", [])
        if icu_zone_times:
            pz = {}
            for zone in icu_zone_times:
                zone_id = zone.get("id", "").lower()
                secs = zone.get("secs", 0)
                if zone_id in ("z1", "z2", "z3", "z4", "z5", "z6", "z7"):
                    pz[zone_id] = secs
            if pz:
                power_zones = pz
        
        hr_zones = None
        icu_hr_zone_times = activity.get("icu_hr_zone_times", [])
        if icu_hr_zone_times:
            zone_labels = ("z1", "z2", "z3", "z4", "z5", "z6", "z7")
            hz = {}
            for idx, secs in enumerate(icu_hr_zone_times):
                if idx < len(zone_labels) and secs:
                    hz[zone_labels[idx]] = secs
            if hz:
                hr_zones = hz
        
        # Return based on preference
        if prefer_hr:
            if hr_zones:
                return (hr_zones, "hr")
            if power_zones:
                return (power_zones, "power")
        else:
            if power_zones:
                return (power_zones, "power")
            if hr_zones:
                return (hr_zones, "hr")
        
        return ({}, None)

    @staticmethod
    def _classify_hard_day(day_zones_by_basis: Dict) -> tuple:
        """
        Classify whether a day is hard based on accumulated zone times.
        
        Args:
            day_zones_by_basis: {"power": {"z3": N, "z4": N, ...}, "hr": {"z4": N, "z5": N, ...}}
                Power and HR zones accumulated SEPARATELY across the day's activities.
        
        Returns (is_hard, basis) where:
        - is_hard: True | False | None (None = no zone data, unknown)
        - basis: "power" | "hr" | "mixed" | None
        
        Power ladder (5 rungs, per Seiler/Foster):
            z3+ >= 1800s, z4+ >= 600s, z5+ >= 300s, z6+ >= 120s, z7 >= 60s
        
        HR ladder (2 rungs, conservative — per Seiler 3-zone model):
            z4+ >= 600s (sustained above LT2)
            z5+ >= 300s (VO2max)
        
        HR zones are too wide and lagged for fine-grained classification.
        Short-duration rungs (z6+/z7) invalid for HR due to cardiac lag.
        Z3 skipped for HR to avoid false positives on steady-state runs.
        """
        pz = day_zones_by_basis.get("power", {})
        hz = day_zones_by_basis.get("hr", {})
        
        has_power = bool(pz)
        has_hr = bool(hz)
        
        if not has_power and not has_hr:
            return (None, None)
        
        # Power ladder (unchanged)
        power_hard = False
        if has_power:
            p_z3 = pz.get("z3", 0)
            p_z4 = pz.get("z4", 0)
            p_z5 = pz.get("z5", 0)
            p_z6 = pz.get("z6", 0)
            p_z7 = pz.get("z7", 0)
            power_hard = (
                (p_z3 + p_z4 + p_z5 + p_z6 + p_z7) >= 1800 or  # z3+: 30 min tempo+
                (p_z4 + p_z5 + p_z6 + p_z7) >= 600 or            # z4+: 10 min threshold+
                (p_z5 + p_z6 + p_z7) >= 300 or                    # z5+: 5 min VO2max+
                (p_z6 + p_z7) >= 120 or                            # z6+: 2 min anaerobic+
                p_z7 >= 60                                          # z7:  1 min neuromuscular
            )
        
        # HR ladder (conservative fallback)
        hr_hard = False
        if has_hr:
            h_z4 = hz.get("z4", 0)
            h_z5 = hz.get("z5", 0)
            h_z6 = hz.get("z6", 0)
            h_z7 = hz.get("z7", 0)
            hr_hard = (
                (h_z4 + h_z5 + h_z6 + h_z7) >= 600 or  # z4+: 10 min above LT2
                (h_z5 + h_z6 + h_z7) >= 300              # z5+: 5 min VO2max
            )
        
        is_hard = power_hard or hr_hard
        
        # Determine basis
        if has_power and has_hr:
            basis = "mixed"
        elif has_power:
            basis = "power"
        else:
            basis = "hr"
        
        return (is_hard, basis)

    def _aggregate_zones(self, activities: List[Dict]) -> Dict:
        """
        Aggregate zone times across all activities.
        
        Returns separate Z1, Z2, Z3, and Z4+ times for proper polarization analysis.
        Per Seiler's model:
        - Z1-Z2: Easy (below LT1)
        - Z3: Grey zone / Tempo (between LT1 and LT2) - to be minimized
        - Z4+: Hard / Quality (above LT2) - ~20% target
        
        Uses _get_activity_zones() for consistent zone preference support.
        """
        z1_time = 0
        z2_time = 0
        z3_time = 0
        z4_plus_time = 0
        total_time = 0
        basis_set = set()
        
        for act in activities:
            sf = self.SPORT_FAMILIES.get(act.get("type", ""), None)
            zones, basis = self._get_activity_zones(act, sport_family=sf)
            
            if zones:
                if basis:
                    basis_set.add(basis)
                z1_time += zones.get("z1", 0)
                z2_time += zones.get("z2", 0)
                z3_time += zones.get("z3", 0)
                z4_plus_time += (zones.get("z4", 0) + zones.get("z5", 0) + 
                               zones.get("z6", 0) + zones.get("z7", 0))
                total_time += sum(zones.values())
        
        # Determine aggregate zone basis
        if len(basis_set) > 1:
            zone_basis = "mixed"
        elif len(basis_set) == 1:
            zone_basis = next(iter(basis_set))
        else:
            zone_basis = None
        
        return {
            "z1_time": z1_time,
            "z2_time": z2_time,
            "z3_time": z3_time,
            "z4_plus_time": z4_plus_time,
            "total_time": total_time,
            "zone_basis": zone_basis
        }
    
    # === SEILER TID (Training Intensity Distribution) v3.4.0 ===

    def _aggregate_seiler_zones(self, activities: List[Dict],
                                sport_family_filter: str = None) -> Dict:
        """
        Aggregate 7-zone times into Seiler 3-zone model.

        Mapping (per Treff et al. 2019):
            Seiler Z1 = z1 + z2  (below LT1)
            Seiler Z2 = z3       (between LT1 and LT2)
            Seiler Z3 = z4 + z5 + z6 + z7  (above LT2)

        Uses _get_activity_zones() for consistent zone preference support.

        Args:
            activities: List of activity dicts with zone data
            sport_family_filter: If set, only include activities matching
                                 this sport family (from SPORT_FAMILIES).
                                 Note: this controls which activities enter
                                 the aggregation; zone preference uses each
                                 activity's own sport family (separate lookup).

        Returns dict with z1_seconds, z2_seconds, z3_seconds, total_seconds, zone_basis
        """
        sz1 = 0
        sz2 = 0
        sz3 = 0
        basis_set = set()

        for act in activities:
            # Apply sport family filter if specified (controls inclusion)
            activity_type = act.get("type", "Unknown")
            act_sport_family = self.SPORT_FAMILIES.get(activity_type, "other")
            if sport_family_filter:
                if act_sport_family != sport_family_filter:
                    continue

            # Zone preference uses each activity's own sport family
            zones, basis = self._get_activity_zones(act, sport_family=act_sport_family)

            if zones:
                if basis:
                    basis_set.add(basis)
                sz1 += zones.get("z1", 0) + zones.get("z2", 0)
                sz2 += zones.get("z3", 0)
                sz3 += (zones.get("z4", 0) + zones.get("z5", 0) +
                        zones.get("z6", 0) + zones.get("z7", 0))

        total = sz1 + sz2 + sz3
        
        # Determine aggregate zone basis
        if len(basis_set) > 1:
            zone_basis = "mixed"
        elif len(basis_set) == 1:
            zone_basis = next(iter(basis_set))
        else:
            zone_basis = None
        
        return {
            "z1_seconds": sz1,
            "z2_seconds": sz2,
            "z3_seconds": sz3,
            "total_seconds": total,
            "zone_basis": zone_basis
        }

    def _calculate_polarization_index(self, z1_frac: float, z2_frac: float,
                                       z3_frac: float) -> Optional[float]:
        """
        Calculate Treff Polarization Index.

        Formula: PI = log10((Z1 / Z2) × Z3 × 100)

        Rules (per Treff et al. 2019 + updated literature):
        - Only compute when Z1 > Z3 > Z2 and Z3 >= 0.01
        - If Z2 = 0 but structure is polarized: substitute Z2 = 0.01
        - Otherwise: return None (not a polarization score)
        """
        if z3_frac < 0.01:
            return None
        if not (z1_frac > z3_frac > z2_frac):
            return None

        # Handle Z2 = 0 with substitution (per updated PI formulation)
        effective_z2 = z2_frac if z2_frac > 0 else 0.01

        try:
            raw = (z1_frac / effective_z2) * z3_frac * 100
            if raw <= 0:
                return None
            return round(math.log10(raw), 2)
        except (ValueError, ZeroDivisionError):
            return None

    def _classify_tid(self, z1_frac: float, z2_frac: float,
                      z3_frac: float, pi: Optional[float]) -> str:
        """
        Classify Training Intensity Distribution.

        Explicit priority order (to avoid overlaps):
        1. Z3 < 0.01 and Z1 largest → Base
        2. Z1 > Z3 > Z2 and PI > 2.0 → Polarized
        3. Z1 > Z2 > Z3 → Pyramidal
        4. Z2 largest → Threshold
        5. Z3 largest → High Intensity
        """
        # 1. Base: Z3 near zero, Z1 dominant
        if z3_frac < 0.01 and z1_frac >= z2_frac and z1_frac >= z3_frac:
            return "Base"

        # 2. Polarized: Z1 > Z3 > Z2 and PI > 2.0
        if z1_frac > z3_frac > z2_frac and pi is not None and pi > 2.0:
            return "Polarized"

        # 3. Pyramidal: Z1 > Z2 > Z3
        if z1_frac > z2_frac > z3_frac:
            return "Pyramidal"

        # 4. Threshold: Z2 dominant
        if z2_frac >= z1_frac and z2_frac >= z3_frac:
            return "Threshold"

        # 5. High Intensity: Z3 dominant
        if z3_frac >= z1_frac and z3_frac >= z2_frac:
            return "High Intensity"

        # Fallback: polarized structure but PI <= 2.0
        return "Pyramidal"

    def _build_seiler_tid(self, activities: List[Dict],
                          sport_family_filter: str = None) -> Dict:
        """
        Build complete Seiler TID structure for given activities.

        Returns dict with:
            z1_seconds, z2_seconds, z3_seconds
            z1_pct, z2_pct, z3_pct
            polarization_index (float or null)
            classification (string)
            zone_basis ("power" | "hr" | "mixed" | null)
        """
        zones = self._aggregate_seiler_zones(activities, sport_family_filter)
        total = zones["total_seconds"]
        zone_basis = zones["zone_basis"]

        if total == 0:
            return {
                "z1_seconds": 0,
                "z2_seconds": 0,
                "z3_seconds": 0,
                "z1_pct": None,
                "z2_pct": None,
                "z3_pct": None,
                "polarization_index": None,
                "classification": None,
                "zone_basis": None
            }

        z1_frac = zones["z1_seconds"] / total
        z2_frac = zones["z2_seconds"] / total
        z3_frac = zones["z3_seconds"] / total

        pi = self._calculate_polarization_index(z1_frac, z2_frac, z3_frac)
        classification = self._classify_tid(z1_frac, z2_frac, z3_frac, pi)

        return {
            "z1_seconds": zones["z1_seconds"],
            "z2_seconds": zones["z2_seconds"],
            "z3_seconds": zones["z3_seconds"],
            "z1_pct": round(z1_frac * 100, 1),
            "z2_pct": round(z2_frac * 100, 1),
            "z3_pct": round(z3_frac * 100, 1),
            "polarization_index": pi,
            "classification": classification,
            "zone_basis": zone_basis
        }

    def _calculate_durability(self, activities_7d: List[Dict],
                               activities_28d: List[Dict]) -> Dict:
        """
        Calculate aggregate decoupling as a durability trend.

        Filters to steady-state power sessions only:
        - decoupling is not None
        - variability_index is not None and > 0 and <= 1.05
        - moving_time >= 5400 (90 minutes)

        Per Maunder et al. (2021), Rothschild et al. (2025): meaningful
        cardiac drift requires prolonged exercise. 90 min is the practical
        field floor where drift becomes detectable.

        Negative decoupling is included — it indicates HR drifted down
        relative to power (strong durability or cooling conditions).

        Returns dict with 7d/28d means, high-drift counts, qualifying
        session counts, and trend direction.
        """
        def _filter_qualifying(activities: List[Dict]) -> List[float]:
            """Return decoupling values from qualifying sessions."""
            qualifying = []
            for act in activities:
                # Raw API field names (before _format_activities)
                dec = act.get("icu_hr_decoupling")
                if dec is None:
                    dec = act.get("decoupling")
                vi = act.get("icu_variability_index")
                mt = act.get("moving_time", 0) or 0

                if (dec is not None
                        and vi is not None
                        and vi > 0
                        and vi <= 1.05
                        and mt >= 5400):
                    qualifying.append(dec)
            return qualifying

        vals_7d = _filter_qualifying(activities_7d)
        vals_28d = _filter_qualifying(activities_28d)

        # Compute means (need >= 2 qualifying sessions)
        mean_7d = round(statistics.mean(vals_7d), 2) if len(vals_7d) >= 2 else None
        mean_28d = round(statistics.mean(vals_28d), 2) if len(vals_28d) >= 2 else None

        # High drift counts (> 5%)
        high_drift_7d = sum(1 for v in vals_7d if v > 5.0)
        high_drift_28d = sum(1 for v in vals_28d if v > 5.0)

        # Trend (requires both windows)
        trend = None
        if mean_7d is not None and mean_28d is not None:
            delta = mean_7d - mean_28d
            if delta < -1.0:
                trend = "improving"
            elif delta > 1.0:
                trend = "declining"
            else:
                trend = "stable"

        # Reliability gate: alarm needs N28>=5; declining warning needs N7>=3 AND N28>=5.
        # Flag set whenever either gate would suppress an alert if one were to fire.
        # The mean itself is still computed at N>=2 for situational awareness.
        n7 = len(vals_7d)
        n28 = len(vals_28d)
        reliability_limited = (n28 < 5) or (n7 < 3)
        reliability_note = None
        if reliability_limited:
            reliability_note = (
                f"insufficient qualifying sessions for alert evaluation: "
                f"7d N={n7} (min 3), 28d N={n28} (min 5)"
            )

        if self.debug:
            print(f"  Durability: 7d={mean_7d} ({n7} sessions), "
                  f"28d={mean_28d} ({n28} sessions), trend={trend}, "
                  f"reliability_limited={reliability_limited}")

        return {
            "mean_decoupling_7d": mean_7d,
            "mean_decoupling_28d": mean_28d,
            "high_drift_count_7d": high_drift_7d,
            "high_drift_count_28d": high_drift_28d,
            "qualifying_sessions_7d": n7,
            "qualifying_sessions_28d": n28,
            "trend": trend,
            "reliability_limited": reliability_limited,
            "reliability_note": reliability_note,
            "note": ("Steady-state power sessions only (VI <= 1.05, VI > 0, "
                     ">= 90min, power data). Negative decoupling = strong "
                     "durability. Trend compares 7d vs 28d mean "
                     "(+/-1% = stable). Alerts require N28>=5 (alarm) "
                     "or N7>=3 AND N28>=5 (declining warning) for "
                     "statistical reliability.")
        }

    def _calculate_efficiency_factor(self, activities_7d: List[Dict],
                                      activities_28d: List[Dict]) -> Dict:
        """
        Calculate aggregate Efficiency Factor (EF) as an aerobic fitness trend.

        EF = Normalized Power / Average HR (Coggan). Intervals.icu provides
        this as icu_efficiency_factor per activity.

        Filters to qualifying sessions only:
        - icu_efficiency_factor is not None
        - Cycling types (Ride, VirtualRide, MountainBikeRide, GravelRide)
        - icu_variability_index is not None and > 0 and <= 1.05 (steady-state)
        - moving_time >= 1200 (20 minutes)

        Per TrainingPeaks / Coggan: EF is only valid for aerobic, steady-state
        efforts. Values under 20 minutes are not reliable. Low VI ensures
        steady pacing for meaningful HR-power relationship.

        Rising EF at the same intensity = improving aerobic fitness.
        Compare like-for-like sessions only — EF varies with intensity.

        Returns dict with 7d/28d means, qualifying session counts, and trend.
        """
        CYCLING_TYPES = {"Ride", "VirtualRide", "MountainBikeRide", "GravelRide"}

        def _filter_qualifying(activities: List[Dict]) -> List[float]:
            """Return EF values from qualifying sessions."""
            qualifying = []
            for act in activities:
                ef = act.get("icu_efficiency_factor")
                vi = act.get("icu_variability_index")
                mt = act.get("moving_time", 0) or 0
                act_type = act.get("type", "")

                if (ef is not None
                        and act_type in CYCLING_TYPES
                        and vi is not None
                        and vi > 0
                        and vi <= 1.05
                        and mt >= 1200):
                    qualifying.append(ef)
            return qualifying

        vals_7d = _filter_qualifying(activities_7d)
        vals_28d = _filter_qualifying(activities_28d)

        # Compute means (need >= 2 qualifying sessions)
        mean_7d = round(statistics.mean(vals_7d), 2) if len(vals_7d) >= 2 else None
        mean_28d = round(statistics.mean(vals_28d), 2) if len(vals_28d) >= 2 else None

        # Trend (requires both windows)
        trend = None
        if mean_7d is not None and mean_28d is not None:
            delta = mean_7d - mean_28d
            if delta > 0.03:
                trend = "improving"
            elif delta < -0.03:
                trend = "declining"
            else:
                trend = "stable"

        if self.debug:
            print(f"  Efficiency Factor: 7d={mean_7d} ({len(vals_7d)} sessions), "
                  f"28d={mean_28d} ({len(vals_28d)} sessions), trend={trend}")

        return {
            "mean_ef_7d": mean_7d,
            "mean_ef_28d": mean_28d,
            "qualifying_sessions_7d": len(vals_7d),
            "qualifying_sessions_28d": len(vals_28d),
            "trend": trend,
            "note": ("Steady-state cycling sessions only (VI <= 1.05, VI > 0, "
                     ">= 20min, power+HR data). Rising EF = improving aerobic "
                     "efficiency. Compare like-for-like sessions only — "
                     "EF varies with intensity. Trend compares 7d vs 28d mean "
                     "(+/-0.03 = stable).")
        }

    def _calculate_hrrc_trend(self, activities_7d: List[Dict],
                               activities_28d: List[Dict]) -> Dict:
        """
        Calculate aggregate HRRc (heart rate recovery) as a recovery quality trend.

        HRRc = largest 60-second HR drop (bpm) after exceeding configured
        threshold HR for >1 minute. Intervals.icu API field: icu_hrr,
        displayed as HRRc. Higher = faster parasympathetic recovery.

        Qualifying criteria: icu_hrr is not None (self-selects — only fires
        when threshold HR held >1min and cooldown recorded).

        Window minimums: 7d >= 1 session, 28d >= 3 sessions.
        Trend: 7d mean vs 28d mean, >10% difference = meaningful
        (conservative threshold for noisy field metric; lab CV ~4% but
        field CV likely 10-15% due to variable workout type, intensity,
        and recording conditions).

        References:
        - Fecchio et al. (2019) systematic review: HRR60s exhibits high
          reliability (ICC up to 0.99, CV 3.4-13.5% across protocols)
        - Lamberts et al. (2024): HRR60s ICC=0.97, TEM=4.3% in cyclists
        - Buchheit (2006): HRR associated with training loads, not VO2max
        - Intervals.icu: renamed HRR to HRRc to avoid confusion with
          Heart Rate Reserve (Tinker, 2019)
        """
        def _filter_qualifying(activities: List[Dict]) -> List[float]:
            """Return HRRc values from sessions where it was recorded."""
            qualifying = []
            for act in activities:
                hrrc = act.get("icu_hrr")
                if hrrc is None:
                    continue
                # API may return a dict (e.g. {"value": 34}) or a plain number
                if isinstance(hrrc, dict):
                    _v = hrrc.get("value")
                    if _v is None:
                        _v = hrrc.get("hrr")
                    hrrc = _v
                if isinstance(hrrc, (int, float)) and hrrc > 0:
                    qualifying.append(float(hrrc))
            return qualifying

        vals_7d = _filter_qualifying(activities_7d)
        vals_28d = _filter_qualifying(activities_28d)

        # 7d: >= 1 session (report value or mean)
        mean_7d = round(statistics.mean(vals_7d), 1) if len(vals_7d) >= 1 else None
        # 28d: >= 3 sessions (noise dampening for field metric)
        mean_28d = round(statistics.mean(vals_28d), 1) if len(vals_28d) >= 3 else None

        # Trend: >10% difference = meaningful (conservative for field noise)
        trend = None
        if mean_7d is not None and mean_28d is not None and mean_28d > 0:
            pct_change = (mean_7d - mean_28d) / mean_28d
            if pct_change > 0.10:
                trend = "improving"
            elif pct_change < -0.10:
                trend = "declining"
            else:
                trend = "stable"

        if self.debug:
            print(f"  HRRc: 7d={mean_7d} ({len(vals_7d)} sessions), "
                  f"28d={mean_28d} ({len(vals_28d)} sessions), trend={trend}")

        return {
            "mean_hrrc_7d": mean_7d,
            "mean_hrrc_28d": mean_28d,
            "qualifying_sessions_7d": len(vals_7d),
            "qualifying_sessions_28d": len(vals_28d),
            "trend": trend,
            "note": ("HRRc = heart rate recovery (largest 60s HR drop in bpm "
                     "after exceeding threshold HR for >1 min). Higher = "
                     "better parasympathetic recovery. Null when threshold "
                     "not reached, recording stopped before cooldown, or no "
                     "HR data. Trend: 7d mean vs 28d mean, >10% = meaningful "
                     "(min 1 session/7d, 3 sessions/28d). Display only — "
                     "not wired into readiness_decision signals.")
        }

    def _calculate_power_curve_delta(self, power_curve_data: Dict = None,
                                      power_curve_dates: Tuple = None) -> Dict:
        """
        Calculate power curve delta across two 28-day windows.
        
        Extracts MMP at five anchor durations (5s, 60s, 300s, 1200s, 3600s)
        from each window. Computes % change per anchor and rotation_index.
        
        Rotation index = mean(short-anchor changes) - mean(long-anchor changes)
        where short = 5s, 60s and long = 1200s, 3600s. 300s excluded (transitional).
        Positive = sprint-biased gains, negative = endurance-biased gains.
        
        Curve matching by response ID field, not list index — handles empty
        windows gracefully (API omits curves with no data).
        
        Guards:
        - Per-anchor: null if duration not in secs array or watts is 0/None
        - pct_change: null if either window's anchor watts is 0/None
        - Block-level: null if either window has < 3 non-null anchors
        - Rotation: null if any of the 4 component anchors has null pct_change
        
        References:
        - Pinot & Grappe (2011): power-duration profiling across durations
        - Quod et al. (2010): MMP tracking for training monitoring
        - Intervals.icu API: GET /api/v1/athlete/{id}/power-curves
        """
        ANCHORS = {"5s": 5, "60s": 60, "300s": 300, "1200s": 1200, "3600s": 3600}
        
        # Build null block (reused for all early returns)
        def _null_block(note="Insufficient power data in one or both windows."):
            dates = {}
            if power_curve_dates:
                dates = {
                    "current_window": {"start": power_curve_dates[0], "end": power_curve_dates[1]},
                    "previous_window": {"start": power_curve_dates[2], "end": power_curve_dates[3]},
                }
            return {
                "window_days": 28,
                **dates,
                "anchors": None,
                "rotation_index": None,
                "note": note
            }
        
        # Guard: no data or no dates
        if not power_curve_data or not power_curve_dates:
            return _null_block()
        
        curves_list = power_curve_data.get("list", [])
        if not curves_list:
            return _null_block()
        
        # Match curves by ID, not list index
        pc_start1, pc_end1, pc_start2, pc_end2 = power_curve_dates
        current_id = f"r.{pc_start1}.{pc_end1}"
        previous_id = f"r.{pc_start2}.{pc_end2}"
        
        curves_by_id = {c["id"]: c for c in curves_list if "id" in c}
        current_curve = curves_by_id.get(current_id)
        previous_curve = curves_by_id.get(previous_id)
        
        if not current_curve or not previous_curve:
            missing = []
            if not current_curve:
                missing.append("current")
            if not previous_curve:
                missing.append("previous")
            return _null_block(f"No power data in {' and '.join(missing)} window(s).")
        
        # Extract anchor values from both curves
        anchors = {}
        for label, duration_secs in ANCHORS.items():
            cur_secs = current_curve.get("secs", [])
            cur_watts = current_curve.get("watts", [])
            prev_secs = previous_curve.get("secs", [])
            prev_watts = previous_curve.get("watts", [])
            
            # Current window anchor
            cur_w = None
            if duration_secs in cur_secs:
                idx = cur_secs.index(duration_secs)
                val = cur_watts[idx] if idx < len(cur_watts) else None
                if val is not None and val > 0:
                    cur_w = val
            
            # Previous window anchor
            prev_w = None
            if duration_secs in prev_secs:
                idx = prev_secs.index(duration_secs)
                val = prev_watts[idx] if idx < len(prev_watts) else None
                if val is not None and val > 0:
                    prev_w = val
            
            # Compute pct_change (null if either side is null)
            pct_change = None
            if cur_w is not None and prev_w is not None:
                pct_change = round((cur_w - prev_w) / prev_w * 100, 1)
            
            anchors[label] = {
                "current_watts": cur_w,
                "previous_watts": prev_w,
                "pct_change": pct_change
            }
        
        # Block-level guard: need >= 3 non-null anchors in EACH window
        current_valid = sum(1 for a in anchors.values() if a["current_watts"] is not None)
        previous_valid = sum(1 for a in anchors.values() if a["previous_watts"] is not None)
        
        if current_valid < 3 or previous_valid < 3:
            return _null_block(f"Too few valid anchors (current: {current_valid}, previous: {previous_valid}, need 3+).")
        
        # Rotation index: mean(5s, 60s) - mean(1200s, 3600s), 300s excluded
        short_changes = [anchors["5s"]["pct_change"], anchors["60s"]["pct_change"]]
        long_changes = [anchors["1200s"]["pct_change"], anchors["3600s"]["pct_change"]]
        
        rotation_index = None
        if all(v is not None for v in short_changes + long_changes):
            short_mean = sum(short_changes) / len(short_changes)
            long_mean = sum(long_changes) / len(long_changes)
            rotation_index = round(short_mean - long_mean, 1)
        
        if self.debug:
            if rotation_index is not None:
                print(f"  📈 Power curve delta: rotation={rotation_index:+.1f}")
            else:
                print(f"  📈 Power curve delta: rotation unavailable (missing anchor data)")
            for label, vals in anchors.items():
                if vals["pct_change"] is not None:
                    print(f"      {label}: {vals['current_watts']}W vs {vals['previous_watts']}W ({vals['pct_change']:+.1f}%)")
        
        return {
            "window_days": 28,
            "current_window": {"start": pc_start1, "end": pc_end1},
            "previous_window": {"start": pc_start2, "end": pc_end2},
            "anchors": anchors,
            "rotation_index": rotation_index,
            "note": ("Compares MMP at 5 anchor durations (5s neuromuscular, 60s anaerobic, "
                     "300s MAP, 1200s threshold, 3600s endurance) across two 28d windows. "
                     "rotation_index = mean(5s,60s pct_change) - mean(1200s,3600s pct_change). "
                     "Positive = sprint-biased gains, negative = endurance-biased. "
                     "300s excluded from rotation (transitional). "
                     "Null when either window has fewer than 3 valid anchor durations.")
        }

    def _calculate_hr_curve_delta(self, hr_curve_data: Dict = None,
                                   curve_dates: Tuple = None) -> Dict:
        """
        Calculate HR curve delta across two 28-day windows.
        
        Extracts max sustained HR at four anchor durations (60s, 300s, 1200s, 3600s)
        from each window. Computes % change per anchor and rotation_index.
        
        No 5s anchor — peak HR at 5s is just max HR, not an energy system signal.
        
        Rotation index = mean(short-anchor changes) - mean(long-anchor changes)
        where short = 60s, 300s and long = 1200s, 3600s.
        Positive = intensity-biased HR shift, negative = endurance-biased shift.
        
        IMPORTANT: Unlike power where higher is always better, rising max sustained HR
        is ambiguous — could indicate improved cardiac output (fitness gain) or
        accumulated fatigue / dehydration / heat. The AI coach must cross-reference
        with resting HRV, resting HR, RPE trends, and environmental context.
        
        No sport filter on the API call — HR is physiological, not sport-specific.
        Max sustained HR at 300s is max sustained HR at 300s whether from cycling,
        running, or SkiErg. The curve is naturally dominated by the hardest efforts.
        
        Data key is 'values' (not 'watts' as in power curves).
        
        Guards: same as power_curve_delta — per-anchor null, div-by-zero, block-level <3.
        """
        ANCHORS = {"60s": 60, "300s": 300, "1200s": 1200, "3600s": 3600}
        
        def _null_block(note="Insufficient HR data in one or both windows."):
            dates = {}
            if curve_dates:
                dates = {
                    "current_window": {"start": curve_dates[0], "end": curve_dates[1]},
                    "previous_window": {"start": curve_dates[2], "end": curve_dates[3]},
                }
            return {
                "window_days": 28,
                **dates,
                "anchors": None,
                "rotation_index": None,
                "note": note
            }
        
        # Guard: no data or no dates
        if not hr_curve_data or not curve_dates:
            return _null_block()
        
        curves_list = hr_curve_data.get("list", [])
        if not curves_list:
            return _null_block()
        
        # Match curves by ID, not list index
        pc_start1, pc_end1, pc_start2, pc_end2 = curve_dates
        current_id = f"r.{pc_start1}.{pc_end1}"
        previous_id = f"r.{pc_start2}.{pc_end2}"
        
        curves_by_id = {c["id"]: c for c in curves_list if "id" in c}
        current_curve = curves_by_id.get(current_id)
        previous_curve = curves_by_id.get(previous_id)
        
        if not current_curve or not previous_curve:
            missing = []
            if not current_curve:
                missing.append("current")
            if not previous_curve:
                missing.append("previous")
            return _null_block(f"No HR data in {' and '.join(missing)} window(s).")
        
        # Extract anchor values — HR curves use 'values' key, not 'watts'
        anchors = {}
        for label, duration_secs in ANCHORS.items():
            cur_secs = current_curve.get("secs", [])
            cur_values = current_curve.get("values", [])
            prev_secs = previous_curve.get("secs", [])
            prev_values = previous_curve.get("values", [])
            
            # Current window anchor
            cur_v = None
            if duration_secs in cur_secs:
                idx = cur_secs.index(duration_secs)
                val = cur_values[idx] if idx < len(cur_values) else None
                if val is not None and val > 0:
                    cur_v = val
            
            # Previous window anchor
            prev_v = None
            if duration_secs in prev_secs:
                idx = prev_secs.index(duration_secs)
                val = prev_values[idx] if idx < len(prev_values) else None
                if val is not None and val > 0:
                    prev_v = val
            
            # Compute pct_change (null if either side is null)
            pct_change = None
            if cur_v is not None and prev_v is not None:
                pct_change = round((cur_v - prev_v) / prev_v * 100, 1)
            
            anchors[label] = {
                "current_bpm": cur_v,
                "previous_bpm": prev_v,
                "pct_change": pct_change
            }
        
        # Block-level guard: need >= 3 non-null anchors in EACH window
        current_valid = sum(1 for a in anchors.values() if a["current_bpm"] is not None)
        previous_valid = sum(1 for a in anchors.values() if a["previous_bpm"] is not None)
        
        if current_valid < 3 or previous_valid < 3:
            return _null_block(f"Too few valid anchors (current: {current_valid}, previous: {previous_valid}, need 3+).")
        
        # Rotation index: mean(60s, 300s) - mean(1200s, 3600s)
        short_changes = [anchors["60s"]["pct_change"], anchors["300s"]["pct_change"]]
        long_changes = [anchors["1200s"]["pct_change"], anchors["3600s"]["pct_change"]]
        
        rotation_index = None
        if all(v is not None for v in short_changes + long_changes):
            short_mean = sum(short_changes) / len(short_changes)
            long_mean = sum(long_changes) / len(long_changes)
            rotation_index = round(short_mean - long_mean, 1)
        
        if self.debug:
            if rotation_index is not None:
                print(f"  📈 HR curve delta: rotation={rotation_index:+.1f}")
            else:
                print(f"  📈 HR curve delta: rotation unavailable (missing anchor data)")
            for label, vals in anchors.items():
                if vals["pct_change"] is not None:
                    print(f"      {label}: {vals['current_bpm']}bpm vs {vals['previous_bpm']}bpm ({vals['pct_change']:+.1f}%)")
        
        return {
            "window_days": 28,
            "current_window": {"start": pc_start1, "end": pc_end1},
            "previous_window": {"start": pc_start2, "end": pc_end2},
            "anchors": anchors,
            "rotation_index": rotation_index,
            "note": ("Compares max sustained HR at 4 anchor durations (60s anaerobic ceiling, "
                     "300s VO2max HR, 1200s threshold HR, 3600s endurance HR) across two 28d windows. "
                     "rotation_index = mean(60s,300s pct_change) - mean(1200s,3600s pct_change). "
                     "Positive = intensity-biased HR shift, negative = endurance-biased. "
                     "No sport filter — HR is cross-sport physiological (dominated by hardest efforts). "
                     "IMPORTANT: rising max sustained HR is ambiguous — may indicate improved cardiac "
                     "output (good) or accumulated fatigue/dehydration/heat (bad). Cross-reference with "
                     "resting HRV, resting HR, RPE, and environmental context before interpreting. "
                     "Null when either window has fewer than 3 valid anchor durations.")
        }

    def _calculate_dfa_a1_profile(self) -> Optional[Dict]:
        """
        Build dfa_a1_profile for latest.json capability block.

        Reads from self._intervals_data (must be set first by _generate_intervals).
        Returns:
          - latest_session: most recent activity with a sufficient dfa block (any sport)
          - trailing_by_sport: per sport family, aggregated rollups across the latest
            DFA_TRAILING_WINDOW_N sessions, with confidence + validated flags

        Returns None if no intervals data or no DFA-equipped sessions exist.
        """
        intervals_data = getattr(self, "_intervals_data", None)
        if not intervals_data:
            return None
        activities = intervals_data.get("activities", [])
        # Keep only activities with a dfa block (i.e. AlphaHRV recorded), most recent first
        dfa_activities = [a for a in activities if a.get("dfa") is not None]
        if not dfa_activities:
            return None
        dfa_activities.sort(key=lambda a: a.get("date", ""), reverse=True)

        # --- latest_session: most recent SUFFICIENT session ---
        latest_session = None
        for a in dfa_activities:
            block = a["dfa"]
            quality = block.get("quality", {})
            if quality.get("sufficient"):
                tiz_split = {}
                for key, label in [
                    ("tiz_below_lt1", "below_lt1"),
                    ("tiz_lt1_transition", "lt1_transition"),
                    ("tiz_transition_lt2", "transition_lt2"),
                    ("tiz_above_lt2", "above_lt2"),
                ]:
                    band = block.get(key)
                    tiz_split[label] = band["pct"] if band else 0.0
                drift = block.get("drift") or {}
                latest_session = {
                    "activity_id": a.get("activity_id"),
                    "date": a.get("date"),
                    "name": a.get("name"),
                    "sport": a.get("type"),
                    "validated": self.SPORT_FAMILIES.get(a.get("type", "")) in self.DFA_VALIDATED_SPORTS,
                    "avg": block.get("avg"),
                    "tiz_split_pct": tiz_split,
                    "drift_delta": drift.get("delta"),
                    "drift_interpretable": drift.get("interpretable"),
                    "quality_pct": quality.get("valid_pct"),
                    "sufficient": True,
                }
                break

        # If no sufficient session, surface the most recent insufficient one so the AI
        # can see "AlphaHRV ran but unusable" instead of "no data".
        if latest_session is None:
            a = dfa_activities[0]
            latest_session = {
                "activity_id": a.get("activity_id"),
                "date": a.get("date"),
                "name": a.get("name"),
                "sport": a.get("type"),
                "validated": self.SPORT_FAMILIES.get(a.get("type", "")) in self.DFA_VALIDATED_SPORTS,
                "avg": None,
                "tiz_split_pct": None,
                "drift_delta": None,
                "drift_interpretable": None,
                "quality_pct": a["dfa"].get("quality", {}).get("valid_pct"),
                "sufficient": False,
            }

        # --- trailing_by_sport: per-sport aggregation across last N sufficient sessions ---
        trailing_by_sport = {}
        # Group dfa activities by sport family
        by_family = {}
        for a in dfa_activities:
            if not a["dfa"].get("quality", {}).get("sufficient"):
                continue
            family = self.SPORT_FAMILIES.get(a.get("type", ""), "other")
            by_family.setdefault(family, []).append(a)

        for family, acts in by_family.items():
            window = acts[: self.DFA_TRAILING_WINDOW_N]
            n = len(window)
            if n == 0:
                continue
            avg_dfa_values = [a["dfa"]["avg"] for a in window if a["dfa"].get("avg") is not None]
            avg_dfa = round(sum(avg_dfa_values) / len(avg_dfa_values), 3) if avg_dfa_values else None
            drift_values = [
                a["dfa"]["drift"]["delta"]
                for a in window
                if a["dfa"].get("drift") and a["dfa"]["drift"].get("interpretable")
                and a["dfa"]["drift"].get("delta") is not None
            ]
            drift_mean = round(sum(drift_values) / len(drift_values), 3) if drift_values else None

            # Threshold estimates from crossing bands — only sessions with sufficient dwell
            def _avg_crossing(key, field, subset=None):
                source = subset if subset is not None else window
                vals = []
                for a in source:
                    cb = a["dfa"].get(key)
                    if cb and cb.get("secs_in_band", 0) >= self.DFA_MIN_CROSSING_DWELL_SECS:
                        v = cb.get(field)
                        if v is not None:
                            vals.append(v)
                if not vals:
                    return None, 0
                return round(sum(vals) / len(vals)), len(vals)

            # HR estimates — pooled across all sessions (physiology signal, not environment-dependent)
            lt1_hr, lt1_n_hr = _avg_crossing("lt1_crossing", "avg_hr")
            lt2_hr, lt2_n_hr = _avg_crossing("lt2_crossing", "avg_hr")

            # Watts estimates — split by environment for cycling, pooled for other sports
            is_cycling = (family == "cycling")
            if is_cycling:
                indoor = [a for a in window if self._is_indoor_cycling(a.get("type", ""))]
                outdoor = [a for a in window if not self._is_indoor_cycling(a.get("type", ""))]
                lt1_watts_out, lt1_n_w_out = _avg_crossing("lt1_crossing", "avg_watts", outdoor)
                lt1_watts_in, lt1_n_w_in = _avg_crossing("lt1_crossing", "avg_watts", indoor)
                lt2_watts_out, lt2_n_w_out = _avg_crossing("lt2_crossing", "avg_watts", outdoor)
                lt2_watts_in, lt2_n_w_in = _avg_crossing("lt2_crossing", "avg_watts", indoor)
                lt1_n_w = lt1_n_w_out + lt1_n_w_in
                lt2_n_w = lt2_n_w_out + lt2_n_w_in
            else:
                lt1_watts, lt1_n_w = _avg_crossing("lt1_crossing", "avg_watts")
                lt2_watts, lt2_n_w = _avg_crossing("lt2_crossing", "avg_watts")

            # Observability: how many sessions in window had ≥dwell threshold in each band.
            # If confidence stays stuck at low/null with high n_sessions, these counts reveal
            # whether the issue is "athlete rarely crosses this band" (count low) vs some
            # other failure mode. Diagnostic only — not used in confidence logic itself.
            lt1_crossing_sessions = sum(
                1 for a in window
                if (a["dfa"].get("lt1_crossing") or {}).get("secs_in_band", 0)
                >= self.DFA_MIN_CROSSING_DWELL_SECS
            )
            lt2_crossing_sessions = sum(
                1 for a in window
                if (a["dfa"].get("lt2_crossing") or {}).get("secs_in_band", 0)
                >= self.DFA_MIN_CROSSING_DWELL_SECS
            )

            # Confidence based on n sessions contributing to crossing estimates
            crossing_n = max(lt1_n_hr, lt1_n_w, lt2_n_hr, lt2_n_w)
            if crossing_n >= 6:
                confidence = "high"
            elif crossing_n >= 4:
                confidence = "moderate"
            elif crossing_n >= 3:
                confidence = "low"
            else:
                confidence = None  # not enough sessions for any threshold estimate

            quality_avg = round(
                sum(a["dfa"]["quality"]["valid_pct"] for a in window) / n, 1
            )

            validated = family in self.DFA_VALIDATED_SPORTS

            # Build estimate blocks — cycling splits watts by environment, others keep pooled
            if is_cycling:
                lt1_est = {
                    "hr": lt1_hr if confidence else None,
                    "watts_outdoor": lt1_watts_out if confidence else None,
                    "watts_indoor": lt1_watts_in if confidence else None,
                    "n_sessions": max(lt1_n_hr, lt1_n_w),
                    "n_sessions_outdoor": lt1_n_w_out,
                    "n_sessions_indoor": lt1_n_w_in,
                } if confidence else None
                lt2_est = {
                    "hr": lt2_hr if confidence else None,
                    "watts_outdoor": lt2_watts_out if confidence else None,
                    "watts_indoor": lt2_watts_in if confidence else None,
                    "n_sessions": max(lt2_n_hr, lt2_n_w),
                    "n_sessions_outdoor": lt2_n_w_out,
                    "n_sessions_indoor": lt2_n_w_in,
                } if confidence else None
            else:
                lt1_est = {
                    "hr": lt1_hr if confidence else None,
                    "watts": lt1_watts if confidence else None,
                    "n_sessions": max(lt1_n_hr, lt1_n_w),
                } if confidence else None
                lt2_est = {
                    "hr": lt2_hr if confidence else None,
                    "watts": lt2_watts if confidence else None,
                    "n_sessions": max(lt2_n_hr, lt2_n_w),
                } if confidence else None

            sport_block = {
                "n_sessions": n,
                "date_range": [window[-1].get("date"), window[0].get("date")],
                "avg_dfa_a1": avg_dfa,
                "drift_delta_mean": drift_mean,
                "lt1_crossing_sessions": lt1_crossing_sessions,
                "lt2_crossing_sessions": lt2_crossing_sessions,
                "lt1_estimate": lt1_est,
                "lt2_estimate": lt2_est,
                "quality_avg_pct": quality_avg,
                "validated": validated,
                "confidence": confidence,
            }
            if not validated:
                sport_block["note"] = (
                    f"DFA a1 threshold mapping (1.0/0.5) is cycling-validated. "
                    f"{family} thresholds may differ — treat estimates as informational only."
                )
            trailing_by_sport[family] = sport_block

        return {
            "latest_session": latest_session,
            "trailing_by_sport": trailing_by_sport,
        }

    def _calculate_sustainability_profile(self, sustainability_curves: Dict,
                                           sustainability_window: Tuple,
                                           power_model: Dict,
                                           sport_settings: Dict,
                                           wellness_7d: List[Dict],
                                           wellness_extended: List[Dict],
                                           icu_weight: float = None) -> Dict:
        """
        Build per-sport sustainability profile for race estimation (v3.91).
        
        For each active sport family, extracts MMP and max sustained HR at
        sport-specific anchor durations from a single wider window (42d default).
        
        Three model layers for cycling:
        1. Actual MMP — observed from training data
        2. Coggan predicted — FTP × duration factor (Allen & Coggan, 3rd ed.)
        3. CP/W' predicted — P = CP + W'/t (Skiba critical power model)
        
        Non-cycling power sports get actual MMP only (no published duration
        factors, no sport-specific CP/W' values).
        
        Indoor/outdoor handling (cycling only): fetches Ride and VirtualRide
        separately, takes max at each anchor. Source flag indicates which
        environment produced the best effort.
        
        Weight fallback chain: today's wellness → most recent in wellness
        history → athlete.icu_weight → null (all W/kg fields null).
        
        References:
        - Allen & Coggan, Training and Racing with a Power Meter (3rd ed.)
        - Skiba et al. (2012): CP/W' model for performance prediction
        - Pinot & Grappe (2011): power-duration profiling
        """
        # Null block for early returns
        def _null_profile(note="No sustainability data available."):
            result = {"note": note}
            if sustainability_window:
                result["window"] = {
                    "days": self.SUSTAINABILITY_WINDOW_DAYS,
                    "start": sustainability_window[0],
                    "end": sustainability_window[1]
                }
            return result
        
        if not sustainability_curves or not sustainability_window:
            return _null_profile()
        
        # --- Weight fallback chain ---
        weight_kg = None
        weight_source = None
        
        # 1. Today's wellness (last entry in 7d)
        if wellness_7d:
            for w in reversed(wellness_7d):
                if w.get("weight"):
                    weight_kg = round(w["weight"], 1)
                    weight_source = "wellness_recent"
                    break
        
        # 2. Extended wellness history
        if weight_kg is None and wellness_extended:
            for w in reversed(wellness_extended):
                if w.get("weight"):
                    weight_kg = round(w["weight"], 1)
                    weight_source = "wellness_extended"
                    break
        
        # 3. Athlete profile weight (icu_weight)
        if weight_kg is None and icu_weight is not None:
            weight_kg = round(icu_weight, 1)
            weight_source = "athlete_profile"
        
        if self.debug:
            if weight_kg:
                print(f"  ⚖️  Sustainability weight: {weight_kg}kg ({weight_source})")
            else:
                print(f"  ⚖️  Sustainability weight: unavailable (W/kg will be null)")
        
        # --- FTP staleness (cycling only) ---
        ftp_staleness_days = None
        try:
            ftp_history = self._load_ftp_history()
            all_dates = []
            for ftp_type in ["indoor", "outdoor"]:
                dates = list(ftp_history.get(ftp_type, {}).keys())
                all_dates.extend(dates)
            if all_dates:
                most_recent = max(all_dates)
                most_recent_date = datetime.strptime(most_recent, "%Y-%m-%d")
                ftp_staleness_days = (datetime.now() - most_recent_date).days
        except Exception:
            pass
        
        # --- Cycling model inputs ---
        cycling_ftp = None
        cycling_w_prime = None
        cycling_settings = sport_settings.get("cycling", {})
        
        # Use athlete-set FTP from sportSettings (not eFTP)
        cycling_ftp = cycling_settings.get("ftp")
        if not cycling_ftp:
            # Fallback to indoor FTP if outdoor not set
            cycling_ftp = cycling_settings.get("ftp_indoor")
        
        cycling_w_prime = power_model.get("w_prime")  # In joules from API
        
        # --- Build per-sport blocks ---
        profile = {
            "window": {
                "days": self.SUSTAINABILITY_WINDOW_DAYS,
                "start": sustainability_window[0],
                "end": sustainability_window[1]
            },
            "weight_kg": weight_kg,
            "weight_source": weight_source,
        }
        
        for sport_family, sport_data in sustainability_curves.items():
            anchors_map = self.SUSTAINABILITY_ANCHORS.get(sport_family)
            if not anchors_map:
                continue
            
            sport_lthr = sport_settings.get(sport_family, {}).get("lthr")
            power_curves_by_type = sport_data.get("power", {})
            hr_curves_by_type = sport_data.get("hr", {})
            
            is_cycling = (sport_family == "cycling")
            
            # --- Extract MMP per anchor (power) ---
            # For cycling: max(Ride, VirtualRide) at each anchor with source tracking
            anchors = {}
            curve_id = f"r.{sustainability_window[0]}.{sustainability_window[1]}"
            
            for label, duration_secs in anchors_map.items():
                best_watts = None
                best_source = None
                
                for ptype, pdata in power_curves_by_type.items():
                    curves_list = pdata.get("list", []) if isinstance(pdata, dict) else []
                    curves_by_id = {c["id"]: c for c in curves_list if "id" in c}
                    curve = curves_by_id.get(curve_id)
                    if not curve:
                        continue
                    
                    secs = curve.get("secs", [])
                    watts = curve.get("watts", [])
                    
                    if duration_secs in secs:
                        idx = secs.index(duration_secs)
                        val = watts[idx] if idx < len(watts) else None
                        if val is not None and val > 0:
                            if best_watts is None or val > best_watts:
                                best_watts = val
                                if is_cycling:
                                    if self._is_indoor_cycling(ptype):
                                        best_source = "observed_indoor"
                                    else:
                                        best_source = "observed_outdoor"
                                else:
                                    best_source = "observed"
                
                # --- Extract max sustained HR at this anchor ---
                best_hr = None
                
                for htype, hdata in hr_curves_by_type.items():
                    curves_list = hdata.get("list", []) if isinstance(hdata, dict) else []
                    curves_by_id = {c["id"]: c for c in curves_list if "id" in c}
                    curve = curves_by_id.get(curve_id)
                    if not curve:
                        continue
                    
                    secs = curve.get("secs", [])
                    values = curve.get("values", [])
                    
                    if duration_secs in secs:
                        idx = secs.index(duration_secs)
                        val = values[idx] if idx < len(values) else None
                        if val is not None and val > 0:
                            if best_hr is None or val > best_hr:
                                best_hr = round(val)
                
                # --- Compute W/kg ---
                actual_wpkg = None
                if best_watts is not None and weight_kg is not None and weight_kg > 0:
                    actual_wpkg = round(best_watts / weight_kg, 2)
                
                # --- Compute %LTHR ---
                pct_lthr = None
                if best_hr is not None and sport_lthr is not None and sport_lthr > 0:
                    pct_lthr = round(best_hr / sport_lthr * 100, 1)
                
                # --- Coggan model (cycling only) ---
                coggan_watts = None
                coggan_wpkg = None
                if is_cycling and cycling_ftp and duration_secs in self.COGGAN_DURATION_FACTORS:
                    coggan_watts = round(cycling_ftp * self.COGGAN_DURATION_FACTORS[duration_secs])
                    if weight_kg and weight_kg > 0:
                        coggan_wpkg = round(coggan_watts / weight_kg, 2)
                
                # --- CP/W' model (cycling only) ---
                cp_model_watts = None
                cp_model_wpkg = None
                if is_cycling and cycling_ftp and cycling_w_prime and duration_secs > 0:
                    # P = CP + W'/t  (CP approximated by FTP for this model)
                    cp_model_watts = round(cycling_ftp + cycling_w_prime / duration_secs)
                    if weight_kg and weight_kg > 0:
                        cp_model_wpkg = round(cp_model_watts / weight_kg, 2)
                
                # --- Model divergence (actual vs CP model) ---
                model_divergence_pct = None
                if best_watts is not None and cp_model_watts is not None and cp_model_watts > 0:
                    model_divergence_pct = round((best_watts - cp_model_watts) / cp_model_watts * 100, 1)
                
                # --- Best effort date (not available from aggregate curves) ---
                # The power-curves endpoint returns aggregate MMP, not per-activity.
                # Date/recency fields would require cross-referencing recent_activities,
                # which isn't passed this deep. Omitted by design — the AI can cross-ref.
                
                anchor_data = {
                    "actual_watts": best_watts,
                    "actual_wpkg": actual_wpkg,
                    "actual_hr": best_hr,
                    "pct_lthr": pct_lthr,
                    "source": best_source,
                }
                
                # Cycling gets model layers
                if is_cycling:
                    anchor_data["coggan_watts"] = coggan_watts
                    anchor_data["coggan_wpkg"] = coggan_wpkg
                    anchor_data["cp_model_watts"] = cp_model_watts
                    anchor_data["cp_model_wpkg"] = cp_model_wpkg
                    anchor_data["model_divergence_pct"] = model_divergence_pct
                
                anchors[label] = anchor_data
            
            # --- Coverage ratio ---
            total_anchors = len(anchors)
            observed_anchors = sum(1 for a in anchors.values() if a.get("actual_watts") is not None)
            coverage_ratio = round(observed_anchors / total_anchors, 2) if total_anchors > 0 else 0
            
            # Block-level guard: need >= 2 non-null anchors
            if observed_anchors < 2:
                profile[sport_family] = {
                    "anchors": None,
                    "coverage_ratio": coverage_ratio,
                    "note": f"Too few observed anchors ({observed_anchors}, need 2+)."
                }
                continue
            
            sport_block = {
                "anchors": anchors,
                "coverage_ratio": coverage_ratio,
            }
            
            # Cycling-only fields at sport block level
            if is_cycling:
                sport_block["ftp_used"] = cycling_ftp
                sport_block["w_prime_used"] = cycling_w_prime
                sport_block["ftp_staleness_days"] = ftp_staleness_days
                sport_block["model_trust_note"] = (
                    "CP/W' model (P=CP+W'/t) is primary for durations ≤20min where W' contribution "
                    "is meaningful. Coggan duration factors (Allen & Coggan, 3rd ed.) are the established "
                    "reference for ≥60min. 30min is the crossover zone where both apply. "
                    "model_divergence_pct = (actual - CP_model) / CP_model × 100. "
                    "Positive divergence at short durations may indicate strong anaerobic capacity "
                    "or stale W' value. Indoor MMP is typically 3-5% lower than outdoor (cooling, "
                    "motivation) — source flag indicates which environment produced each anchor."
                )
            
            profile[sport_family] = sport_block
            
            if self.debug:
                print(f"  📊 Sustainability {sport_family}: {observed_anchors}/{total_anchors} anchors observed")
                for label, vals in anchors.items():
                    w = vals.get("actual_watts")
                    hr = vals.get("actual_hr")
                    src = vals.get("source", "")
                    if w is not None:
                        div = vals.get("model_divergence_pct")
                        div_str = f", div={div:+.1f}%" if div is not None else ""
                        print(f"      {label}: {w}W ({src}), HR={hr}{div_str}")
        
        # If no sport blocks were added beyond the header
        has_sport_data = any(k not in ("window", "weight_kg", "weight_source", "note") for k in profile)
        if not has_sport_data:
            return _null_profile("No sport families produced valid sustainability data.")
        
        return profile

    def _calculate_tid_comparison(self, seiler_tid_7d: Dict,
                                   seiler_tid_28d: Dict) -> Dict:
        """
        Compare 7d vs 28d Seiler TID to detect distribution drift.

        Drift categories:
        - consistent: 7d and 28d classification match
        - shifting: 7d and 28d classification differ
        - acute_depolarization: 7d PI < 2.0 AND 28d PI >= 2.0

        Returns dict with classifications, PI values, delta, and drift.
        """
        cls_7d = seiler_tid_7d.get("classification")
        cls_28d = seiler_tid_28d.get("classification")
        pi_7d = seiler_tid_7d.get("polarization_index")
        pi_28d = seiler_tid_28d.get("polarization_index")

        # Null handling: if either window has no data, no comparison
        if cls_7d is None or cls_28d is None:
            return {
                "classification_7d": cls_7d,
                "classification_28d": cls_28d,
                "pi_7d": pi_7d,
                "pi_28d": pi_28d,
                "pi_delta": None,
                "drift": None,
                "note": ("Compares 7d vs 28d Seiler TID to detect "
                         "distribution shifts. Insufficient data in "
                         "one or both windows.")
            }

        # PI delta (positive = more polarized acutely)
        pi_delta = None
        if pi_7d is not None and pi_28d is not None:
            pi_delta = round(pi_7d - pi_28d, 2)

        # Drift classification
        # Check acute_depolarization first (more specific than shifting)
        if (pi_7d is not None and pi_28d is not None
                and pi_7d < 2.0 and pi_28d >= 2.0):
            drift = "acute_depolarization"
        elif cls_7d != cls_28d:
            drift = "shifting"
        else:
            drift = "consistent"

        if self.debug:
            print(f"  TID comparison: 7d={cls_7d} (PI={pi_7d}), "
                  f"28d={cls_28d} (PI={pi_28d}), drift={drift}")

        return {
            "classification_7d": cls_7d,
            "classification_28d": cls_28d,
            "pi_7d": pi_7d,
            "pi_28d": pi_28d,
            "pi_delta": pi_delta,
            "drift": drift,
            "note": ("Compares 7d vs 28d Seiler TID to detect "
                     "distribution shifts. pi_delta positive = "
                     "more polarized acutely.")
        }

    # === PHASE DETECTION v2 (dual-stream, spec-driven) ===
    
    def _detect_phase_v2(self, weekly_rows: List[Dict], planned_workouts: List[Dict],
                          race_calendar: Dict, previous_phase: Optional[str] = None,
                          today: str = None, dossier_declared: Optional[str] = None,
                          primary_sport: Optional[str] = None,
                          is_backfill: bool = False) -> Dict:
        """
        Dual-stream phase detection (v2).
        
        Stream 1: Completed history — rolling 4-week lookback from weekly_180d rows.
        Stream 2: Planned calendar — next 7-14 days of planned workouts + race calendar.
        
        Returns full phase output structure with confidence and reason_codes.
        
        Phase states: Build, Base, Peak, Taper, Deload, Recovery, Overreached, null.

        is_backfill: forwarded to _phase_stream1_features. Set True only when
        called from history regeneration (each historical week's classifier
        needs to see its own row at weekly_rows[-1]).
        """
        if today is None:
            today = datetime.now().strftime("%Y-%m-%d")
        
        reason_codes = []
        
        # Compute features from both streams
        s1 = self._phase_stream1_features(weekly_rows, is_backfill=is_backfill)
        s2 = self._phase_stream2_features(planned_workouts, race_calendar, s1, today, primary_sport, weekly_rows=weekly_rows)
        
        # Data quality assessment
        data_quality = self._phase_data_quality(weekly_rows, s1, reason_codes)
        
        # Classification
        phase, confidence, extra_reasons = self._phase_classify(
            s1, s2, previous_phase, data_quality
        )
        reason_codes.extend(extra_reasons)
        
        # Phase duration: count consecutive weeks of same phase from history.
        # Skip weekly_rows[-1] — it's the current week (being classified now,
        # phase_detected is stale or absent). Count from [-2] backward, +1 for current.
        phase_duration = 0
        if phase and weekly_rows:
            for row in reversed(weekly_rows[:-1]):
                if row.get("phase_detected") == phase:
                    phase_duration += 1
                else:
                    break
            phase_duration += 1  # current week (just classified)
        
        # Dossier agreement
        dossier_agreement = None
        if dossier_declared:
            dossier_agreement = (dossier_declared == phase) if phase else None
        
        # Stream agreement
        stream_agreement = s1.get("suggested_phase") == s2.get("suggested_phase")
        if s1.get("suggested_phase") is None or s2.get("suggested_phase") is None:
            stream_agreement = None  # can't assess if one stream has no opinion
        
        return {
            "phase": phase,
            "confidence": confidence,
            "reason_codes": reason_codes,
            "basis": {
                "stream_1": {
                    "ctl_slope": s1.get("ctl_slope"),
                    "acwr_trend": s1.get("acwr_trend"),
                    "hard_day_pattern": s1.get("hard_day_avg"),
                    "weeks_available": s1.get("weeks_available", 0)
                },
                "stream_2": {
                    "planned_tss_delta": s2.get("planned_tss_delta"),
                    "hard_sessions_planned": s2.get("hard_sessions_planned"),
                    "current_week_hard_days_completed": s2.get("current_week_hard_days_completed"),
                    "current_week_hard_days_total": s2.get("current_week_hard_days_total"),
                    "race_proximity": s2.get("race_proximity"),
                    "next_week_load": s2.get("next_week_tss_delta"),
                    "plan_coverage_current_week": s2.get("plan_coverage_current_week"),
                    "plan_coverage_next_week": s2.get("plan_coverage_next_week")
                },
                "data_quality": data_quality,
                "stream_agreement": stream_agreement
            },
            "previous_phase": previous_phase,
            "phase_duration_weeks": phase_duration,
            "dossier_declared": dossier_declared,
            "dossier_agreement": dossier_agreement
        }
    
    def _phase_stream1_features(self, weekly_rows: List[Dict],
                                is_backfill: bool = False) -> Dict:
        """
        Extract Stream 1 (retrospective) features from weekly_180d rows.
        Uses last 4 weeks for trend detection.

        is_backfill: when True, weekly_rows[-1] is the target week being
        classified retroactively (history regen); include it in the lookback so
        its own data is visible to stream1. When False (live mode),
        weekly_rows[-1] is the in-progress current week with partial mid-day
        CTL — exclude it.
        """
        result = {
            "weeks_available": len(weekly_rows),
            "ctl_slope": None,
            "ctl_values": [],
            "acwr_trend": None,
            "hard_day_avg": None,
            "hard_day_values": [],
            "monotony_trend": None,
            "tss_values": [],
            "primary_tss_values": [],
            "suggested_phase": None
        }
        
        if not weekly_rows:
            return result
        
        # Live mode: weekly_rows[-1] is the in-progress current week (partial
        # mid-day CTL); exclude it so the regression sees only finalized weeks.
        # Backfill mode: weekly_rows[-1] IS the target week being classified;
        # include it so its own data drives the classification (otherwise a
        # deload week is invisible to its own classifier).
        if is_backfill:
            finalized = weekly_rows
        else:
            finalized = weekly_rows[:-1] if len(weekly_rows) >= 2 else weekly_rows
        recent = finalized[-4:] if len(finalized) >= 4 else finalized
        
        # CTL slope: linear regression (CTL units per week) over finalized window.
        # Previous impl was a 2-point endpoint chord divided by len(values) instead
        # of (len-1), which both ignored interior points and mis-scaled the
        # denominator — producing spuriously negative slopes when a deload week
        # sat inside the lookback.
        ctl_values = [r.get("ctl_end") for r in recent if r.get("ctl_end") is not None]
        result["ctl_values"] = ctl_values
        if len(ctl_values) >= 2:
            try:
                slope, _ = statistics.linear_regression(
                    range(len(ctl_values)), ctl_values
                )
                result["ctl_slope"] = round(slope, 2)
            except (AttributeError, statistics.StatisticsError):
                # Fallback for Python <3.10: chord over (n-1) intervals
                result["ctl_slope"] = round(
                    (ctl_values[-1] - ctl_values[0]) / (len(ctl_values) - 1), 2
                )
        
        # TSS values for trend
        result["tss_values"] = [r.get("total_tss", 0) or 0 for r in recent]
        result["primary_tss_values"] = [r.get("primary_sport_tss", 0) or 0 for r in recent]
        
        # ACWR trend: direction over the window
        acwr_values = [r.get("acwr") for r in recent if r.get("acwr") is not None]
        if len(acwr_values) >= 2:
            acwr_diff = acwr_values[-1] - acwr_values[0]
            if acwr_diff > 0.1:
                result["acwr_trend"] = "rising"
            elif acwr_diff < -0.1:
                result["acwr_trend"] = "falling"
            else:
                result["acwr_trend"] = "stable"
        
        # Hard-day density
        hard_values = [r.get("hard_days", 0) or 0 for r in recent]
        result["hard_day_values"] = hard_values
        if hard_values:
            result["hard_day_avg"] = round(statistics.mean(hard_values), 1)
        
        # Monotony trend (last week vs average of prior weeks)
        mono_values = [r.get("monotony") for r in recent if r.get("monotony") is not None]
        if len(mono_values) >= 2:
            if mono_values[-1] and mono_values[-1] > 2.5:
                result["monotony_trend"] = "elevated"
            else:
                result["monotony_trend"] = "normal"
        
        # Stream 1 suggested phase (retrospective only)
        result["suggested_phase"] = self._phase_from_stream1(result, recent)
        
        return result
    
    def _phase_from_stream1(self, features: Dict, recent_rows: List[Dict]) -> Optional[str]:
        """Suggest a phase from Stream 1 features alone. Returns phase or None."""
        ctl_slope = features.get("ctl_slope")
        hard_avg = features.get("hard_day_avg")
        acwr_trend = features.get("acwr_trend")
        mono_trend = features.get("monotony_trend")
        
        # Overreached: requires convergence of multiple signals, not a single metric.
        # Path A: Current week ACWR >= 1.5 (acute spike, Gabbett danger zone)
        # Path B: Sustained elevated monotony (>2.5) + ACWR trending up or >=1.3
        if mono_trend == "elevated":
            # Use CURRENT week's ACWR, not historical max — a spike 3 weeks ago
            # that's since resolved should not keep triggering Overreached
            current_acwr = recent_rows[-1].get("acwr") if recent_rows else None
            if current_acwr is not None and current_acwr >= 1.5:
                return "Overreached"
            # Sustained pattern: elevated monotony + ACWR still above normal
            if current_acwr is not None and current_acwr >= 1.3 and acwr_trend == "rising":
                return "Overreached"
        
        if ctl_slope is None:
            return None
        
        # Build: rising CTL + sustained hard days
        if ctl_slope > 1.0 and hard_avg is not None and hard_avg >= 1.5:
            return "Build"
        
        # Base: flat CTL + moderate volume
        if -1.0 <= ctl_slope <= 1.0 and hard_avg is not None and hard_avg <= 1.5:
            return "Base"
        
        # Declining CTL — could be Deload, Taper, or Recovery (need Stream 2)
        if ctl_slope < -1.0:
            return None  # ambiguous without calendar context
        
        return None
    
    def _phase_stream2_features(self, planned_workouts: List[Dict], race_calendar: Dict,
                                 stream1: Dict, today: str,
                                 primary_sport: Optional[str] = None,
                                 weekly_rows: Optional[List[Dict]] = None) -> Dict:
        """
        Extract Stream 2 (prospective) features from planned workouts and race calendar.
        
        Windows are aligned to the training week (configurable via
        .sync_config.json, WEEK_START env var, or --week-start CLI;
        default Monday/ISO). This prevents mid-week contamination where
        a deload week's window leaks into the next build week.
        
        - Current week remainder: today → last day of training week
        - Next week: next full training week (7 days)
        
        When primary_sport is set, planned_tss_delta and next_week_tss_delta
        are filtered to primary sport only (numerator from planned workouts,
        denominator from weekly history). Falls back to all-sport when
        primary sport data is unavailable.

        weekly_rows (optional): live weekly aggregates including the in-progress
        current week at [-1]. Used to (a) compute current_week_hard_days_total
        by merging the in-progress week's completed hard_days with planned
        hard sessions remaining, and (b) derive expected_sessions for plan
        coverage from recent activity_count instead of hard-coding 5.
        """
        result = {
            "planned_tss_delta": None,
            "hard_sessions_planned": 0,
            "current_week_hard_days_completed": 0,
            "current_week_hard_days_total": 0,
            "race_proximity": None,
            "race_category": None,
            "next_week_tss_delta": None,
            "plan_coverage_current_week": 0.0,
            "plan_coverage_next_week": 0.0,
            "suggested_phase": None
        }
        
        today_date = datetime.strptime(today, "%Y-%m-%d")
        
        # Race proximity from race_calendar
        next_race = race_calendar.get("next_race")
        if next_race and next_race.get("days_until") is not None:
            result["race_proximity"] = next_race["days_until"]
            result["race_category"] = next_race.get("category")
        
        if not planned_workouts:
            return result
        
        # Week-aligned boundaries (configurable via self.week_start_day)
        # week_start_day: Mon=0..Sun=6 (Python weekday convention)
        # Week end day = day before start (e.g., Sun start → Sat end, Mon start → Sun end)
        week_end_day = (self.week_start_day - 1) % 7
        today_weekday = today_date.weekday()  # Mon=0..Sun=6
        days_to_week_end = (week_end_day - today_weekday) % 7
        current_week_end = today_date + timedelta(days=days_to_week_end)
        # Next training week: day after current_week_end → 6 days later
        next_week_start = current_week_end + timedelta(days=1)
        next_week_end = next_week_start + timedelta(days=6)
        
        # Classify planned workouts into current week remainder and next full week
        current_week_workouts = []
        next_week_workouts = []
        current_week_tss = 0
        current_week_tss_primary = 0
        
        for pw in planned_workouts:
            pw_date_str = (pw.get("date") or "")[:10]
            if not pw_date_str or pw_date_str == "unknown":
                continue
            try:
                pw_date = datetime.strptime(pw_date_str, "%Y-%m-%d")
            except ValueError:
                continue
            
            pw_tss = pw.get("planned_tss") or 0
            pw_sport = self.SPORT_FAMILIES.get(pw.get("sport_type", ""))
            is_primary = (pw_sport == primary_sport) if primary_sport else False
            
            # Current week remainder (today through end of training week)
            if today_date <= pw_date <= current_week_end:
                current_week_workouts.append(pw)
                current_week_tss += pw_tss
                if is_primary:
                    current_week_tss_primary += pw_tss
            # Next full training week
            elif next_week_start <= pw_date <= next_week_end:
                next_week_workouts.append(pw)
        
        # Plan coverage: sessions / expected sessions.
        # Derive expected_sessions from recent weekly history (activity_count
        # average over finalized weeks) instead of the legacy hard-coded 5.
        # Falls back to 5 when no history is available (e.g. first runs).
        tss_values = stream1.get("tss_values", [])
        primary_tss_values = stream1.get("primary_tss_values", [])
        weeks_avail = stream1.get("weeks_available", 0)
        expected_sessions = 5
        if weekly_rows:
            # Use finalized weeks only (exclude in-progress current week at [-1])
            finalized = weekly_rows[:-1] if len(weekly_rows) >= 2 else weekly_rows
            recent = finalized[-4:] if len(finalized) >= 4 else finalized
            counts = [r.get("activity_count") for r in recent
                      if r.get("activity_count") is not None]
            if counts:
                expected_sessions = max(1, round(statistics.mean(counts)))
        
        result["plan_coverage_current_week"] = round(
            len(current_week_workouts) / expected_sessions, 2
        ) if expected_sessions > 0 else 0.0
        result["plan_coverage_next_week"] = round(
            len(next_week_workouts) / expected_sessions, 2
        ) if expected_sessions > 0 else 0.0
        
        # Planned TSS delta: current week remainder planned / avg of prior 3 weeks actual
        # Use primary-sport values when available; fall back to all-sport
        use_primary = primary_sport and primary_tss_values and any(v > 0 for v in primary_tss_values)
        denom_values = primary_tss_values if use_primary else tss_values
        numer_current = current_week_tss_primary if use_primary else current_week_tss
        
        avg_tss_prev = None
        if denom_values and len(denom_values) >= 3:
            avg_tss_prev = statistics.mean(denom_values[-3:])
        elif denom_values:
            avg_tss_prev = statistics.mean(denom_values)
        
        # Scale: project current week remainder to full-week equivalent
        # so it's comparable to the historical weekly average.
        # days_remaining = days_to_week_end + 1 (inclusive of today)
        days_remaining = days_to_week_end + 1
        if avg_tss_prev and avg_tss_prev > 0 and numer_current > 0 and days_remaining > 0:
            projected_week_tss = numer_current * (7 / days_remaining)
            result["planned_tss_delta"] = round(projected_week_tss / avg_tss_prev, 2)
        
        # Next week TSS delta (for Deload confirmation: does load resume?)
        next_week_tss_all = sum(pw.get("planned_tss") or 0 for pw in next_week_workouts)
        if use_primary:
            next_week_tss = sum(
                (pw.get("planned_tss") or 0) for pw in next_week_workouts
                if self.SPORT_FAMILIES.get(pw.get("sport_type", "")) == primary_sport
            )
        else:
            next_week_tss = next_week_tss_all
        if avg_tss_prev and avg_tss_prev > 0 and next_week_tss > 0:
            result["next_week_tss_delta"] = round(next_week_tss / avg_tss_prev, 2)
        
        # Hard sessions planned (current week remainder only)
        # A planned workout is "hard" if its name or type suggests intensity
        hard_count = 0
        current_week_sessions = len(current_week_workouts)
        for pw in current_week_workouts:
            ws = pw.get("workout_summary") or ""
            cat = (pw.get("type") or "").upper()
            name = (pw.get("name") or "").lower()
            # Heuristic: interval markers, race categories, or intensity keywords
            if ("×" in ws or "sets" in ws.lower() or
                cat in ("RACE_A", "RACE_B", "RACE_C") or
                any(kw in name for kw in ("interval", "vo2", "threshold", "sprint", "tempo",
                                           "race", "hard", "intensity", "sweet spot"))):
                hard_count += 1
        result["hard_sessions_planned"] = hard_count
        result["next_7d_sessions"] = current_week_sessions  # renamed semantically but key preserved for compat
        
        # Merge completed (so far) + planned (remaining) hard days for the
        # current week. Without this, on the first day of a new week the
        # scorer sees only N-1 planned hard sessions even though completed
        # ones already happened — biasing Build-shaped weeks toward Base.
        # The in-progress week's hard_days count lives in weekly_rows[-1]
        # (built live from activities_28d in _calculate_derived_metrics).
        completed_hard_days = 0
        if weekly_rows:
            completed_hard_days = weekly_rows[-1].get("hard_days") or 0
        result["current_week_hard_days_completed"] = completed_hard_days
        result["current_week_hard_days_total"] = completed_hard_days + hard_count
        
        # Stream 2 suggested phase
        result["suggested_phase"] = self._phase_from_stream2(result)
        
        return result
    
    def _phase_from_stream2(self, features: Dict) -> Optional[str]:
        """Suggest a phase from Stream 2 features alone. Returns phase or None."""
        race_prox = features.get("race_proximity")
        race_cat = features.get("race_category")
        tss_delta = features.get("planned_tss_delta")
        next_week_delta = features.get("next_week_tss_delta")
        
        # Taper: race within 14 days + volume reducing
        if race_prox is not None and race_prox <= 14 and race_cat in ("RACE_A", "RACE_B"):
            if tss_delta is not None and tss_delta <= 0.80:
                return "Taper"
            # Race is close but volume not yet reducing — could be Peak
            return "Taper"  # err toward Taper when race is imminent
        
        # Peak: race within 21 days + no volume reduction yet
        if race_prox is not None and race_prox <= 21 and race_cat in ("RACE_A", "RACE_B"):
            if tss_delta is not None and tss_delta > 0.80:
                return "Peak"
        
        # Deload signal: ≥20% reduction + next week resumes
        if tss_delta is not None and tss_delta <= 0.80:
            if next_week_delta is not None and next_week_delta >= 0.85:
                return "Deload"
            # Next week unknown — Deload candidate (can't confirm)
            if features.get("plan_coverage_next_week", 0) < 0.3:
                return None  # ambiguous, can't confirm rebound
            return "Deload"
        
        return None
    
    def _phase_data_quality(self, weekly_rows: List[Dict], stream1: Dict,
                             reason_codes: List[str]) -> str:
        """Assess data quality and append reason codes. Returns 'good', 'mixed', or 'poor'."""
        quality = "good"
        weeks = stream1.get("weeks_available", 0)
        
        if weeks < 3:
            reason_codes.append("INSUFFICIENT_LOOKBACK")
            quality = "poor"
        
        # Check intensity basis breakdown across recent weeks
        if weekly_rows:
            recent = weekly_rows[-4:] if len(weekly_rows) >= 4 else weekly_rows
            hr_only_weeks = 0
            for row in recent:
                ibb = row.get("intensity_basis_breakdown")
                if ibb and ibb.get("hr", 0) > 0 and ibb.get("power", 0) == 0:
                    hr_only_weeks += 1
            if hr_only_weeks > len(recent) / 2:
                has_hr_preference = any(b == "hr" for b in self.zone_preference.values())
                if not has_hr_preference:
                    reason_codes.append("HR_ONLY_MAJORITY")
                    quality = "mixed" if quality == "good" else quality
        
        return quality
    
    def _phase_classify(self, s1: Dict, s2: Dict, previous_phase: Optional[str],
                         data_quality: str) -> Tuple[Optional[str], str, List[str]]:
        """
        Core classification logic. Combines both streams, applies scoring, 
        hysteresis, and confidence.
        
        Returns (phase, confidence, extra_reason_codes).
        """
        reasons = []
        
        s1_phase = s1.get("suggested_phase")
        s2_phase = s2.get("suggested_phase")
        race_prox = s2.get("race_proximity")
        race_cat = s2.get("race_category")
        tss_delta = s2.get("planned_tss_delta")
        next_week_delta = s2.get("next_week_tss_delta")
        ctl_slope = s1.get("ctl_slope")
        hard_avg = s1.get("hard_day_avg")
        plan_cov_curr = s2.get("plan_coverage_current_week", 0)
        plan_cov_next = s2.get("plan_coverage_next_week", 0)
        weeks = s1.get("weeks_available", 0)
        
        # planned_tss_delta is only meaningful if enough sessions are planned in the next 7 days.
        # With few planned sessions, planned TSS is a subset — delta will be misleadingly low.
        next_7d_sessions = s2.get("next_7d_sessions", 0)
        tss_delta_reliable = tss_delta is not None and next_7d_sessions >= 3
        
        # === Insufficient data guard ===
        if data_quality == "poor" and weeks < 2:
            reasons.append("INSUFFICIENT_DATA")
            return None, "low", reasons
        
        # === Priority 1: Overreached (safety) ===
        if s1_phase == "Overreached":
            return "Overreached", "high", ["SAFETY_ACWR_OR_MONOTONY"]
        
        # Secondary Overreached check — elevated monotony alone is insufficient.
        # Require actual acute overload evidence (ACWR rising AND hard-day density high).
        # "Rising" ACWR from 0.8→1.0 with 2 hard days is normal Build, not overreaching.
        
        # === Priority 2: Taper (race-anchored) ===
        if race_prox is not None and race_prox <= 14 and race_cat in ("RACE_A", "RACE_B"):
            confidence = "high"
            if tss_delta_reliable and tss_delta <= 0.80:
                reasons.append("RACE_IMMINENT_VOLUME_REDUCING")
            else:
                reasons.append("RACE_IMMINENT")
                confidence = "medium"
            return "Taper", confidence, reasons
        
        # === Priority 3: Peak (race approaching, not yet tapering) ===
        if race_prox is not None and race_prox <= 21 and race_cat in ("RACE_A", "RACE_B"):
            if not tss_delta_reliable or tss_delta > 0.80:
                ctl_values = s1.get("ctl_values", [])
                if ctl_values and len(ctl_values) >= 3:
                    current_ctl = ctl_values[-1]
                    max_ctl = max(ctl_values)
                    if current_ctl >= max_ctl * 0.95:
                        # At actual peak, CTL often flattens (slope ~0) as the athlete
                        # is at cycle high but no longer gaining. Allow marginal decline.
                        if ctl_slope is not None and ctl_slope >= -0.5:
                            return "Peak", "medium", ["RACE_APPROACHING_CTL_HIGH"]
        
        # === Priority 3.5: Recovery (early check for clearly declining/idle athletes) ===
        # Extended low load + 0 hard days + declining CTL → Recovery before Build/Base scoring
        if (ctl_slope is not None and ctl_slope < -1.0 and
                hard_avg is not None and hard_avg < 0.5 and weeks >= 3):
            confidence = "medium" if data_quality != "poor" else "low"
            reasons.append("DECLINING_LOAD_NO_HARD_DAYS")
            return "Recovery", confidence, reasons
        
        # === Priority 4: Deload→Build transition ===
        # When previous phase was Deload, expected next state is Build.
        # TSS delta is unreliable here (prior 3-week avg includes the deload week).
        # Use planned workout content instead.
        if previous_phase == "Deload":
            hard_planned = s2.get("hard_sessions_planned", 0)
            if hard_planned >= 2:
                return "Build", "medium", ["BUILD_RESUMING_AFTER_DELOAD"]
            elif hard_planned >= 1 or (plan_cov_curr > 0 and (not tss_delta_reliable or tss_delta > 0.80)):
                return "Build", "low", ["BUILD_RESUMING_AFTER_DELOAD_TENTATIVE"]
        
        # === Priority 5: Deload (calendar-driven or retrospective) ===
        # Deload = Build history + reduced/easy planned load + ≤1 hard session planned.
        # The 3-week Build history gate (weeks >= 3, rising CTL, hard_avg >= 1.5) is
        # intentional: an athlete doing their first-ever deload with <3 weeks of Build
        # data gets Recovery instead. This is the safer classification — without sufficient
        # Build evidence, we can't distinguish "planned deload" from "athlete just isn't
        # training hard". False Recovery is less harmful than false Deload.
        # Three paths:
        #  A) Reliable TSS delta ≤ 0.80 + ≤1 hard session → strong Deload signal
        #  B) Sparse plan (< 3 sessions) + ≤1 hard session + Build history → Deload candidate
        #  C) No plan at all + completed week TSS ≤ 80% of prior 3-week avg → retrospective Deload
        hard_planned = s2.get("hard_sessions_planned", 0)
        build_history = (ctl_slope is not None and ctl_slope > 0 and
                        hard_avg is not None and hard_avg >= 1.5 and
                        weeks >= 3)
        
        deload_signal = False
        deload_path = None
        
        # Allow ≤1 hard session during deload — real deload weeks often keep
        # one short quality session for neuromuscular maintenance (e.g., deload SS).
        # 2+ hard sessions = not structurally a deload.
        # When hard_planned == 1, require ≥3 planned sessions to trust the plan
        # is representative — a 2-session plan with 1 hard is too sparse to judge.
        if hard_planned == 0 or (hard_planned == 1 and next_7d_sessions >= 3):
            # Path A: reliable TSS delta showing reduction
            if tss_delta_reliable and tss_delta <= 0.80 and build_history:
                deload_signal = True
                deload_path = "A"
            # Path B: sparse plan, all easy, strong Build history
            elif (next_7d_sessions > 0 and not tss_delta_reliable and build_history
                  and ctl_slope > 1.0 and hard_avg >= 2.0):
                deload_signal = True
                deload_path = "B"
        
        # Path C: Retrospective deload — no usable plan, but completed week
        # shows clear TSS reduction vs prior 3 weeks.  Build evidence computed
        # from prior 3 weeks ONLY (excludes the current deload week which
        # would dilute hard_avg / ctl_slope in the 4-week window).
        if not deload_signal and next_7d_sessions == 0:
            tss_values = s1.get("tss_values", [])
            hard_values = s1.get("hard_day_values", [])
            if len(tss_values) >= 4 and len(hard_values) >= 4:
                current_tss = tss_values[-1]
                prior_3_avg = statistics.mean(tss_values[-4:-1])
                prior_3_hard_avg = statistics.mean(hard_values[-4:-1])
                
                # Build evidence from PRIOR 3 weeks only
                prior_build = (prior_3_hard_avg >= 1.5 and
                               prior_3_avg > 0 and
                               weeks >= 4)
                
                if prior_build:
                    actual_ratio = current_tss / prior_3_avg if prior_3_avg > 0 else 1.0
                    # ≤80% of prior volume — same threshold as Path A (≥20%
                    # reduction).  Validated against 26 weeks of history: catches
                    # confirmed deload weeks with zero false positives.
                    # Hard-day count is NOT gated here: deload weeks often keep
                    # 1-2 reduced-volume quality sessions (e.g., 2x10m SS) that
                    # still trigger the zone ladder as "hard". The TSS reduction
                    # captures the volume difference that matters.
                    if actual_ratio <= 0.80:
                        deload_signal = True
                        deload_path = "C"
        
        if deload_signal:
            if next_week_delta is not None and next_week_delta >= 0.80:
                return "Deload", "high", ["BUILD_HISTORY_REDUCED_LOAD_REBOUND_CONFIRMED"]
            elif plan_cov_next < 0.3:
                reasons.append("PLAN_GAP_NEXT_WEEK")
                conf = "medium" if deload_path == "A" else "medium"
                return "Deload", conf, reasons
            else:
                return "Deload", "medium", ["BUILD_HISTORY_REDUCED_LOAD"]
        
        # Non-Build-history reduction: Recovery (only if CTL is also declining)
        # A Base athlete with stable CTL and low planned TSS isn't recovering — they're maintaining.
        if tss_delta_reliable and tss_delta <= 0.80 and hard_planned <= 1:
            if not build_history and ctl_slope is not None and ctl_slope < -1.0:
                confidence = "medium" if data_quality != "poor" else "low"
                return "Recovery", confidence, ["NO_BUILD_HISTORY_LOW_LOAD"]
        
        # === Priority 6: Build / Base (scored) ===
        build_score = 0
        base_score = 0
        
        # CTL slope
        if ctl_slope is not None:
            if ctl_slope > 2.0:
                build_score += 3
            elif ctl_slope > 1.0:
                build_score += 2
            elif ctl_slope > 0:
                build_score += 1
            elif -1.0 <= ctl_slope <= 0:
                base_score += 2
            # ctl_slope < -1.0 already handled in Recovery early check
        
        # Hard-day density
        if hard_avg is not None:
            if hard_avg >= 2.5:
                build_score += 2
            elif hard_avg >= 1.5:
                build_score += 1
            elif hard_avg <= 1.0:
                base_score += 2
            else:
                base_score += 1
        
        # ACWR trend
        acwr_trend = s1.get("acwr_trend")
        if acwr_trend == "rising":
            build_score += 1
        elif acwr_trend == "stable":
            base_score += 1
        elif acwr_trend == "falling":
            base_score += 1
        
        # Current-week hard-day intent (Stream 2) — uses completed (so far) +
        # planned (remaining) so the score doesn't drop on Mon/Tue of a new
        # week just because most hard sessions haven't happened yet. Only
        # applied when there are enough planned sessions for the signal to
        # mean anything.
        if next_7d_sessions >= 3:
            cw_hard_total = s2.get("current_week_hard_days_total")
            # Fallback to legacy planned-only field if merged value missing
            if cw_hard_total is None:
                cw_hard_total = s2.get("hard_sessions_planned", 0)
            if cw_hard_total >= 2:
                build_score += 1
            elif cw_hard_total <= 1:
                base_score += 1
        
        # Determine winner
        margin = build_score - base_score
        
        if margin >= 2:
            phase = "Build"
        elif margin <= -2:
            phase = "Base"
        elif margin > 0:
            phase = previous_phase if previous_phase in ("Build", "Base") else "Build"
        elif margin < 0:
            phase = previous_phase if previous_phase in ("Build", "Base") else "Base"
        else:
            if previous_phase in ("Build", "Base"):
                phase = previous_phase
            else:
                phase = None
                reasons.append("BUILD_BASE_AMBIGUOUS")
        
        if phase is None:
            confidence = "low"
        elif abs(margin) >= 3 and data_quality == "good":
            confidence = "high"
        elif abs(margin) >= 2 or data_quality == "good":
            confidence = "medium"
        else:
            confidence = "low"
        
        # === Hysteresis for normal transitions ===
        if phase and previous_phase and phase != previous_phase:
            if previous_phase not in ("Overreached", None):
                reasons.append(f"PHASE_TRANSITION_{previous_phase}_TO_{phase}")
        
        # Adjust confidence for data quality
        if data_quality == "poor" and confidence == "high":
            confidence = "medium"
        elif data_quality == "poor" and confidence == "medium":
            confidence = "low"
        
        # Adjust confidence for plan coverage
        if plan_cov_curr == 0 and plan_cov_next == 0:
            if confidence == "high":
                confidence = "medium"
            reasons.append("NO_PLANNED_WORKOUTS")
        
        return phase, confidence, reasons
    
    def _determine_seasonal_context(self) -> str:
        """
        Determine seasonal context based on current month.
        Assumes Northern Hemisphere cycling calendar.
        """
        month = datetime.now().month
        
        if month in [11, 12]:
            return "Off-season / Transition"
        elif month in [1, 2]:
            return "Early Base"
        elif month in [3, 4]:
            return "Late Base / Build"
        elif month in [5, 6]:
            return "Build / Early Race Season"
        elif month in [7, 8]:
            return "Peak Race Season"
        elif month in [9, 10]:
            return "Late Season / Transition"
        else:
            return "Unknown"
    
    def _load_weekly_rows_for_phase(self) -> List[Dict]:
        """Load recent weekly_180d rows from history.json for phase detection lookback."""
        history_path = self.data_dir / self.HISTORY_FILE
        if not history_path.exists():
            return []
        try:
            with open(history_path, 'r') as f:
                history_data = json.load(f)
            rows = history_data.get("weekly_180d", [])
            # Return last 4 weeks for lookback
            return rows[-4:] if len(rows) >= 4 else rows
        except Exception:
            return []
    
    # === ALERTS SYSTEM (v3.3.0) ===
    
    def _generate_alerts(self, derived_metrics: Dict, wellness_7d: List[Dict],
                         tss_7d_total: float, tss_28d_total: float) -> List[Dict]:
        """
        Generate graduated alerts array based on Section 11 v11.4 thresholds.
        
        Severity levels: "info" → "warning" → "alarm"
        Empty array = green light.
        
        Monotony alerts use effective_monotony (primary sport when multi-sport
        detected) to avoid false positives from cross-training TSS floor inflation.
        """
        alerts = []
        
        acwr = derived_metrics.get("acwr")
        monotony = derived_metrics.get("monotony")
        effective_monotony = derived_metrics.get("effective_monotony")
        primary_sport = derived_metrics.get("primary_sport")
        primary_sport_monotony = derived_metrics.get("primary_sport_monotony")
        is_multi_sport = derived_metrics.get("multi_sport_detected", False)
        strain = derived_metrics.get("strain")
        ri = derived_metrics.get("recovery_index")
        ri_yesterday = derived_metrics.get("recovery_index_yesterday")
        latest_hrv = derived_metrics.get("latest_hrv")
        latest_rhr = derived_metrics.get("latest_rhr")
        hrv_baseline_7d = derived_metrics.get("hrv_baseline_7d")
        rhr_baseline_7d = derived_metrics.get("rhr_baseline_7d")
        
        # --- ACWR Alerts ---
        # High-side only. Low ACWR = undertraining / reduced recent load context,
        # not overload risk. Low-side is surfaced via derived_metrics.acwr_interpretation.
        if acwr is not None:
            if acwr >= 1.35:
                alerts.append({
                    "metric": "acwr",
                    "value": acwr,
                    "severity": "alarm",
                    "threshold": "1.35",
                    "context": f"ACWR {acwr} above safe range. Injury/overreach risk elevated.",
                    "persistence_days": None,
                    "tier": 2
                })
            elif acwr >= 1.3:
                alerts.append({
                    "metric": "acwr",
                    "value": acwr,
                    "severity": "warning",
                    "threshold": "1.3",
                    "context": f"ACWR {acwr} at edge of optimal range. Monitor closely. Alarm at 1.35.",
                    "persistence_days": None,
                    "tier": 2
                })
        
        # --- Monotony Alerts (with deload context + multi-sport awareness) ---
        # Use effective_monotony for alert thresholds. When multi-sport training
        # is detected and primary sport monotony is lower than total, the effective
        # value reflects the actual training load variation of the main modality.
        if effective_monotony is not None:
            deload_context = self._detect_deload_context(tss_7d_total, tss_28d_total)

            # Build context string for multi-sport cases
            multi_sport_note = ""
            if is_multi_sport and primary_sport_monotony is not None and monotony is not None and primary_sport_monotony < monotony:
                multi_sport_note = f" (total monotony {monotony} inflated by multi-sport training; {primary_sport} monotony {primary_sport_monotony} used for alerting)"

            if effective_monotony >= 2.5:
                if deload_context:
                    alerts.append({
                        "metric": "monotony",
                        "value": effective_monotony,
                        "severity": "info",
                        "threshold": 2.5,
                        "context": f"Monotony {effective_monotony} ≥ 2.5 but {deload_context}. Structural artifact, not overuse risk. Will normalize as 7-day window rolls forward.{multi_sport_note}",
                        "persistence_days": None,
                        "tier": 2
                    })
                else:
                    alerts.append({
                        "metric": "monotony",
                        "value": effective_monotony,
                        "severity": "alarm",
                        "threshold": 2.5,
                        "context": f"Monotony {effective_monotony} ≥ 2.5. Overuse risk elevated. Vary training load.{multi_sport_note}",
                        "persistence_days": None,
                        "tier": 2
                    })
            elif effective_monotony >= 2.3:
                if deload_context:
                    alerts.append({
                        "metric": "monotony",
                        "value": effective_monotony,
                        "severity": "info",
                        "threshold": 2.3,
                        "context": f"Monotony {effective_monotony} approaching threshold but {deload_context}. Expected, not actionable.{multi_sport_note}",
                        "persistence_days": None,
                        "tier": 2
                    })
                else:
                    alerts.append({
                        "metric": "monotony",
                        "value": effective_monotony,
                        "severity": "warning",
                        "threshold": 2.3,
                        "context": f"Monotony {effective_monotony} approaching overuse threshold. Alarm at 2.5.{multi_sport_note}",
                        "persistence_days": None,
                        "tier": 2
                    })
        
        # --- Strain Alerts ---
        if strain is not None and strain > 3500:
            alerts.append({
                "metric": "strain",
                "value": strain,
                "severity": "alarm",
                "threshold": 3500,
                "context": f"Strain {strain} > 3500. High cumulative stress. Consider load reduction.",
                "persistence_days": None,
                "tier": 2
            })
        
        # --- Recovery Index Alerts ---
        # Aligned with readiness_decision RI rule:
        #   alarm: ri < 0.6 (single day, immediate)
        #   warning: ri < 0.7 AND ri_yesterday < 0.7 (persistent, 2+ days)
        # Single-day dips 0.6–0.7 are context only, not warning-grade.
        if ri is not None:
            if ri < 0.6:
                alerts.append({
                    "metric": "recovery_index",
                    "value": ri,
                    "severity": "alarm",
                    "threshold": 0.6,
                    "context": f"RI {ri} < 0.6. Immediate deload required.",
                    "persistence_days": None,
                    "tier": 1
                })
            elif ri < 0.7 and ri_yesterday is not None and ri_yesterday < 0.7:
                alerts.append({
                    "metric": "recovery_index",
                    "value": ri,
                    "severity": "warning",
                    "threshold": 0.7,
                    "context": f"RI {ri} < 0.7 for 2+ consecutive days (yesterday {ri_yesterday}). Monitor — if persists 3+ days, deload review required.",
                    "persistence_days": 2,
                    "tier": 1
                })
        
        # --- HRV Alerts ---
        if latest_hrv and hrv_baseline_7d and hrv_baseline_7d > 0:
            hrv_change_pct = ((latest_hrv - hrv_baseline_7d) / hrv_baseline_7d) * 100
            if hrv_change_pct <= -20:
                # Check persistence: count consecutive days with HRV ↓>20%
                hrv_low_days = self._count_hrv_low_days(wellness_7d, hrv_baseline_7d)
                
                if hrv_low_days > 2:
                    alerts.append({
                        "metric": "hrv",
                        "value": round(latest_hrv, 1),
                        "severity": "alarm",
                        "threshold": f"↓>20% vs baseline ({round(hrv_baseline_7d, 1)})",
                        "context": f"HRV {round(latest_hrv, 1)} is {round(abs(hrv_change_pct), 1)}% below baseline, persisting {hrv_low_days} days.",
                        "persistence_days": hrv_low_days,
                        "tier": 1
                    })
                else:
                    alerts.append({
                        "metric": "hrv",
                        "value": round(latest_hrv, 1),
                        "severity": "warning",
                        "threshold": f"↓>20% vs baseline ({round(hrv_baseline_7d, 1)})",
                        "context": f"HRV {round(latest_hrv, 1)} is {round(abs(hrv_change_pct), 1)}% below baseline. Monitor — alarm if persists >2 days.",
                        "persistence_days": hrv_low_days,
                        "tier": 1
                    })
        
        # --- RHR Alerts ---
        if latest_rhr and rhr_baseline_7d and rhr_baseline_7d > 0:
            rhr_change = latest_rhr - rhr_baseline_7d
            if rhr_change >= 5:
                # Check persistence
                rhr_high_days = self._count_rhr_high_days(wellness_7d, rhr_baseline_7d)
                
                if rhr_high_days > 2:
                    alerts.append({
                        "metric": "rhr",
                        "value": round(latest_rhr, 1),
                        "severity": "alarm",
                        "threshold": f"↑≥5bpm vs baseline ({round(rhr_baseline_7d, 1)})",
                        "context": f"RHR {round(latest_rhr, 1)} is {round(rhr_change, 1)}bpm above baseline, persisting {rhr_high_days} days.",
                        "persistence_days": rhr_high_days,
                        "tier": 1
                    })
                else:
                    alerts.append({
                        "metric": "rhr",
                        "value": round(latest_rhr, 1),
                        "severity": "warning",
                        "threshold": f"↑≥5bpm vs baseline ({round(rhr_baseline_7d, 1)})",
                        "context": f"RHR {round(latest_rhr, 1)} is {round(rhr_change, 1)}bpm above baseline. Monitor — alarm if persists >2 days.",
                        "persistence_days": rhr_high_days,
                        "tier": 1
                    })
        
        # --- Durability Alerts (v3.4.0; N-gate added v3.104) ---
        # Aggregate decoupling trend from capability metrics.
        # Reliability gate: alarm requires N28>=5; declining warning requires N7>=3 AND N28>=5.
        # Below the gate, metrics are still surfaced in capability.durability but no alert fires.
        # The high_drift_count warning (>=3 sessions in 7d) is count-based and naturally
        # self-guarding — not subject to the reliability gate.
        capability = derived_metrics.get("capability", {})
        durability = capability.get("durability", {})
        dur_mean_7d = durability.get("mean_decoupling_7d")
        dur_mean_28d = durability.get("mean_decoupling_28d")
        dur_trend = durability.get("trend")
        dur_high_drift_7d = durability.get("high_drift_count_7d", 0)
        dur_n_7d = durability.get("qualifying_sessions_7d", 0)
        dur_n_28d = durability.get("qualifying_sessions_28d", 0)

        # Alarm: sustained high decoupling (28d mean > 5%, requires N28>=5)
        if (dur_mean_28d is not None and dur_mean_28d > 5.0
                and dur_n_28d >= 5):
            alerts.append({
                "metric": "durability",
                "value": dur_mean_28d,
                "severity": "alarm",
                "threshold": "28d mean > 5% (N28>=5)",
                "context": f"Sustained high decoupling ({dur_mean_28d}% 28d mean). Aerobic efficiency concern — review volume and recovery.",
                "persistence_days": None,
                "tier": 3
            })
        # Warning: declining trend with >2% delta (requires N7>=3 AND N28>=5)
        elif (dur_trend == "declining" and dur_mean_7d is not None
              and dur_mean_28d is not None
              and (dur_mean_7d - dur_mean_28d) > 2.0
              and dur_n_7d >= 3 and dur_n_28d >= 5):
            alerts.append({
                "metric": "durability",
                "value": dur_mean_7d,
                "severity": "warning",
                "threshold": "7d > 28d by > 2% (N7>=3, N28>=5)",
                "context": f"Durability declining: 7d mean decoupling {dur_mean_7d}% vs 28d {dur_mean_28d}%. Check fatigue and recovery.",
                "persistence_days": None,
                "tier": 3
            })

        # Warning: repeated poor durability (>= 3 high-drift sessions in 7d)
        # Count-based; not subject to the reliability gate.
        if dur_high_drift_7d >= 3:
            alerts.append({
                "metric": "durability",
                "value": dur_high_drift_7d,
                "severity": "warning",
                "threshold": ">= 3 sessions with >5% decoupling in 7d",
                "context": f"Repeated poor durability: {dur_high_drift_7d} sessions with >5% decoupling in last 7 days.",
                "persistence_days": None,
                "tier": 3
            })

        # --- TID Drift Alerts (v3.4.0) ---
        tid_comparison = capability.get("tid_comparison", {})
        tid_drift = tid_comparison.get("drift")

        if tid_drift == "acute_depolarization":
            pi_7d = tid_comparison.get("pi_7d")
            pi_28d = tid_comparison.get("pi_28d")
            alerts.append({
                "metric": "tid_distribution",
                "value": pi_7d,
                "severity": "warning",
                "threshold": "7d PI < 2.0, 28d PI >= 2.0",
                "context": f"Acute depolarization: 7d PI {pi_7d} vs 28d PI {pi_28d}. Grey zone or threshold work displacing polarized structure.",
                "persistence_days": None,
                "tier": 3
            })
        elif tid_drift == "shifting":
            cls_7d = tid_comparison.get("classification_7d")
            cls_28d = tid_comparison.get("classification_28d")
            alerts.append({
                "metric": "tid_distribution",
                "value": cls_7d,
                "severity": "warning",
                "threshold": "7d/28d classification mismatch",
                "context": f"TID shift: 7d {cls_7d} vs 28d {cls_28d}. Training distribution changing.",
                "persistence_days": None,
                "tier": 3
            })
        
        # Sort by tier (lower = more important), then severity
        severity_order = {"alarm": 0, "warning": 1, "info": 2}
        alerts.sort(key=lambda a: (a["tier"], severity_order.get(a["severity"], 3)))
        
        return alerts
    
    def _detect_deload_context(self, tss_7d_total: float, tss_28d_total: float) -> Optional[str]:
        """
        Detect if current period is a deload or post-deload transition.
        
        A deload is detected when trailing 7-day TSS is ≥20% below the 28-day weekly average.
        Returns context string if deload detected, None otherwise.
        """
        if not tss_28d_total or tss_28d_total == 0:
            return None
        
        weekly_avg_28d = tss_28d_total / 4  # 4 weeks
        
        if weekly_avg_28d == 0:
            return None
        
        deficit_pct = ((weekly_avg_28d - tss_7d_total) / weekly_avg_28d) * 100
        
        if deficit_pct >= 20:
            return f"deload pattern detected (7-day TSS {round(tss_7d_total)} is {round(deficit_pct)}% below 28-day weekly avg {round(weekly_avg_28d)})"
        
        return None

    @staticmethod
    def _is_valid_hrv(value: float) -> bool:
        """
        Check if HRV value is within valid physiological range (10-250ms RMSSD).
        Filters sensor errors while preserving legitimate high values in elite athletes.
        """
        return value is not None and 10 <= value <= 250

    def _count_hrv_low_days(self, wellness_7d: List[Dict], baseline: float) -> int:
        """Count consecutive days (from most recent) where HRV is ↓>20% below baseline"""
        threshold = baseline * 0.8
        count = 0
        for w in reversed(wellness_7d):
            hrv = w.get("hrv")
            if self._is_valid_hrv(hrv) and hrv < threshold:
                count += 1
            else:
                break
        return count
    
    def _count_rhr_high_days(self, wellness_7d: List[Dict], baseline: float) -> int:
        """Count consecutive days (from most recent) where RHR is ↑≥5bpm above baseline"""
        threshold = baseline + 5
        count = 0
        for w in reversed(wellness_7d):
            rhr = w.get("restingHR")
            if rhr is not None and rhr >= threshold:
                count += 1
            else:
                break
        return count
    
    # === READINESS DECISION (v3.72) ===
    
    def _get_phase_modifiers(self, phase: Optional[str], race_week_active: bool) -> Dict:
        """Return threshold modifiers based on current phase and race proximity.
        
        Returns:
            amber_threshold: int — number of amber signals before Modify triggers
            tsb_amber: float — TSB threshold for amber classification
            tighten_red: bool — whether single red = Skip (not just Modify)
            modifier_applied: str — audit label for which rule was applied
        """
        if race_week_active:
            return {"amber_threshold": 1, "tsb_amber": -15, "tighten_red": True, "modifier_applied": "race_week_tightened"}
        
        modifiers = {
            "Build":       {"amber_threshold": 3, "tsb_amber": -20, "tighten_red": False, "modifier_applied": "build_loosened"},
            "Taper":       {"amber_threshold": 1, "tsb_amber": -15, "tighten_red": True,  "modifier_applied": "taper_tightened"},
        }
        
        default = {"amber_threshold": 2, "tsb_amber": -15, "tighten_red": False, "modifier_applied": "default"}
        return modifiers.get(phase, default)
    
    def _compute_readiness_decision(self, derived_metrics: Dict, alerts: List[Dict],
                                     latest_wellness: Dict, activities: List[Dict],
                                     race_calendar: Dict, current_tsb: float = None) -> Dict:
        """
        Pre-compute deterministic readiness decision (go/modify/skip).
        
        Priority ladder (first match wins):
          P0 — Safety stop: RI < 0.6 or any tier-1 alarm → Skip
          P1 — Acute overload: ACWR >= 1.5, compound TSB+HRV, RI < 0.7 + persistent alerts → Skip/Modify
          P2 — Accumulated fatigue: signal counting with phase-adjusted thresholds → Modify
          P3 — Green light → Go
        
        Phase modifiers shift amber thresholds (Build loosens, Taper/Race week tightens).
        AI reads the decision and writes the coaching note. Can override with explanation.
        """
        # --- Gather inputs ---
        ri = derived_metrics.get("recovery_index")
        acwr = derived_metrics.get("acwr")
        tsb = current_tsb
        
        latest_hrv = derived_metrics.get("latest_hrv")
        latest_rhr = derived_metrics.get("latest_rhr")
        hrv_baseline_7d = derived_metrics.get("hrv_baseline_7d")
        rhr_baseline_7d = derived_metrics.get("rhr_baseline_7d")
        
        phase_detection = derived_metrics.get("phase_detection", {})
        current_phase = phase_detection.get("phase")
        phase_duration = phase_detection.get("phase_duration_weeks")
        
        race_week_active = race_calendar.get("race_week", {}).get("active", False)
        
        # Sleep from latest wellness
        sleep_secs = latest_wellness.get("sleepSecs")
        sleep_hours = round(sleep_secs / 3600, 2) if sleep_secs else None
        sleep_quality = latest_wellness.get("sleepQuality")
        
        # Phase modifiers
        modifiers = self._get_phase_modifiers(current_phase, race_week_active)
        
        # --- Compute signal statuses ---
        signals = {}
        
        # HRV signal
        if latest_hrv and hrv_baseline_7d and hrv_baseline_7d > 0:
            hrv_delta_pct = round(((latest_hrv - hrv_baseline_7d) / hrv_baseline_7d) * 100, 1)
            if hrv_delta_pct <= -20:
                hrv_status = "red"
            elif hrv_delta_pct <= -10:
                hrv_status = "amber"
            else:
                hrv_status = "green"
            signals["hrv"] = {"status": hrv_status, "value": round(latest_hrv, 1), "baseline_7d": round(hrv_baseline_7d, 1), "delta_pct": hrv_delta_pct}
        else:
            hrv_delta_pct = None
            signals["hrv"] = {"status": "unavailable", "value": latest_hrv, "baseline_7d": hrv_baseline_7d, "delta_pct": None}
        
        # RHR signal
        if latest_rhr and rhr_baseline_7d and rhr_baseline_7d > 0:
            rhr_delta = round(latest_rhr - rhr_baseline_7d, 1)
            if rhr_delta >= 5:
                rhr_status = "red"
            elif rhr_delta >= 3:
                rhr_status = "amber"
            else:
                rhr_status = "green"
            signals["rhr"] = {"status": rhr_status, "value": round(latest_rhr, 1), "baseline_7d": round(rhr_baseline_7d, 1), "delta_bpm": rhr_delta}
        else:
            rhr_delta = None
            signals["rhr"] = {"status": "unavailable", "value": latest_rhr, "baseline_7d": rhr_baseline_7d, "delta_bpm": None}
        
        # Sleep signal (hours only — sleep quality/score excluded from readiness; v3.90)
        if sleep_hours is not None:
            sleep_red = sleep_hours < 5
            sleep_amber = (not sleep_red) and sleep_hours < 7
            if sleep_red:
                sleep_status = "red"
            elif sleep_amber:
                sleep_status = "amber"
            else:
                sleep_status = "green"
            signals["sleep"] = {"status": sleep_status, "hours": sleep_hours, "quality": sleep_quality}
        else:
            signals["sleep"] = {"status": "unavailable", "hours": None, "quality": sleep_quality}
        
        # ACWR signal
        # Readiness: high-side only. Low ACWR = reduced recent load (taper/undertraining),
        # not a fatigue/overload signal — context surfaces via acwr_interpretation.
        if acwr is not None:
            if acwr >= 1.5:
                acwr_status = "red"
            elif acwr >= 1.3:
                acwr_status = "amber"
            else:
                acwr_status = "green"
            signals["acwr"] = {"status": acwr_status, "value": acwr}
        else:
            signals["acwr"] = {"status": "unavailable", "value": None}
        
        # RI signal — amber requires 2-day persistence to filter single-night noise.
        #   red: ri < 0.6 (single day, immediate)
        #   amber: ri < 0.7 AND ri_yesterday < 0.7 (persistent)
        #   green: otherwise (single-day dips 0.6–0.7 remain visible via value, not counted)
        ri_yesterday = derived_metrics.get("recovery_index_yesterday")
        if ri is not None:
            if ri < 0.6:
                ri_status = "red"
            elif ri < 0.7 and ri_yesterday is not None and ri_yesterday < 0.7:
                ri_status = "amber"
            else:
                ri_status = "green"
            signals["ri"] = {"status": ri_status, "value": ri, "value_yesterday": ri_yesterday}
        else:
            signals["ri"] = {"status": "unavailable", "value": None, "value_yesterday": ri_yesterday}
        
        # --- Count signals ---
        green_count = sum(1 for s in signals.values() if s["status"] == "green")
        amber_count = sum(1 for s in signals.values() if s["status"] == "amber")
        red_count = sum(1 for s in signals.values() if s["status"] == "red")
        unavailable_count = sum(1 for s in signals.values() if s["status"] == "unavailable")
        
        signal_summary = {"green": green_count, "amber": amber_count, "red": red_count, "unavailable": unavailable_count}
        
        # Collect amber/red signal names for reason strings
        amber_signals = [k for k, v in signals.items() if v["status"] == "amber"]
        red_signals = [k for k, v in signals.items() if v["status"] == "red"]
        
        # --- P0: Safety stop ---
        tier1_alarms = [a for a in alerts if a.get("severity") == "alarm" and a.get("tier") == 1]
        
        if (ri is not None and ri < 0.6) or tier1_alarms:
            alarm_refs = [a["metric"] for a in tier1_alarms]
            reasons = []
            if ri is not None and ri < 0.6:
                reasons.append(f"RI {ri} < 0.6")
            if tier1_alarms:
                reasons.append(f"tier-1 alarms: {', '.join(alarm_refs)}")
            
            return {
                "recommendation": "skip",
                "priority": 0,
                "signals": signals,
                "signal_summary": signal_summary,
                "phase_context": {
                    "phase": current_phase,
                    "phase_week": phase_duration,
                    "amber_threshold": modifiers["amber_threshold"],
                    "modifier_applied": modifiers["modifier_applied"]
                },
                "race_week_defers": False,
                "modification": None,
                "reason": f"P0 safety stop. {'; '.join(reasons)}.",
                "alarm_refs": alarm_refs
            }
        
        # --- P1: Acute overload ---
        p1_skip_reasons = []
        p1_modify_reasons = []
        
        if acwr is not None and acwr >= 1.5:
            p1_skip_reasons.append(f"ACWR {acwr} >= 1.5")
        
        # Compound: deep TSB + HRV confirming
        if tsb is not None and tsb < -30 and hrv_delta_pct is not None and hrv_delta_pct < -10:
            p1_skip_reasons.append(f"TSB {tsb} < -30 with HRV {hrv_delta_pct}% below baseline")
        
        # RI < 0.7 + persistent tier-1 alerts
        tier1_persistent = [a for a in alerts if a.get("tier") == 1 and (a.get("persistence_days") or 0) >= 2]
        if ri is not None and ri < 0.7 and tier1_persistent:
            persistent_metrics = [a["metric"] for a in tier1_persistent]
            p1_skip_reasons.append(f"RI {ri} < 0.7 with persistent alerts: {', '.join(persistent_metrics)}")
        
        if p1_skip_reasons:
            return {
                "recommendation": "skip",
                "priority": 1,
                "signals": signals,
                "signal_summary": signal_summary,
                "phase_context": {
                    "phase": current_phase,
                    "phase_week": phase_duration,
                    "amber_threshold": modifiers["amber_threshold"],
                    "modifier_applied": modifiers["modifier_applied"]
                },
                "race_week_defers": False,
                "modification": None,
                "reason": f"P1 acute overload. {'; '.join(p1_skip_reasons)}.",
                "alarm_refs": [a["metric"] for a in tier1_persistent]
            }
        
        # P1 modify tier (sub-skip thresholds)
        if acwr is not None and acwr >= 1.3:
            p1_modify_reasons.append(f"ACWR {acwr} >= 1.3")
        if tsb is not None and tsb < -25 and hrv_delta_pct is not None and hrv_delta_pct < -10:
            p1_modify_reasons.append(f"TSB {tsb} < -25 with HRV {hrv_delta_pct}% below baseline")
        
        if p1_modify_reasons:
            return {
                "recommendation": "modify",
                "priority": 1,
                "signals": signals,
                "signal_summary": signal_summary,
                "phase_context": {
                    "phase": current_phase,
                    "phase_week": phase_duration,
                    "amber_threshold": modifiers["amber_threshold"],
                    "modifier_applied": modifiers["modifier_applied"]
                },
                "race_week_defers": race_week_active,
                "modification": self._build_modification(["acwr"] if acwr and acwr >= 1.3 else amber_signals),
                "reason": f"P1 acute overload (modify). {'; '.join(p1_modify_reasons)}.",
                "alarm_refs": []
            }
        
        # --- P2: Accumulated fatigue (signal counting) ---
        # Phase-adjusted TSB signal (override default if phase shifts threshold)
        tsb_amber_threshold = modifiers["tsb_amber"]
        if tsb is not None:
            if tsb < -30:
                signals["tsb"] = {"status": "red", "value": round(tsb, 1)}
            elif tsb < tsb_amber_threshold:
                signals["tsb"] = {"status": "amber", "value": round(tsb, 1)}
            else:
                signals["tsb"] = {"status": "green", "value": round(tsb, 1)}
        else:
            signals["tsb"] = {"status": "unavailable", "value": None}
        
        # Recount after TSB added
        amber_count = sum(1 for s in signals.values() if s["status"] == "amber")
        red_count = sum(1 for s in signals.values() if s["status"] == "red")
        green_count = sum(1 for s in signals.values() if s["status"] == "green")
        unavailable_count = sum(1 for s in signals.values() if s["status"] == "unavailable")
        signal_summary = {"green": green_count, "amber": amber_count, "red": red_count, "unavailable": unavailable_count}
        amber_signals = [k for k, v in signals.items() if v["status"] == "amber"]
        red_signals = [k for k, v in signals.items() if v["status"] == "red"]
        
        # Red signal handling
        if red_count >= 2 or (red_count >= 1 and modifiers["tighten_red"]):
            triggers = red_signals + amber_signals
            return {
                "recommendation": "skip" if red_count >= 2 else "modify",
                "priority": 2,
                "signals": signals,
                "signal_summary": signal_summary,
                "phase_context": {
                    "phase": current_phase,
                    "phase_week": phase_duration,
                    "amber_threshold": modifiers["amber_threshold"],
                    "modifier_applied": modifiers["modifier_applied"]
                },
                "race_week_defers": race_week_active and red_count < 2,
                "modification": self._build_modification(triggers) if red_count < 2 else None,
                "reason": f"P2 signal count. {red_count} red ({', '.join(red_signals)}), {amber_count} amber ({', '.join(amber_signals)}).",
                "alarm_refs": []
            }
        
        if red_count >= 1:
            # Single red (not tightened phase) = modify
            triggers = red_signals + amber_signals
            return {
                "recommendation": "modify",
                "priority": 2,
                "signals": signals,
                "signal_summary": signal_summary,
                "phase_context": {
                    "phase": current_phase,
                    "phase_week": phase_duration,
                    "amber_threshold": modifiers["amber_threshold"],
                    "modifier_applied": modifiers["modifier_applied"]
                },
                "race_week_defers": race_week_active,
                "modification": self._build_modification(triggers),
                "reason": f"P2 signal count. 1 red ({', '.join(red_signals)}), {amber_count} amber ({', '.join(amber_signals)}).",
                "alarm_refs": []
            }
        
        # Amber threshold check
        if amber_count >= modifiers["amber_threshold"]:
            return {
                "recommendation": "modify",
                "priority": 2,
                "signals": signals,
                "signal_summary": signal_summary,
                "phase_context": {
                    "phase": current_phase,
                    "phase_week": phase_duration,
                    "amber_threshold": modifiers["amber_threshold"],
                    "modifier_applied": modifiers["modifier_applied"]
                },
                "race_week_defers": race_week_active,
                "modification": self._build_modification(amber_signals),
                "reason": f"P2 signal count. {amber_count} amber ({', '.join(amber_signals)}) >= threshold {modifiers['amber_threshold']}.",
                "alarm_refs": []
            }
        
        # --- P3: Green light ---
        # Check data availability
        available_count = green_count + amber_count + red_count
        reason = f"P3 green light. {green_count} green, {amber_count} amber (threshold {modifiers['amber_threshold']}), {red_count} red."
        if unavailable_count > 3:
            reason += f" Note: {unavailable_count} signals unavailable — limited data."
        
        return {
            "recommendation": "go",
            "priority": 3,
            "signals": signals,
            "signal_summary": signal_summary,
            "phase_context": {
                "phase": current_phase,
                "phase_week": phase_duration,
                "amber_threshold": modifiers["amber_threshold"],
                "modifier_applied": modifiers["modifier_applied"]
            },
            "race_week_defers": False,
            "modification": None,
            "reason": reason,
            "alarm_refs": []
        }
    
    def _build_modification(self, triggers: List[str]) -> Dict:
        """Build structured modification guidance from trigger signals.
        
        Returns adjustment directions as data — AI writes the coaching language.
        Trigger → adjustment mapping is deterministic.
        """
        if not triggers:
            return {"triggers": [], "suggested_adjustments": {"intensity": "preserve", "volume": "preserve", "cap_zone": None}}
        
        # Determine adjustment directions based on trigger pattern
        has_sleep = "sleep" in triggers
        has_hrv = "hrv" in triggers
        has_rhr = "rhr" in triggers
        has_acwr = "acwr" in triggers
        has_tsb = "tsb" in triggers
        has_ri = "ri" in triggers
        
        autonomic = has_hrv or has_rhr or has_ri
        load = has_acwr or has_tsb
        multiple = len(triggers) >= 2
        
        # ACWR-driven: cap intensity, cut volume
        if has_acwr:
            return {"triggers": triggers, "suggested_adjustments": {"intensity": "reduce", "volume": "reduce", "cap_zone": "Z2"}}
        
        # Combined (2+ triggers): reduce both
        if multiple:
            return {"triggers": triggers, "suggested_adjustments": {"intensity": "reduce", "volume": "reduce", "cap_zone": None}}
        
        # Sleep-only: reduce volume, preserve intensity
        if has_sleep and not autonomic and not load:
            return {"triggers": triggers, "suggested_adjustments": {"intensity": "preserve", "volume": "reduce", "cap_zone": None}}
        
        # Autonomic-only (HRV/RHR/RI): reduce intensity, preserve volume
        if autonomic and not has_sleep and not load:
            return {"triggers": triggers, "suggested_adjustments": {"intensity": "reduce", "volume": "preserve", "cap_zone": None}}
        
        # TSB-only: reduce volume
        if has_tsb and not autonomic and not has_sleep:
            return {"triggers": triggers, "suggested_adjustments": {"intensity": "preserve", "volume": "reduce", "cap_zone": None}}
        
        # Fallback: reduce both
        return {"triggers": triggers, "suggested_adjustments": {"intensity": "reduce", "volume": "reduce", "cap_zone": None}}
    
    # === HISTORY GENERATION (v3.3.0) ===
    
    def _get_history_confidence(self) -> Dict:
        """
        Check history.json availability and return confidence metadata.
        """
        history_path = self.data_dir / self.HISTORY_FILE
        
        if history_path.exists():
            try:
                with open(history_path, 'r') as f:
                    history_data = json.load(f)
                generated_at = history_data.get("generated_at", "")
                
                # Calculate age
                try:
                    gen_date = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
                    age_days = (datetime.now() - gen_date.replace(tzinfo=None)).days
                except:
                    age_days = None
                
                # Determine confidence from data range
                total_months = history_data.get("data_range", {}).get("total_months", 0)
                if total_months >= 12:
                    confidence = "high"
                elif total_months >= 3:
                    confidence = "medium"
                else:
                    confidence = "low"
                
                return {
                    "available": True,
                    "last_generated": generated_at[:10] if generated_at else None,
                    "age_days": age_days,
                    "total_months": total_months,
                    "history_confidence": confidence
                }
            except Exception as e:
                if self.debug:
                    print(f"  Could not read history.json: {e}")
        
        return {
            "available": False,
            "history_confidence": "low",
            "note": "No history.json available. Longitudinal analysis limited to current 28-day window."
        }
    
    def should_generate_history(self) -> bool:
        """
        Determine if history.json needs to be (re)generated.
        
        Triggers:
        - history.json missing → ALWAYS generate (bypass time gate, first-run scenario)
        - history.json >28 days old → regenerate (time-gated to Sun/Mon midnight)
        
        Refresh runs only on Sundays (6) or Mondays (0), in the first two runs
        after midnight (00:00 and 00:15 UTC).
        """
        history_path = self.data_dir / self.HISTORY_FILE
        
        # If history.json doesn't exist, ALWAYS generate (bypass time gate)
        if not history_path.exists():
            if self.debug:
                print("  history.json missing — will generate (first run)")
            return True
        
        # If sync.py changed, regenerate regardless of time gate
        try:
            with open(history_path, 'r') as f:
                history_data = json.load(f)
            if history_data.get("script_hash") != self.script_hash:
                if self.debug:
                    print("  history.json stale (sync.py changed) — will regenerate")
                return True
        except Exception:
            return True
        
        # For REFRESH of existing history, apply the time gate
        now = datetime.now()
        
        # Only on Sundays (6) or Mondays (0)
        if now.weekday() not in [0, 6]:
            return False
        
        # Only in the first two runs after midnight (00:00-00:30)
        if now.hour > 0 or (now.hour == 0 and now.minute > 30):
            return False
        
        # Check age of existing file
        try:
            with open(history_path, 'r') as f:
                history_data = json.load(f)
            generated_at = history_data.get("generated_at", "")
            gen_date = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            age_days = (datetime.now() - gen_date.replace(tzinfo=None)).days
            
            if age_days > 28:
                if self.debug:
                    print(f"  history.json is {age_days} days old — will regenerate")
                return True
            else:
                if self.debug:
                    print(f"  history.json is {age_days} days old — fresh enough")
                return False
        except Exception as e:
            if self.debug:
                print(f"  Could not parse history.json age: {e} — will regenerate")
            return True
    
    def generate_history(self) -> Dict:
        """
        Generate history.json with tiered granularity.
        
        Pulls fresh from Intervals.icu API:
        - 90-day tier: daily rows (15 fields)
        - 180-day tier: weekly aggregates (18 fields)
        - 1/2/3-year tiers: monthly aggregates (17 fields)
        - FTP timeline from API
        - Data gaps flagged factually
        """
        print("\n📊 Generating history.json...")
        
        now = datetime.now()
        
        # Determine how far back we can go (up to 3 years)
        earliest_3y = (now - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
        newest = now.strftime("%Y-%m-%d")
        
        # Fetch all activities for full range
        print("  Fetching full activity history (up to 3 years)...")
        try:
            all_activities = self._intervals_get("activities", {
                "oldest": earliest_3y, "newest": newest
            })
        except Exception as e:
            print(f"  ⚠️ Could not fetch full history: {e}")
            all_activities = []
        
        # Fetch all wellness for full range
        print("  Fetching full wellness history...")
        try:
            all_wellness = self._intervals_get("wellness", {
                "oldest": earliest_3y, "newest": newest
            })
        except Exception as e:
            print(f"  ⚠️ Could not fetch wellness history: {e}")
            all_wellness = []
        
        # Fetch athlete data for FTP history from API
        print("  Fetching athlete settings...")
        athlete = self._intervals_get("")
        # v3.109: athlete_units sourced once and threaded into every tier
        # builder so weight/distance/elevation get display blocks consistent
        # with latest.json's display semantics.
        athlete_units = self._athlete_units_from_dict(athlete)
        
        # Determine actual data range
        activity_dates = sorted([a.get("start_date_local", "")[:10] for a in all_activities if a.get("start_date_local")])
        
        if activity_dates:
            earliest_date = activity_dates[0]
            latest_date = activity_dates[-1]
        else:
            earliest_date = newest
            latest_date = newest
        
        try:
            earliest_dt = datetime.strptime(earliest_date, "%Y-%m-%d")
            total_months = max(1, int((now - earliest_dt).days / 30.44))
        except:
            total_months = 0
        
        # Build wellness lookup by date
        wellness_by_date = {}
        for w in all_wellness:
            date_str = w.get("id", "")
            if date_str:
                wellness_by_date[date_str] = w
        
        # Build activity lookup by date
        activities_by_date = defaultdict(list)
        for a in all_activities:
            date_str = a.get("start_date_local", "")[:10]
            if date_str:
                activities_by_date[date_str].append(a)
        
        # === FTP TIMELINE (from wellness sportInfo history or settings) ===
        ftp_timeline = self._build_ftp_timeline(all_wellness, athlete)
        
        # === DATA GAPS ===
        data_gaps = self._find_data_gaps(activity_dates, earliest_date, latest_date)
        
        # === 90-DAY DAILY ===
        print("  Building 90-day daily tier...")
        daily_90d = self._build_daily_tier(activities_by_date, wellness_by_date, days=90,
                                           athlete_units=athlete_units)
        
        # === 180-DAY WEEKLY ===
        print("  Building 180-day weekly tier...")
        weekly_180d = self._build_weekly_tier(activities_by_date, wellness_by_date, days=180,
                                              athlete_units=athlete_units)
        
        # === PHASE BACKFILL ===
        # Retroactively classify phase for each COMPLETED weekly row using
        # trailing 4-week window. The in-progress current week (last row) is
        # skipped — it's not finalized, only has partial data, and its phase
        # is determined live each run by _detect_phase_v2 in the main flow.
        # Stream 2 (planned calendar) is unavailable for historical weeks —
        # confidence is limited.
        empty_race_cal = {"next_race": None, "all_races": [], "taper_alert": {"active": False}, "race_week": {"active": False}}
        for i in range(len(weekly_180d) - 1):  # skip last row (in-progress)
            lookback = weekly_180d[max(0, i-3):i+1]
            prev_phase = weekly_180d[i-1].get("phase_detected") if i > 0 else None
            result = self._detect_phase_v2(
                weekly_rows=lookback,
                planned_workouts=[],
                race_calendar=empty_race_cal,
                previous_phase=prev_phase,
                today=weekly_180d[i]["week_start"],
                is_backfill=True,
            )
            weekly_180d[i]["phase_detected"] = result["phase"]
        
        # === MONTHLY TIERS ===
        monthly_tiers = {}
        for years in [1, 2, 3]:
            label = f"{years}y"
            days_back = years * 365
            if total_months >= years * 12 * 0.5:  # Only generate if enough data
                print(f"  Building {label} monthly tier...")
                monthly_tiers[f"monthly_{label}"] = self._build_monthly_tier(
                    activities_by_date, wellness_by_date, days=days_back,
                    athlete_units=athlete_units, weekly_180d=weekly_180d
                )
            else:
                monthly_tiers[f"monthly_{label}"] = []
        
        # === SUMMARIES ===
        summaries = self._build_history_summaries(daily_90d, weekly_180d, monthly_tiers)
        
        history = {
            "generated_at": now.isoformat(),
            "source": "Intervals.icu API",
            "sync_version": self.VERSION,
            "script_hash": self.script_hash,
            "data_range": {
                "earliest": earliest_date,
                "latest": latest_date,
                "total_months": total_months
            },
            "ftp_timeline": ftp_timeline,
            "data_gaps": data_gaps,
            "summaries": summaries,
            "daily_90d": daily_90d,
            "weekly_180d": weekly_180d,
            **monthly_tiers
        }
        
        # Save locally
        history_path = self.data_dir / self.HISTORY_FILE
        with open(history_path, 'w') as f:
            json.dump(history, f, indent=2, default=str)
        print(f"  ✅ history.json saved ({len(daily_90d)} daily, {len(weekly_180d)} weekly rows)")
        
        return history
    
    def _build_daily_tier(self, activities_by_date: Dict, wellness_by_date: Dict, 
                          days: int,
                          athlete_units: Optional[Dict[str, str]] = None) -> List[Dict]:
        """Build daily resolution rows for the 90-day tier.
        
        athlete_units (v3.109): when provided, each row gets a `display` block
        with weight (display.weight) alongside canonical weight_kg.
        """
        rows = []
        now = datetime.now()
        
        for i in range(days - 1, -1, -1):
            date = (now - timedelta(days=i))
            date_str = date.strftime("%Y-%m-%d")
            
            day_activities = activities_by_date.get(date_str, [])
            wellness = wellness_by_date.get(date_str, {})
            
            total_tss = sum(a.get("icu_training_load", 0) or 0 for a in day_activities)
            total_seconds = sum(a.get("moving_time", 0) or 0 for a in day_activities)
            activity_types = list(dict.fromkeys(a.get("type", "Unknown") for a in day_activities)) if day_activities else ["Rest"]
            
            # Hard day detection via shared classifier (power + HR fallback)
            day_zones_by_basis = {}
            for a in day_activities:
                sf = self.SPORT_FAMILIES.get(a.get("type", ""), None)
                zones, basis = self._get_activity_zones(a, sport_family=sf)
                if zones and basis:
                    if basis not in day_zones_by_basis:
                        day_zones_by_basis[basis] = {}
                    for zid, secs in zones.items():
                        day_zones_by_basis[basis][zid] = day_zones_by_basis[basis].get(zid, 0) + secs
            
            is_hard, intensity_basis = self._classify_hard_day(day_zones_by_basis)
            
            rows.append({
                "date": date_str,
                "total_hours": round(total_seconds / 3600, 2),
                "total_tss": round(total_tss, 0),
                "activity_count": len(day_activities),
                "activity_types": ", ".join(activity_types),
                "ctl": wellness.get("ctl"),
                "atl": wellness.get("atl"),
                "tsb": round(wellness.get("ctl", 0) - wellness.get("atl", 0), 1) if wellness.get("ctl") and wellness.get("atl") else None,
                "hrv": wellness.get("hrv"),
                "rhr": wellness.get("restingHR"),
                "sleep_hours": round(wellness.get("sleepSecs", 0) / 3600, 2) if wellness.get("sleepSecs") else None,
                "sleep_formatted": self._format_duration(int(wellness.get("sleepSecs", 0)) // 60 * 60) if wellness.get("sleepSecs") else None,
                "sleep_quality": wellness.get("sleepQuality"),
                "sleep_score": wellness.get("sleepScore"),
                "weight_kg": wellness.get("weight"),
                "display": {
                    "weight": self._to_display(wellness.get("weight"), "weight", athlete_units),
                },
                "is_hard_day": is_hard,
                "intensity_basis": intensity_basis,
                # Subjective state (categorical 1-4, see wellness_field_scales in READ_THIS_FIRST)
                "fatigue": wellness.get("fatigue"),
                "soreness": wellness.get("soreness"),
                "stress": wellness.get("stress"),
                "mood": wellness.get("mood"),
                "motivation": wellness.get("motivation"),
                "injury": wellness.get("injury"),
                "hydration": wellness.get("hydration"),
                # Vitals
                "spO2": wellness.get("spO2"),
                "blood_glucose": wellness.get("bloodGlucose"),
                "systolic": wellness.get("systolic"),
                "diastolic": wellness.get("diastolic"),
                "baevsky_si": wellness.get("baevskySI"),
                "lactate": wellness.get("lactate"),
                "respiration": wellness.get("respiration"),
                # Body composition
                "body_fat_pct": wellness.get("bodyFat"),
                "abdomen_cm": wellness.get("abdomen"),
                # Lifestyle / nutrition
                "steps": wellness.get("steps"),
                "hydration_volume_l": wellness.get("hydrationVolume"),
                "kcal_consumed": wellness.get("kcalConsumed"),
                "carbohydrates_g": wellness.get("carbohydrates"),
                "protein_g": wellness.get("protein"),
                "fat_g": wellness.get("fatTotal"),
                # Cycle
                "menstrual_phase": wellness.get("menstrualPhase"),
                "menstrual_phase_predicted": wellness.get("menstrualPhasePredicted"),
                # Platform
                "readiness": wellness.get("readiness")
            })
        
        return rows
    
    def _build_weekly_tier(self, activities_by_date: Dict, wellness_by_date: Dict,
                           days: int,
                           athlete_units: Optional[Dict[str, str]] = None) -> List[Dict]:
        """Build weekly aggregate rows for the 180-day tier.
        
        athlete_units (v3.109): when provided, each row gets a `display` block
        with weight (display.weight) alongside canonical weight_kg.
        """
        rows = []
        now = datetime.now()
        
        # Calculate weeks
        start_date = now - timedelta(days=days)
        # Align to configured week start day
        days_since_week_start = (start_date.weekday() - self.week_start_day) % 7
        start_aligned = start_date - timedelta(days=days_since_week_start)
        
        current = start_aligned
        while current < now:
            week_end = current + timedelta(days=6)
            if week_end > now:
                week_end = now
            
            week_tss = 0
            week_seconds = 0
            week_activities = 0
            week_hrv = []
            week_rhr = []
            week_sleep = []
            week_feel = []
            week_rpe = []
            week_weight = []
            hard_days = 0
            daily_tss_list = []
            intensity_basis_counts = {"power": 0, "hr": 0}
            longest_ride = 0
            z1_z2_time = 0
            z3_time = 0
            z4_plus_time = 0
            total_zone_time = 0
            ctl_end = None
            atl_end = None
            tsb_end = None
            ramp_rate = None
            sport_tss = defaultdict(float)
            
            for d in range(7):
                date = current + timedelta(days=d)
                if date > now:
                    break
                date_str = date.strftime("%Y-%m-%d")
                
                day_activities = activities_by_date.get(date_str, [])
                wellness = wellness_by_date.get(date_str, {})
                
                day_tss = sum(a.get("icu_training_load", 0) or 0 for a in day_activities)
                day_seconds = sum(a.get("moving_time", 0) or 0 for a in day_activities)
                
                week_tss += day_tss
                week_seconds += day_seconds
                week_activities += len(day_activities)
                daily_tss_list.append(day_tss)

                if self._is_valid_hrv(wellness.get("hrv")):
                    week_hrv.append(wellness["hrv"])
                if wellness.get("restingHR"):
                    week_rhr.append(wellness["restingHR"])
                if wellness.get("sleepSecs"):
                    week_sleep.append(wellness["sleepSecs"] / 3600)
                if wellness.get("weight"):
                    week_weight.append(wellness["weight"])
                
                ctl_end = wellness.get("ctl") or ctl_end
                atl_end = wellness.get("atl") or atl_end
                ramp_rate = wellness.get("rampRate") or ramp_rate
                
                # Zone distribution + hard day analysis (shared helper)
                day_zones_by_basis = {}
                for a in day_activities:
                    ride_seconds = a.get("moving_time", 0) or 0
                    if ride_seconds > longest_ride:
                        longest_ride = ride_seconds
                    
                    sf = self.SPORT_FAMILIES.get(a.get("type", ""), None)
                    a_tss = a.get("icu_training_load", 0) or 0
                    if a_tss > 0 and sf:
                        sport_tss[sf] += a_tss
                    zones, basis = self._get_activity_zones(a, sport_family=sf)
                    if zones and basis:
                        # Accumulate for hard day classification (separate by basis)
                        if basis not in day_zones_by_basis:
                            day_zones_by_basis[basis] = {}
                        for zid, secs in zones.items():
                            day_zones_by_basis[basis][zid] = day_zones_by_basis[basis].get(zid, 0) + secs
                        
                        # Accumulate for weekly zone distribution (combined)
                        for zid, secs in zones.items():
                            if zid in ("z1", "z2"):
                                z1_z2_time += secs
                            elif zid == "z3":
                                z3_time += secs
                            elif zid in ("z4", "z5", "z6", "z7"):
                                z4_plus_time += secs
                            total_zone_time += secs
                    
                    feel = a.get("feel")
                    if feel is not None:
                        week_feel.append(feel)
                    rpe = a.get("icu_rpe")
                    if rpe is not None:
                        week_rpe.append(rpe)
                
                is_hard, hard_basis = self._classify_hard_day(day_zones_by_basis)
                if is_hard:
                    hard_days += 1
                    if hard_basis in ("power", "hr"):
                        intensity_basis_counts[hard_basis] += 1
            
            if ctl_end and atl_end:
                tsb_end = round(ctl_end - atl_end, 1)
            
            # Monotony: mean(daily_tss) / stdev(daily_tss) — Foster (1998)
            # Requires 5+ days for meaningful value; partial weeks produce garbage
            # (e.g., 2 similar days → near-zero stdev → monotony 40+)
            week_monotony = None
            days_with_data = sum(1 for t in daily_tss_list if t > 0)
            if len(daily_tss_list) >= 5 and days_with_data >= 3:
                try:
                    m = statistics.mean(daily_tss_list)
                    s = statistics.stdev(daily_tss_list)
                    week_monotony = round(m / s, 2) if s > 0 else None
                except Exception:
                    week_monotony = None
            
            week_primary_sport = max(sport_tss, key=sport_tss.get) if sport_tss else None
            week_primary_sport_tss = round(sport_tss[week_primary_sport], 0) if week_primary_sport else None

            # Weekly capability rollup (v3.110) — trajectory layer for Season Report v2.
            # Mirrors gating rules from _calculate_durability / _calculate_efficiency_factor /
            # _calculate_hrrc_trend but operates on the week's activities without the trend
            # or alert layer. N>=1 is sufficient; qualifying count lets the report calibrate.
            # Durability: explicit is not None check (avoids silent drop of 0.0 values).
            _week_acts = [
                a for d in range(7)
                for a in activities_by_date.get(
                    (current + timedelta(days=d)).strftime("%Y-%m-%d"), []
                )
                if (current + timedelta(days=d)) <= now
            ]
            _CYCLING_EF_TYPES = {"Ride", "VirtualRide", "MountainBikeRide", "GravelRide"}

            # Durability (VI<=1.05, VI>0, mt>=5400, decoupling not None)
            _dur_vals = []
            for _a in _week_acts:
                _dec = _a.get("icu_hr_decoupling")
                if _dec is None:
                    _dec = _a.get("decoupling")
                _vi = _a.get("icu_variability_index")
                _mt = _a.get("moving_time", 0) or 0
                if (_dec is not None and _vi is not None
                        and _vi > 0 and _vi <= 1.05 and _mt >= 5400):
                    _dur_vals.append(_dec)
            week_durability_mean = round(statistics.mean(_dur_vals), 2) if _dur_vals else None
            week_durability_qualifying = len(_dur_vals)

            # EF (cycling only, VI<=1.05, VI>0, mt>=1200, EF not None)
            _ef_vals = []
            for _a in _week_acts:
                _ef = _a.get("icu_efficiency_factor")
                _vi = _a.get("icu_variability_index")
                _mt = _a.get("moving_time", 0) or 0
                if (_ef is not None and _a.get("type", "") in _CYCLING_EF_TYPES
                        and _vi is not None and _vi > 0 and _vi <= 1.05 and _mt >= 1200):
                    _ef_vals.append(_ef)
            week_ef_mean = round(statistics.mean(_ef_vals), 2) if _ef_vals else None
            week_ef_qualifying = len(_ef_vals)

            # HRRc (icu_hrr not None, >0)
            _hrrc_vals = []
            for _a in _week_acts:
                _hrrc = _a.get("icu_hrr")
                if isinstance(_hrrc, dict):
                    _v = _hrrc.get("value")
                    if _v is None:
                        _v = _hrrc.get("hrr")
                    _hrrc = _v
                if isinstance(_hrrc, (int, float)) and _hrrc > 0:
                    _hrrc_vals.append(float(_hrrc))
            week_hrrc_mean = round(statistics.mean(_hrrc_vals), 1) if _hrrc_vals else None
            week_hrrc_qualifying = len(_hrrc_vals)

            rows.append({
                "week_start": current.strftime("%Y-%m-%d"),
                "total_hours": round(week_seconds / 3600, 2),
                "total_tss": round(week_tss, 0),
                "primary_sport": week_primary_sport,
                "primary_sport_tss": week_primary_sport_tss,
                "sport_tss_breakdown": {k: round(v, 0) for k, v in sport_tss.items()} if sport_tss else None,
                "activity_count": week_activities,
                "ctl_end": round(ctl_end, 1) if ctl_end else None,
                "atl_end": round(atl_end, 1) if atl_end else None,
                "tsb_end": tsb_end,
                "ramp_rate": round(ramp_rate, 2) if ramp_rate else None,
                "avg_hrv": round(statistics.mean(week_hrv), 1) if week_hrv else None,
                "avg_rhr": round(statistics.mean(week_rhr), 1) if week_rhr else None,
                "avg_sleep_hours": round(statistics.mean(week_sleep), 2) if week_sleep else None,
                "z1_z2_pct": round((z1_z2_time / total_zone_time) * 100, 1) if total_zone_time > 0 else None,
                "z3_pct": round((z3_time / total_zone_time) * 100, 1) if total_zone_time > 0 else None,
                "z4_plus_pct": round((z4_plus_time / total_zone_time) * 100, 1) if total_zone_time > 0 else None,
                "hard_days": hard_days,
                "longest_ride_hours": round(longest_ride / 3600, 2),
                "avg_feel": round(statistics.mean(week_feel), 1) if week_feel else None,
                "feel_count": len(week_feel) if week_feel else 0,
                "avg_rpe": round(statistics.mean(week_rpe), 1) if week_rpe else None,
                "rpe_count": len(week_rpe) if week_rpe else 0,
                "weight_kg": round(week_weight[-1], 1) if week_weight else None,
                "display": {
                    "weight": self._to_display(
                        round(week_weight[-1], 1) if week_weight else None,
                        "weight", athlete_units
                    ),
                },
                "monotony": week_monotony,
                "intensity_basis_breakdown": intensity_basis_counts if hard_days > 0 else None,
                "acwr": None,  # computed in post-pass below
                "phase_detected": None,  # populated by _detect_phase_v2
                "durability_mean": week_durability_mean,
                "durability_qualifying": week_durability_qualifying,
                "ef_mean": week_ef_mean,
                "ef_qualifying": week_ef_qualifying,
                "hrrc_mean": week_hrrc_mean,
                "hrrc_qualifying": week_hrrc_qualifying,
            })
            
            current += timedelta(days=7)
        
        # Post-pass: compute per-week ACWR
        # ACWR = this week's avg daily TSS / prior 3 weeks' avg daily TSS
        for i, row in enumerate(rows):
            if i < 3:
                # Not enough prior weeks for chronic load
                continue
            acute = row["total_tss"] / 7 if row["total_tss"] else 0
            chronic_tss = sum(rows[j]["total_tss"] or 0 for j in range(i - 3, i))
            chronic = chronic_tss / 21 if chronic_tss else 0
            if chronic > 0:
                row["acwr"] = round(acute / chronic, 2)
        
        return rows
    
    def _build_monthly_tier(self, activities_by_date: Dict, wellness_by_date: Dict,
                            days: int,
                            athlete_units: Optional[Dict[str, str]] = None,
                            weekly_180d: Optional[List[Dict]] = None) -> List[Dict]:
        """Build monthly aggregate rows for 1/2/3-year tiers.

        athlete_units (v3.109): when provided, each row gets a `display` block
        with avg_weight (display.avg_weight) alongside canonical avg_weight_kg.
        Aggregate naming preserved — point-in-time rows expose `display.weight`.

        weekly_180d (v3.110): when provided, dominant_phase is derived via modal
        aggregation of already-computed phase_detected values from weekly rows
        whose span overlaps the month (overlap: week_start < next_month AND
        week_end >= current_month). TSS-weighted tie-break. None when no
        overlapping weekly rows exist (month outside 180d window).
        """
        rows = []
        now = datetime.now()
        start_date = now - timedelta(days=days)
        
        # Group by month
        current_month = datetime(start_date.year, start_date.month, 1)
        
        while current_month <= now:
            month_str = current_month.strftime("%Y-%m")
            
            # Determine days in this month
            if current_month.month == 12:
                next_month = datetime(current_month.year + 1, 1, 1)
            else:
                next_month = datetime(current_month.year, current_month.month + 1, 1)
            
            month_tss = 0
            month_seconds = 0
            month_activities = 0
            month_hrv = []
            month_rhr = []
            month_weight = []
            ctl_values = []
            hard_days_total = 0
            longest_ride = 0
            z1_z2_time = 0
            z3_time = 0
            z4_plus_time = 0
            total_zone_time = 0
            days_with_data = 0
            total_days_in_month = 0
            
            date = current_month
            while date < next_month and date <= now:
                date_str = date.strftime("%Y-%m-%d")
                total_days_in_month += 1
                
                day_activities = activities_by_date.get(date_str, [])
                wellness = wellness_by_date.get(date_str, {})
                
                if day_activities or wellness:
                    days_with_data += 1
                
                day_tss = sum(a.get("icu_training_load", 0) or 0 for a in day_activities)
                day_seconds = sum(a.get("moving_time", 0) or 0 for a in day_activities)
                
                month_tss += day_tss
                month_seconds += day_seconds
                month_activities += len(day_activities)


                if self._is_valid_hrv(wellness.get("hrv")):
                    month_hrv.append(wellness["hrv"])
                if wellness.get("restingHR"):
                    month_rhr.append(wellness["restingHR"])
                if wellness.get("weight"):
                    month_weight.append(wellness["weight"])
                if wellness.get("ctl"):
                    ctl_values.append(wellness["ctl"])
                
                day_zones_by_basis = {}
                for a in day_activities:
                    ride_seconds = a.get("moving_time", 0) or 0
                    if ride_seconds > longest_ride:
                        longest_ride = ride_seconds
                    
                    sf = self.SPORT_FAMILIES.get(a.get("type", ""), None)
                    zones, basis = self._get_activity_zones(a, sport_family=sf)
                    if zones and basis:
                        # Accumulate for hard day classification (separate by basis)
                        if basis not in day_zones_by_basis:
                            day_zones_by_basis[basis] = {}
                        for zid, secs in zones.items():
                            day_zones_by_basis[basis][zid] = day_zones_by_basis[basis].get(zid, 0) + secs
                        
                        # Accumulate for monthly zone distribution (combined)
                        for zid, secs in zones.items():
                            if zid in ("z1", "z2"):
                                z1_z2_time += secs
                            elif zid == "z3":
                                z3_time += secs
                            elif zid in ("z4", "z5", "z6", "z7"):
                                z4_plus_time += secs
                            total_zone_time += secs
                
                is_hard, _basis = self._classify_hard_day(day_zones_by_basis)
                if is_hard:
                    hard_days_total += 1
                
                date += timedelta(days=1)
            
            # Calculate weeks in this month for per-week averages
            weeks_in_period = max(1, total_days_in_month / 7)
            
            # Determine dominant phase via modal aggregation of weekly_180d phase_detected
            # values whose week span overlaps this month (v3.110). Overlap test:
            #   week_start < next_month AND week_end >= current_month
            # Catches boundary weeks that straddle month edges.
            # Rule: most-frequent label wins. TSS is tie-break only (not primary weight).
            # Falls back to None when no overlapping rows exist (month outside 180d window).
            dominant_phase = None
            if weekly_180d:
                phase_counts: Dict[str, int] = {}
                phase_tss_tb: Dict[str, float] = {}  # TSS tie-break accumulator
                for wrow in weekly_180d:
                    phase = wrow.get("phase_detected")
                    if not phase:
                        continue
                    try:
                        ws = datetime.strptime(wrow["week_start"], "%Y-%m-%d")
                    except (KeyError, ValueError):
                        continue
                    we = ws + timedelta(days=6)
                    if ws < next_month and we >= current_month:
                        phase_counts[phase] = phase_counts.get(phase, 0) + 1
                        phase_tss_tb[phase] = phase_tss_tb.get(phase, 0.0) + (wrow.get("total_tss") or 0.0)
                if phase_counts:
                    max_count = max(phase_counts.values())
                    candidates = [p for p, c in phase_counts.items() if c == max_count]
                    # Single winner — no tie-break needed
                    if len(candidates) == 1:
                        dominant_phase = candidates[0]
                    else:
                        # Tie: pick candidate with highest accumulated TSS
                        dominant_phase = max(candidates, key=lambda p: phase_tss_tb.get(p, 0.0))
            
            rows.append({
                "month": month_str,
                "total_hours": round(month_seconds / 3600, 2),
                "total_tss": round(month_tss, 0),
                "activity_count": month_activities,
                "ctl_peak": round(max(ctl_values), 1) if ctl_values else None,
                "ctl_low": round(min(ctl_values), 1) if ctl_values else None,
                "ctl_end": round(ctl_values[-1], 1) if ctl_values else None,
                "avg_hrv": round(statistics.mean(month_hrv), 1) if month_hrv else None,
                "avg_rhr": round(statistics.mean(month_rhr), 1) if month_rhr else None,
                "z1_z2_pct": round((z1_z2_time / total_zone_time) * 100, 1) if total_zone_time > 0 else None,
                "z3_pct": round((z3_time / total_zone_time) * 100, 1) if total_zone_time > 0 else None,
                "z4_plus_pct": round((z4_plus_time / total_zone_time) * 100, 1) if total_zone_time > 0 else None,
                "hard_days_avg_per_week": round(hard_days_total / weeks_in_period, 1),
                "longest_ride_hours": round(longest_ride / 3600, 2),
                "avg_weight_kg": round(statistics.mean(month_weight), 1) if month_weight else None,
                "display": {
                    "avg_weight": self._to_display(
                        round(statistics.mean(month_weight), 1) if month_weight else None,
                        "weight", athlete_units
                    ),
                },
                "dominant_phase": dominant_phase,
                "days_with_data": days_with_data
            })
            
            current_month = next_month
        
        return rows
    
    def _build_ftp_timeline(self, all_wellness: List[Dict], athlete: Dict) -> List[Dict]:
        """
        Build FTP timeline from ftp_history.json (actual user-set FTP values).
        Falls back to current sportSettings if no history file exists.
        """
        timeline = []
        
        # Primary source: ftp_history.json (tracked by sync.py on each run)
        ftp_history = self._load_ftp_history()
        
        for ftp_type in ["indoor", "outdoor"]:
            entries = ftp_history.get(ftp_type, {})
            for date_str, ftp_val in sorted(entries.items()):
                timeline.append({
                    "date": date_str,
                    "ftp": ftp_val,
                    "type": ftp_type,
                    "source": "FTP"
                })
        
        # Fallback: add current user-set FTP if not already in timeline
        cycling_settings = None
        if athlete.get("sportSettings"):
            for sport in athlete["sportSettings"]:
                if "Ride" in sport.get("types", []) or "VirtualRide" in sport.get("types", []):
                    cycling_settings = sport
                    break
        
        if cycling_settings:
            today = datetime.now().strftime("%Y-%m-%d")
            outdoor_ftp = cycling_settings.get("ftp")
            indoor_ftp = cycling_settings.get("indoor_ftp")
            
            # Check if current FTP is already the latest in timeline
            outdoor_dates = {e["date"]: e["ftp"] for e in timeline if e["type"] == "outdoor"}
            indoor_dates = {e["date"]: e["ftp"] for e in timeline if e["type"] == "indoor"}
            
            latest_outdoor = outdoor_dates.get(max(outdoor_dates.keys())) if outdoor_dates else None
            latest_indoor = indoor_dates.get(max(indoor_dates.keys())) if indoor_dates else None
            
            if outdoor_ftp and outdoor_ftp != latest_outdoor:
                timeline.append({"date": today, "ftp": outdoor_ftp, "type": "outdoor", "source": "user_set"})
            if indoor_ftp and indoor_ftp != latest_indoor:
                timeline.append({"date": today, "ftp": indoor_ftp, "type": "indoor", "source": "user_set"})
        
        # Sort chronologically
        timeline.sort(key=lambda x: (x["date"], x["type"]))
        
        return timeline
    
    def _find_data_gaps(self, activity_dates: List[str], earliest: str, latest: str) -> List[Dict]:
        """
        Find periods with no activity data (gaps ≥ 3 days).
        Flags factually without inference about reasons.
        """
        gaps = []
        if not activity_dates:
            return gaps
        
        date_set = set(activity_dates)
        
        try:
            start = datetime.strptime(earliest, "%Y-%m-%d")
            end = datetime.strptime(latest, "%Y-%m-%d")
        except:
            return gaps
        
        gap_start = None
        current = start
        
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            
            if date_str not in date_set:
                if gap_start is None:
                    gap_start = current
            else:
                if gap_start is not None:
                    gap_days = (current - gap_start).days
                    if gap_days >= 3:
                        gaps.append({
                            "period": f"{gap_start.strftime('%Y-%m-%d')} to {(current - timedelta(days=1)).strftime('%Y-%m-%d')}",
                            "days_missing": gap_days
                        })
                    gap_start = None
            
            current += timedelta(days=1)
        
        # Handle trailing gap
        if gap_start is not None:
            gap_days = (end - gap_start).days + 1
            if gap_days >= 3:
                gaps.append({
                    "period": f"{gap_start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}",
                    "days_missing": gap_days
                })
        
        return gaps
    
    def _build_history_summaries(self, daily_90d: List[Dict], weekly_180d: List[Dict],
                                  monthly_tiers: Dict) -> Dict:
        """Build pre-computed summaries for each tier."""
        summaries = {}
        
        # 90-day summary from daily data
        if daily_90d:
            tss_values = [d["total_tss"] for d in daily_90d if d["total_tss"]]
            hours_values = [d["total_hours"] for d in daily_90d if d["total_hours"]]
            ctl_values = [d["ctl"] for d in daily_90d if d["ctl"]]
            
            summaries["90d"] = {
                "avg_weekly_tss": round(sum(tss_values) / max(1, len(daily_90d) / 7), 0) if tss_values else None,
                "avg_weekly_hours": round(sum(hours_values) / max(1, len(daily_90d) / 7), 1) if hours_values else None,
                "ctl_start": round(ctl_values[0], 1) if ctl_values else None,
                "ctl_end": round(ctl_values[-1], 1) if ctl_values else None,
                "total_activities": sum(1 for d in daily_90d if d["activity_count"] > 0),
                "rest_days": sum(1 for d in daily_90d if d["activity_count"] == 0),
                "hard_days": sum(1 for d in daily_90d if d.get("is_hard_day"))
            }
        
        # 180-day summary from weekly data
        if weekly_180d:
            tss_values = [w["total_tss"] for w in weekly_180d if w["total_tss"]]
            hours_values = [w["total_hours"] for w in weekly_180d if w["total_hours"]]
            ctl_values = [w["ctl_end"] for w in weekly_180d if w["ctl_end"]]
            
            summaries["180d"] = {
                "avg_weekly_tss": round(statistics.mean(tss_values), 0) if tss_values else None,
                "avg_weekly_hours": round(statistics.mean(hours_values), 1) if hours_values else None,
                "ctl_start": round(ctl_values[0], 1) if ctl_values else None,
                "ctl_end": round(ctl_values[-1], 1) if ctl_values else None,
                "weeks_tracked": len(weekly_180d)
            }
        
        # Yearly summaries from monthly data
        for key in ["monthly_1y", "monthly_2y", "monthly_3y"]:
            monthly = monthly_tiers.get(key, [])
            if monthly:
                tss_values = [m["total_tss"] for m in monthly if m["total_tss"]]
                ctl_values = [m["ctl_end"] for m in monthly if m["ctl_end"]]
                
                label = key.replace("monthly_", "")
                summaries[label] = {
                    "avg_monthly_tss": round(statistics.mean(tss_values), 0) if tss_values else None,
                    "ctl_peak": round(max(ctl_values), 1) if ctl_values else None,
                    "ctl_low": round(min(ctl_values), 1) if ctl_values else None,
                    "months_tracked": len(monthly)
                }
        
        return summaries
    
    # === UPDATE NOTIFICATIONS (v3.3.0) ===
    
    def check_upstream_updates(self):
        """
        Check CrankAddict/section-11 for new releases and create a GitHub Issue.
        
        Tries manifest.json first (version-based comparison). Falls back to
        changelog.json (notification_id-based) if manifest.json is not available.
        """
        if not self.github_token or not self.github_repo:
            if self.debug:
                print("  Skipping update check — no GitHub credentials")
            return
        
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github+json"
        }
        
        # GitHub Issues use changelog.json for human-readable release notes
        # (manifest.json is for local --update only)
        self._check_updates_via_changelog(headers)
    
    def _check_updates_via_manifest(self, manifest, headers):
        """Create a GitHub Issue if manifest file hashes have changed."""
        files = manifest.get("files", {})
        
        # Generate deterministic fingerprint from sorted path:hash pairs
        hash_pairs = sorted(f"{k}:{v.get('hash', '?')}" for k, v in files.items())
        fingerprint = "|".join(hash_pairs)
        
        # Use a short hash for the issue title
        fp_hash = hashlib.md5(fingerprint.encode()).hexdigest()[:8]
        issue_title = f"Section 11 updates — {fp_hash}"
        
        # Check if issue already exists
        if self._issue_exists(issue_title, headers):
            if self.debug:
                print(f"  Update notification already exists: {issue_title}")
            return
        
        # Build issue body
        body = "## Section 11 Update Available\n\n"
        body += "### Tracked files:\n"
        for path in sorted(files.keys()):
            info = files[path]
            desc = info.get("description", "")
            desc_str = f" — {desc}" if desc else ""
            body += f"- **{path}**{desc_str}\n"
        body += f"\n### Repository:\n"
        body += f"https://github.com/{self.UPSTREAM_REPO}\n"
        body += f"\n### Update instructions:\n"
        body += f"- **Local users:** `python section11/examples/sync.py --update`\n"
        body += f"- **GitHub users:** download the latest files from the repository\n"
        body += f"\n*This issue was auto-created by sync.py v{self.VERSION}*"
        
        self._create_issue(issue_title, body, headers)
    
    def _check_updates_via_changelog(self, headers):
        """Legacy: Create a GitHub Issue from changelog.json notification_id."""
        try:
            url = f"https://raw.githubusercontent.com/{self.UPSTREAM_REPO}/main/{self.CHANGELOG_FILE}"
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                if self.debug:
                    print(f"  No changelog.json found upstream (HTTP {response.status_code})")
                return
            
            changelog = response.json()
        except Exception as e:
            if self.debug:
                print(f"  Could not fetch upstream changelog: {e}")
            return
        
        notification_id = changelog.get("notification_id")
        if not notification_id:
            if self.debug:
                print("  No notification_id in changelog")
            return
        
        issue_title = f"Section 11 updates — {notification_id}"
        
        if self._issue_exists(issue_title, headers):
            if self.debug:
                print(f"  Update notification already exists: {issue_title}")
            return
        
        # Build issue body
        changes = changelog.get("changes", [])
        body = f"## Section 11 Update Available\n\n"
        body += f"**Notification ID:** {notification_id}\n\n"
        body += "### Changes:\n"
        for change in changes:
            body += f"- {change}\n"
        body += f"\n### Repository:\n"
        body += f"https://github.com/{self.UPSTREAM_REPO}\n"
        body += f"\n*This issue was auto-created by sync.py v{self.VERSION}*"
        
        self._create_issue(issue_title, body, headers)
    
    def _issue_exists(self, title, headers):
        """Check if a GitHub Issue with this title already exists."""
        try:
            search_url = f"{self.GITHUB_API_URL}/search/issues"
            search_params = {
                "q": f'repo:{self.github_repo} "{title}" in:title'
            }
            response = requests.get(search_url, headers=headers, params=search_params, timeout=10)
            
            if response.status_code == 200:
                results = response.json()
                return results.get("total_count", 0) > 0
        except Exception as e:
            if self.debug:
                print(f"  Could not search issues: {e}")
        return False
    
    def _create_issue(self, title, body, headers):
        """Create a GitHub Issue."""
        try:
            issues_url = f"{self.GITHUB_API_URL}/repos/{self.github_repo}/issues"
            payload = {
                "title": title,
                "body": body,
                "labels": ["update-notification"]
            }
            response = requests.post(issues_url, headers=headers, json=payload, timeout=10)
            
            if response.status_code == 201:
                print(f"  📢 Update notification created: {title}")
            else:
                if self.debug:
                    print(f"  Could not create issue (HTTP {response.status_code}): {response.text}")
        except Exception as e:
            if self.debug:
                print(f"  Could not create update issue: {e}")
    
    def _format_activities(self, activities: List[Dict], interval_activity_ids: set = None,
                           temp_unit: str = "C", wind_unit: str = "MPS",
                           speed_unit: str = "KPH",
                           previous_latest_lookup: Optional[Dict[str, Dict]] = None,
                           athlete_units: Optional[Dict[str, str]] = None) -> List[Dict]:
        """Format activities for LLM analysis.
        
        Unit kwargs default to metric for backward compatibility with any caller
        not yet passing them; collect_training_data passes the athlete's actual
        account preferences (or KPH for speed since sync.py force-converts).
        
        previous_latest_lookup and athlete_units are used to populate
        terrain_summary and weather_summary fields per activity (v3.107).
        Empty dict / None defaults preserve callers that don't need these.
        """
        interval_activity_ids = interval_activity_ids or set()
        previous_latest_lookup = previous_latest_lookup or {}
        athlete_units = athlete_units or {"wind": "m/s", "temp": "c", "rain": "mm"}
        # v3.100: O(1) lookup from intervals.json entries for has_intervals/has_dfa split.
        intervals_by_id = {
            str(e.get("activity_id")): e
            for e in (self._intervals_data or {}).get("activities", [])
            if e.get("activity_id") is not None
        }
        chat_notes_cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        formatted = []
        for i, act in enumerate(activities):
            avg_power = (act.get("average_watts") or act.get("avg_watts") or 
                        act.get("average_power") or act.get("avgWatts") or
                        act.get("icu_average_watts"))
            norm_power = (act.get("weighted_average_watts") or act.get("np") or 
                         act.get("icu_pm_np") or act.get("normalizedPower") or
                         act.get("icu_weighted_avg_watts"))
            avg_hr = (act.get("average_heartrate") or act.get("avg_hr") or 
                     act.get("average_heart_rate") or act.get("avgHr") or
                     act.get("icu_average_hr"))
            max_hr = (act.get("max_heartrate") or act.get("max_hr") or 
                     act.get("max_heart_rate") or act.get("maxHr") or
                     act.get("icu_max_hr"))
            
            avg_cadence = (act.get("average_cadence") or act.get("avg_cadence") or
                          act.get("icu_average_cadence"))
            avg_temp = (act.get("average_weather_temp") or act.get("average_temp") or 
                       act.get("avg_temp") or act.get("average_temperature"))
            joules = act.get("icu_joules")
            work_kj = round(joules / 1000, 1) if joules else None
            calories = act.get("calories") or act.get("icu_calories")
            variability_index = act.get("icu_variability_index")
            decoupling = act.get("icu_hr_decoupling") or act.get("decoupling")
            
            avg_speed_ms = act.get("average_speed")
            max_speed_ms = act.get("max_speed")
            avg_speed = round(avg_speed_ms * 3.6, 1) if avg_speed_ms else None
            max_speed = round(max_speed_ms * 3.6, 1) if max_speed_ms else None
            avg_pace = act.get("average_pace") or act.get("icu_pace")
            
            weather = act.get("weather_description") or act.get("weather")
            humidity = act.get("humidity") or act.get("average_humidity")
            wind_speed = act.get("average_wind_speed") or act.get("wind_speed")
            
            carbs_used = act.get("carbs_used")
            carbs_ingested = act.get("carbs_ingested")
            
            hr_zones = {}
            power_zones = {}
            
            icu_hr_zone_times = act.get("icu_hr_zone_times", [])
            if icu_hr_zone_times and isinstance(icu_hr_zone_times, list):
                zone_labels = ["z1_time", "z2_time", "z3_time", "z4_time", "z5_time", "z6_time", "z7_time"]
                for idx, secs in enumerate(icu_hr_zone_times):
                    if idx < len(zone_labels):
                        hr_zones[zone_labels[idx]] = secs if secs is not None else 0
            
            icu_zone_times = act.get("icu_zone_times", [])
            if icu_zone_times:
                for zone in icu_zone_times:
                    zone_id = zone.get("id", "").lower()
                    secs = zone.get("secs", 0)
                    if zone_id in ["z1", "z2", "z3", "z4", "z5", "z6", "z7"]:
                        power_zones[f"{zone_id}_time"] = secs if secs is not None else 0
            
            zone_dist = {}
            if hr_zones:
                zone_dist["hr_zones"] = hr_zones
            if power_zones:
                zone_dist["power_zones"] = power_zones
            
            if not zone_dist:
                zone_dist = None
            
            activity_name = act.get("name", "")
            
            raw_hrrc = act.get("icu_hrr")
            if isinstance(raw_hrrc, dict):
                _v = raw_hrrc.get("value")
                if _v is None:
                    _v = raw_hrrc.get("hrr")
                raw_hrrc = _v
            
            distance_km = round((act.get("distance") or 0) / 1000, 2)
            elevation_m = act.get("total_elevation_gain")
            
            activity = {
                "id": act.get("id", f"unknown_{i+1}"),
                "date": act.get("start_date_local", "unknown"),
                "type": act.get("type", "Unknown"),
                "name": activity_name,
                "duration_hours": round((act.get("moving_time") or 0) / 3600, 2),
                "distance_km": distance_km,
                "tss": act.get("icu_training_load"),
                "intensity_factor": act.get("icu_intensity"),
                "avg_power": avg_power,
                "normalized_power": norm_power,
                "avg_hr": avg_hr,
                "max_hr": max_hr,
                "avg_cadence": avg_cadence,
                "avg_speed": avg_speed,
                "avg_speed_unit": speed_unit,
                "max_speed": max_speed,
                "max_speed_unit": speed_unit,
                "avg_pace": avg_pace,
                "avg_temp": avg_temp,
                "avg_temp_unit": temp_unit,
                "weather": weather,
                "humidity": humidity,
                "wind_speed": wind_speed,
                "wind_speed_unit": wind_unit,
                "work_kj": work_kj,
                "calories": calories,
                "carbs_used": carbs_used,
                "carbs_ingested": carbs_ingested,
                "variability_index": variability_index,
                "decoupling": decoupling,
                "efficiency_factor": act.get("icu_efficiency_factor"),
                "hrrc": raw_hrrc,
                "elevation_m": elevation_m,
                "display": {
                    # v3.109: display-ready values converted from canonical metric.
                    # AI quotes these for narration; canonical fields above remain
                    # the calculation source. avg_speed/max_speed are km/h on input
                    # (sync.py force-converts m/s → km/h) — display.speed converts
                    # to mph for imperial athletes, resolving the avg_speed_unit
                    # always-KPH asymmetry preserved on the sibling fields above.
                    "distance":   self._to_display(distance_km, "distance", athlete_units),
                    "elevation":  self._to_display(elevation_m, "elevation", athlete_units),
                    "avg_speed":  self._to_display(avg_speed, "speed", athlete_units),
                    "max_speed":  self._to_display(max_speed, "speed", athlete_units),
                },
                "feel": act.get("feel"),
                "rpe": act.get("icu_rpe"),
                "effort_response": self._classify_effort_response(
                    act.get("icu_intensity"), act.get("icu_rpe")
                ),
                "zone_distribution": zone_dist,
                "has_intervals": False,
                "has_dfa": False,
            }

            # has_intervals: requires at least one WORK segment. Intervals.icu emits a
            # whole-session RECOVERY placeholder on unstructured endurance rides, so a
            # non-empty intervals list alone is not sufficient.
            # has_dfa flags AlphaHRV sessions; dfa_summary attached only when sufficient.
            _entry = intervals_by_id.get(str(act.get("id")))
            if _entry:
                if any(i.get("type") == "WORK" for i in (_entry.get("intervals") or [])):
                    activity["has_intervals"] = True
                _dfa = _entry.get("dfa")
                if _dfa:
                    activity["has_dfa"] = True
                    if _dfa.get("quality", {}).get("sufficient"):
                        activity["dfa_summary"] = self._build_dfa_summary(_dfa)

            # Terrain summary (v3.107) — fetched on first encounter, copied
            # forward thereafter via previous_latest_lookup. Indoor activities
            # produce no terrain field at all (activity.type is the indoor signal).
            terrain_fields = self._build_terrain_for_activity(act, previous_latest_lookup, athlete_units)
            for k, v in terrain_fields.items():
                activity[k] = v
            
            # Weather summary (v3.107) — built from existing activity-list fields
            # when has_weather=True. weather_status="unavailable" otherwise (and
            # NOT copied forward — re-evaluated each sync since Intervals may
            # compute weather later).
            weather_fields = self._build_weather_for_activity(act, previous_latest_lookup, athlete_units)
            for k, v in weather_fields.items():
                activity[k] = v

            # Pass through full description + extract NOTE: lines for push.py round-trip (v3.84)
            raw_desc = act.get("description") or ""
            if raw_desc.strip():
                activity["description"] = raw_desc.strip()
                coach_notes = []
                for line in raw_desc.split("\n"):
                    stripped = line.strip()
                    if stripped.upper().startswith("NOTE:"):
                        note_text = stripped[5:].strip()
                        if note_text:
                            coach_notes.append(note_text)
                    elif stripped:
                        break  # NOTE: lines only extracted from top of description
                if coach_notes:
                    activity["coach_notes"] = coach_notes

            # Fetch activity chat messages for recent activities (v3.84 — unconditional, 7-day window)
            act_date = act.get("start_date_local", "")[:10]
            if act_date >= chat_notes_cutoff:
                activity_id = act.get("id")
                if activity_id:
                    notes = self._get_activity_messages(activity_id)
                    if notes:
                        activity["chat_notes"] = notes
            
            formatted.append(activity)
        
        return formatted
    
    def _format_wellness(self, wellness: List[Dict],
                         athlete_units: Optional[Dict[str, str]] = None) -> List[Dict]:
        """Format wellness data.
        
        athlete_units (v3.109): when provided, each row gets a `display` block
        with weight (display.weight) alongside canonical weight_kg.
        """
        formatted = []
        for w in wellness:
            weight_kg = w.get("weight")
            entry = {
                "date": w.get("id", "unknown"),
                # Core metrics
                "weight_kg": weight_kg,
                "display": {
                    "weight": self._to_display(weight_kg, "weight", athlete_units),
                },
                "resting_hr": w.get("restingHR"),
                "hrv_rmssd": w.get("hrv"),
                "hrv_sdnn": w.get("hrvSDNN"),
                "sleep_hours": round(w["sleepSecs"] / 3600, 2) if w.get("sleepSecs") else None,
                "sleep_formatted": self._format_duration(int(w["sleepSecs"]) // 60 * 60) if w.get("sleepSecs") else None,
                "sleep_quality": w.get("sleepQuality"),
                "sleep_score": w.get("sleepScore"),
                "mental_energy": w.get("mentalEnergy"),
                "avg_sleeping_hr": w.get("avgSleepingHR"),
                "vo2max": w.get("vo2max"),
                # Subjective state (categorical 1-4, see wellness_field_scales in READ_THIS_FIRST)
                "fatigue": w.get("fatigue"),
                "soreness": w.get("soreness"),
                "stress": w.get("stress"),
                "mood": w.get("mood"),
                "motivation": w.get("motivation"),
                "injury": w.get("injury"),
                "hydration": w.get("hydration"),
                # Vitals
                "spO2": w.get("spO2"),
                "blood_glucose": w.get("bloodGlucose"),
                "systolic": w.get("systolic"),
                "diastolic": w.get("diastolic"),
                "baevsky_si": w.get("baevskySI"),
                "lactate": w.get("lactate"),
                "respiration": w.get("respiration"),
                # Body composition
                "body_fat_pct": w.get("bodyFat"),
                "abdomen_cm": w.get("abdomen"),
                # Lifestyle / nutrition
                "steps": w.get("steps"),
                "hydration_volume_l": w.get("hydrationVolume"),
                "kcal_consumed": w.get("kcalConsumed"),
                "carbohydrates_g": w.get("carbohydrates"),
                "protein_g": w.get("protein"),
                "fat_g": w.get("fatTotal"),
                # Cycle
                "menstrual_phase": w.get("menstrualPhase"),
                "menstrual_phase_predicted": w.get("menstrualPhasePredicted"),
                # Platform
                "readiness": w.get("readiness")
            }
            
            formatted.append(entry)
        
        return formatted
    
    def _summarize_workout_doc(self, workout_doc: Dict) -> str:
        """
        Summarize a structured workout_doc into a human-readable one-liner.
        
        Uses two deterministic patterns:
          Pattern A: Explicit repeats (step has 'reps' + nested 'steps')
          Pattern B: Flat alternating work/rest pairs (min 3 reps, strict guards)
        
        Returns summary string or None if workout doesn't match either pattern
        or if workout_doc is missing/malformed. Never raises exceptions.
        
        Note: workout_doc availability depends on how the workout was created in
        Intervals.icu. Workouts created via the builder will have it; imported or
        manually typed workouts may not. When absent, raw description is preserved.
        """
        try:
            if not workout_doc or not isinstance(workout_doc, dict):
                return None
            steps = workout_doc.get("steps")
            if not steps or not isinstance(steps, list):
                return None
            
            parts = []
            for step in steps:
                rendered = self._render_step(step)
                if rendered:
                    parts.append(rendered)
            
            if not parts:
                return None
            
            # Check if any part is an interval summary (the whole point of this)
            has_interval = any(
                "×" in p or "sets" in p.lower() 
                for p in parts
            )
            if not has_interval:
                return None  # All flat steps — no wall-of-text problem, skip summary
            
            return self._merge_interval_blocks(parts)
        except Exception:
            return None
    
    def _merge_interval_blocks(self, parts: List[str]) -> str:
        """
        Merge consecutive identical interval blocks in summary parts.
        
        E.g., ["5×10s @700W / 3m rec", "5×10s @700W / 3m rec"] → ["2 × 5×10s @700W / 3m rec"]
        
        No WU/CD labeling — that's a coaching interpretation, not structural data.
        Strict string equality only.
        """
        if not parts:
            return ""
        
        result = []
        i = 0
        while i < len(parts):
            current = parts[i]
            count = 1
            while i + count < len(parts) and parts[i + count] == current:
                count += 1
            if count > 1:
                result.append(f"{count} × {current}")
            else:
                result.append(current)
            i += count
        
        return " | ".join(result)
    
    def _render_step(self, step: Dict) -> str:
        """Render a single workout_doc step. Returns string or None."""
        try:
            if not isinstance(step, dict):
                return None
            
            # Pattern A: Explicit repeats
            if "reps" in step and "steps" in step and isinstance(step["steps"], list):
                return self._render_repeat_block(step)
            
            # Pattern B: Check later at block level (handled in _summarize_workout_doc 
            # by scanning sequences). Individual flat steps just render simply.
            return self._render_flat_step(step)
        except Exception:
            return None
    
    def _render_flat_step(self, step: Dict) -> str:
        """Render a non-repeat step as 'duration @power'."""
        try:
            dur = step.get("duration")
            if not dur or not isinstance(dur, (int, float)):
                return None
            
            dur_str = self._format_duration(int(dur))
            
            # Get power target
            power = step.get("_power") or step.get("power")
            if power and isinstance(power, dict):
                val = power.get("value")
                if val is not None:
                    return f"{dur_str} @{int(round(val))}W"
            
            # HR target
            hr = step.get("_hr") or step.get("hr")
            if hr and isinstance(hr, dict):
                val = hr.get("value")
                if val is not None:
                    return f"{dur_str} @{int(round(val))}bpm"
            
            # Duration only (freeride, etc)
            return f"{dur_str}"
        except Exception:
            return None
    
    def _render_repeat_block(self, step: Dict) -> str:
        """
        Render a repeat block (Pattern A).
        
        Handles:
        - Simple: reps × (work + rest) → "N×dur @power / rest rec"
        - With set recovery: first nested step is low-power rest, then alternating pairs
        
        Bails to None if nested structure has >3 unique step types or is too complex.
        """
        try:
            reps = step.get("reps", 1)
            nested = step.get("steps", [])
            if not nested or not isinstance(nested, list):
                return None
            
            # Simple case: 2 nested steps (work + rest)
            if len(nested) == 2:
                work, rest = nested[0], nested[1]
                work_str = self._describe_work_step(work)
                rest_str = self._describe_rest_duration(rest)
                if work_str and rest_str:
                    return f"{reps}×{work_str} / {rest_str} rec"
                elif work_str:
                    return f"{reps}×{work_str}"
                return None
            
            # Check for alternating work/rest pattern inside nested steps
            # (e.g., 30/15 sessions: set_recovery, then work, rest, work, rest...)
            if len(nested) >= 3:
                result = self._detect_alternating_in_nested(nested, reps)
                if result:
                    return result
            
            # Too complex — bail
            return None
        except Exception:
            return None
    
    def _detect_alternating_in_nested(self, nested: List[Dict], outer_reps: int) -> str:
        """
        Detect alternating work/rest pairs inside a nested step list.
        Used for 30/15-style sessions where the builder unrolls reps inside a set.
        
        Guards:
        - Both work and rest must have numeric power targets
        - All work targets within ±2W, all rest targets within ±2W
        - All work durations equal, all rest durations equal (one tail exception allowed)
        - Minimum 3 pairs
        """
        try:
            # Check if first step is a set recovery (low power, before the main work)
            set_rec = None
            start_idx = 0
            if len(nested) >= 5:  # need at least set_rec + 2 pairs
                first = nested[0]
                second = nested[1]
                first_power = self._get_power(first)
                second_power = self._get_power(second)
                first_dur = first.get("duration", 0)
                second_dur = second.get("duration", 0)
                # Set recovery: longer duration, lower or equal power than work steps
                if (first_power is not None and second_power is not None 
                    and first_power <= second_power and first_dur > second_dur):
                    set_rec = first
                    start_idx = 1
            
            # Collect remaining steps as candidate pairs
            remaining = nested[start_idx:]
            if len(remaining) < 6:  # need at least 3 pairs
                return None
            
            # Try to consume as (work, rest) pairs
            pairs = []
            i = 0
            while i + 1 < len(remaining):
                work = remaining[i]
                rest = remaining[i + 1]
                w_power = self._get_power(work)
                r_power = self._get_power(rest)
                w_dur = work.get("duration")
                r_dur = rest.get("duration")
                
                if w_power is None or r_power is None or w_dur is None or r_dur is None:
                    return None  # Can't compare — bail
                w_power = int(round(w_power))
                r_power = int(round(r_power))
                if w_power <= r_power:
                    return None  # Work should be harder than rest
                if abs(w_power - r_power) < max(10, 0.05 * w_power):
                    return None  # Targets must be meaningfully distinct
                
                pairs.append((w_dur, w_power, r_dur, r_power))
                i += 2
            
            # Trailing solo work step: final rep with no rest (builder drops
            # the last rest when it's followed by set recovery or cooldown).
            has_trailing = False
            if i == len(remaining) - 1:
                trailing = remaining[i]
                t_power = self._get_power(trailing)
                t_dur = trailing.get("duration")
                if (t_power is not None and t_dur is not None and pairs):
                    ref_wd = pairs[0][0]
                    ref_wp = pairs[0][1]
                    if (t_dur == ref_wd and
                            abs(int(round(t_power)) - ref_wp) <= 2):
                        has_trailing = True
            
            if len(pairs) + (1 if has_trailing else 0) < 3:
                return None
            
            # Consistency check (pairs only — trailing rep already validated above)
            ref_w_dur, ref_w_power, ref_r_dur, ref_r_power = pairs[0]
            for j, (wd, wp, rd, rp) in enumerate(pairs):
                if wd != ref_w_dur:
                    return None  # Work durations must match exactly
                if abs(wp - ref_w_power) > 2:
                    return None  # Work power within ±2W
                if abs(rp - ref_r_power) > 2:
                    return None  # Rest power within ±2W
                # Rest duration: allow last pair to differ (tail exception)
                if rd != ref_r_dur and j < len(pairs) - 1:
                    return None
            
            # Build summary
            n_reps = len(pairs) + (1 if has_trailing else 0)
            work_dur_str = self._format_duration(ref_w_dur)
            work_power = int(round(ref_w_power))
            rest_dur_str = self._format_duration(ref_r_dur)
            
            inner = f"{n_reps}×{work_dur_str} @{work_power}W / {rest_dur_str} rec"
            
            if outer_reps > 1:
                if set_rec:
                    sr_dur = self._format_duration(set_rec.get("duration", 0))
                    return f"{outer_reps} sets × {inner} ({sr_dur} set rec)"
                return f"{outer_reps} sets × {inner}"
            
            if set_rec:
                sr_dur = self._format_duration(set_rec.get("duration", 0))
                return f"{inner} ({sr_dur} set rec)"
            return inner
        except Exception:
            return None
    
    def _get_power(self, step: Dict) -> float:
        """Extract resolved power value from a step. Returns float or None."""
        try:
            power = step.get("_power") or step.get("power")
            if power and isinstance(power, dict):
                val = power.get("value")
                if val is not None:
                    return float(val)
            return None
        except Exception:
            return None
    
    def _describe_work_step(self, step: Dict) -> str:
        """Describe a work step as 'dur @power'."""
        try:
            dur = step.get("duration")
            if not dur:
                return None
            dur_str = self._format_duration(int(dur))
            
            power = self._get_power(step)
            if power is not None:
                return f"{dur_str} @{int(round(power))}W"
            
            hr = step.get("_hr") or step.get("hr")
            if hr and isinstance(hr, dict):
                val = hr.get("value")
                if val is not None:
                    return f"{dur_str} @{int(round(val))}bpm"
            
            return dur_str
        except Exception:
            return None
    
    def _describe_rest_duration(self, step: Dict) -> str:
        """Describe a rest step duration."""
        try:
            dur = step.get("duration")
            if not dur:
                return None
            return self._format_duration(int(dur))
        except Exception:
            return None
    
    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Format seconds into human-readable duration (e.g., 300 → '5m', 90 → '1m30s')."""
        if seconds <= 0:
            return "0s"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        parts = []
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if secs:
            parts.append(f"{secs}s")
        return "".join(parts) if parts else "0s"
    
    def _detect_flat_alternating(self, workout_doc: Dict) -> str:
        """
        Pattern B: Detect flat alternating work/rest pairs in top-level steps.
        
        For workouts like sprint openers where intervals are unrolled without
        repeat markers. Scans top-level steps for blocks of alternating high/low
        power pairs separated by non-matching steps (warmup, cooldown, etc).
        
        Guards:
        - Both work and rest must have numeric power targets (via _power or power)
        - All work targets within ±2W, all rest targets within ±2W
        - All work durations equal, all rest durations equal (one tail exception)
        - Minimum 3 pairs per block
        - Work power must be higher than rest power
        """
        try:
            steps = workout_doc.get("steps")
            if not steps or not isinstance(steps, list) or len(steps) < 6:
                return None
            
            # Skip steps that are repeat blocks (already handled by Pattern A)
            if any(s.get("reps") for s in steps if isinstance(s, dict)):
                return None
            
            # Collect (duration, power) for each step
            step_data = []
            for s in steps:
                if not isinstance(s, dict):
                    return None
                dur = s.get("duration")
                power = self._get_power(s)
                step_data.append((dur, power))
            
            # Try to find alternating blocks
            # Strategy: scan for regions where pairs repeat
            parts = []
            i = 0
            while i < len(step_data):
                dur_i, pow_i = step_data[i]
                
                # Try to start an alternating block at position i
                if (i + 1 < len(step_data) 
                    and dur_i is not None and pow_i is not None
                    and step_data[i+1][0] is not None and step_data[i+1][1] is not None):
                    
                    block = self._try_alternating_block(step_data, i)
                    if block:
                        count, work_dur, work_power, rest_dur = block
                        wd_str = self._format_duration(work_dur)
                        rd_str = self._format_duration(rest_dur)
                        parts.append(f"{count}×{wd_str} @{int(round(work_power))}W / {rd_str} rec")
                        i += count * 2
                        continue
                
                # Not part of an alternating block — render as flat step
                if dur_i is not None:
                    flat = self._render_flat_step(steps[i])
                    if flat:
                        parts.append(flat)
                i += 1
            
            if not parts:
                return None
            
            # Only return if we found at least one alternating block
            has_block = any("×" in p for p in parts)
            if not has_block:
                return None
            
            return self._merge_interval_blocks(parts)
        except Exception:
            return None
    
    def _try_alternating_block(self, step_data: List, start: int) -> tuple:
        """
        Try to consume an alternating work/rest block starting at 'start'.
        Returns (count, work_dur, work_power, rest_dur) or None.
        """
        try:
            ref_w_dur, ref_w_power = step_data[start]
            ref_r_dur, ref_r_power = step_data[start + 1]
            
            if ref_w_power is None or ref_r_power is None:
                return None
            # Normalize watts to ints before all comparisons
            ref_w_power = int(round(ref_w_power))
            ref_r_power = int(round(ref_r_power))
            if ref_w_power <= ref_r_power:
                return None  # Work must be harder than rest
            if abs(ref_w_power - ref_r_power) < max(10, 0.05 * ref_w_power):
                return None  # Targets must be meaningfully distinct
            if ref_w_dur is None or ref_r_dur is None:
                return None
            
            count = 1
            j = start + 2
            while j + 1 < len(step_data):
                wd, wp = step_data[j]
                rd, rp = step_data[j + 1]
                
                if wp is None or rp is None or wd is None or rd is None:
                    break
                wp = int(round(wp))
                rp = int(round(rp))
                if abs(wd - ref_w_dur) > 1:
                    break  # Work duration tolerance ±1s
                if abs(wp - ref_w_power) > 2:
                    break
                if abs(rp - ref_r_power) > 2:
                    break
                # Rest duration: allow tail exception on last pair
                if abs(rd - ref_r_dur) > 2:
                    # Long rest (≥1.5× normal) = set break — always consume as tail
                    if rd >= ref_r_dur * 1.5:
                        count += 1
                        j += 2
                        break
                    # Otherwise check if more matching pairs follow
                    if j + 3 < len(step_data):
                        nwd, nwp = step_data[j + 2]
                        if (nwd is not None and abs(nwd - ref_w_dur) <= 1 
                            and nwp is not None and abs(int(round(nwp)) - ref_w_power) <= 2):
                            break  # Not the last pair — strict fail
                    count += 1
                    j += 2
                    break  # Tail exception consumed, stop
                
                count += 1
                j += 2
            
            # Trailing solo work step: final rep with no paired rest
            if j < len(step_data):
                wd, wp = step_data[j]
                if (wd is not None and wp is not None
                        and abs(wd - ref_w_dur) <= 1
                        and abs(int(round(wp)) - ref_w_power) <= 2):
                    count += 1
            
            if count < 3:
                return None
            
            return (count, ref_w_dur, ref_w_power, ref_r_dur)
        except Exception:
            return None
    
    def _format_events(self, events: List[Dict], today: str = None) -> List[Dict]:
        """
        Format planned workouts with workout_summary and tiered detail (v3.6.2).
        
        Tiering:
        - Days 0-7: full output (description + workout_summary + all fields)
        - Days 8-42: skeleton (name, date, type, TSS, duration, workout_summary).
          If workout_summary is null, keeps description_preview (first 3 lines).
        
        Sets self._summary_stats with coverage telemetry.
        """
        if today is None:
            today = datetime.now().strftime("%Y-%m-%d")
        
        day7_cutoff = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
        
        stats = {"attempted": 0, "success": 0, "patternA": 0, "patternB": 0,
                 "bail_no_workout_doc": 0, "bail_no_match": 0}
        
        result = []
        for i, evt in enumerate(events):
            evt_date = (evt.get("start_date_local") or "unknown")[:10]
            is_near = evt_date <= day7_cutoff
            
            # Generate workout_summary from workout_doc
            workout_doc = evt.get("workout_doc")
            summary = None
            
            if workout_doc and isinstance(workout_doc, dict) and workout_doc.get("steps"):
                stats["attempted"] += 1
                summary = self._summarize_workout_doc(workout_doc)
                if summary:
                    stats["patternA"] += 1
                else:
                    # Try Pattern B (flat alternating)
                    summary = self._detect_flat_alternating(workout_doc)
                    if summary:
                        stats["patternB"] += 1
                    else:
                        stats["bail_no_match"] += 1
                if summary:
                    stats["success"] += 1
            elif (evt.get("description") or "").strip():
                stats["bail_no_workout_doc"] += 1

            # Parse NOTE: lines from description (v0.3 — coach annotations)
            raw_desc = evt.get("description") or ""
            coach_notes = []
            clean_desc_lines = []
            past_notes = False
            for line in raw_desc.split("\n"):
                stripped = line.strip()
                if not past_notes and stripped.upper().startswith("NOTE:"):
                    note_text = stripped[5:].strip()
                    if note_text:
                        coach_notes.append(note_text)
                elif not past_notes and stripped == "":
                    continue  # skip blank lines between NOTE: lines and workout
                else:
                    past_notes = True
                    clean_desc_lines.append(line)
            clean_desc = "\n".join(clean_desc_lines).strip()

            entry = {
                "id": evt.get("id", f"unknown_{i+1}"),
                "date": evt_date,
                "name": evt.get("name", ""),
                "type": evt.get("category", ""),
                "sport_type": evt.get("type", ""),
                "planned_tss": evt.get("icu_training_load"),
                "duration_hours": round((evt.get("moving_time") or 0) / 3600, 2),
                "duration_formatted": self._format_duration(int(evt.get("moving_time") or 0)),
                "workout_summary": summary,
                "has_terrain": evt.get("id", f"unknown_{i+1}") in getattr(self, '_terrain_event_ids', set())
            }

            if coach_notes:
                entry["coach_notes"] = coach_notes
            
            # Start time: extract HH:MM when a real time is set (not midnight)
            raw_start = evt.get("start_date_local") or ""
            if "T" in raw_start:
                time_part = raw_start.split("T")[1][:5]
                if time_part != "00:00":
                    entry["start_time"] = time_part
            
            # Indoor flag: only include when True
            if evt.get("indoor"):
                entry["indoor"] = True
            
            if is_near:
                # Days 0-7: full detail
                entry["description"] = clean_desc
            else:
                # Days 8-42: skeleton only
                if summary is None:
                    lines = [l.strip() for l in clean_desc.split("\n") if l.strip()][:3]
                    entry["description_preview"] = "\n".join(lines) if lines else None
            
            result.append(entry)
        
        self._summary_stats = stats
        return result
    
    def _build_race_calendar(self, future_events: List[Dict], current_ctl: float,
                              current_atl: float, current_tsb: float,
                              activities_7d: List[Dict], today: str,
                              athlete_units: Optional[Dict[str, str]] = None) -> Dict:
        """
        Build race calendar with 3-layer awareness (v3.5.0).
        
        Layer 1: All races within 90-day window (always present)
        Layer 2: Taper onset alerts when RACE_A is 8-14 days out
        Layer 3: Race-week protocol when RACE_A/B is ≤7 days out
        
        References: Section 11A Race-Week Protocol
        Scientific basis: Mujika & Padilla (2003), Bosquet et al. (2007), Altini (HRV)
        
        athlete_units (v3.109): when provided, each race entry gets a
        display.distance block alongside canonical distance_meters.
        """
        
        today_date = datetime.strptime(today, "%Y-%m-%d").date()
        
        # Filter to race events only
        race_categories = {"RACE_A", "RACE_B", "RACE_C"}
        race_events = []
        for evt in future_events:
            cat = evt.get("category", "")
            if cat in race_categories:
                start = evt.get("start_date_local", "")[:10]
                if start:
                    try:
                        evt_date = datetime.strptime(start, "%Y-%m-%d").date()
                        days_until = (evt_date - today_date).days
                        if days_until >= 0:
                            distance_meters = evt.get("distance")
                            # Convert meters → km for the display helper (canonical kind="distance" expects km)
                            distance_km_for_display = (distance_meters / 1000) if distance_meters else None
                            race_entry = {
                                "name": evt.get("name", "Unnamed Race"),
                                "date": start,
                                "category": cat,
                                "type": evt.get("type", "Unknown"),
                                "days_until": days_until,
                                "moving_time_seconds": evt.get("moving_time"),
                                "distance_meters": distance_meters,
                                "display": {
                                    "distance": self._to_display(
                                        distance_km_for_display, "distance", athlete_units
                                    ),
                                },
                                "has_terrain": evt.get("id") in getattr(self, '_terrain_event_ids', set()),
                                "_raw": evt  # Keep raw for race-week building
                            }
                            # Start time: extract HH:MM when a real time is set
                            raw_start = evt.get("start_date_local") or ""
                            if "T" in raw_start:
                                time_part = raw_start.split("T")[1][:5]
                                if time_part != "00:00":
                                    race_entry["start_time"] = time_part
                            # Indoor flag: only include when True
                            if evt.get("indoor"):
                                race_entry["indoor"] = True
                            race_events.append(race_entry)
                    except ValueError:
                        continue
        
        # Sort by date
        race_events.sort(key=lambda x: x["days_until"])
        
        # Strip _raw from public output
        all_races = [{k: v for k, v in r.items() if k != "_raw"} for r in race_events]
        
        # Next race (any priority)
        next_race = all_races[0] if all_races else None
        
        # Taper alert: RACE_A within 8-14 days
        taper_race = next((r for r in race_events if r["category"] == "RACE_A" and 8 <= r["days_until"] <= 14), None)
        taper_alert = {"active": taper_race is not None}
        if taper_race:
            taper_alert["event_name"] = taper_race["name"]
            taper_alert["event_date"] = taper_race["date"]
            taper_alert["days_until"] = taper_race["days_until"]
            taper_alert["message"] = (
                f"RACE_A '{taper_race['name']}' in {taper_race['days_until']} days. "
                f"Begin volume reduction (target 41-60% over 2 weeks). Maintain intensity. "
                f"CTL should peak now or within the next few days."
            )
        
        # Race-week: RACE_A or RACE_B within 7 days
        # If both exist, prioritise RACE_A
        race_week_candidates = [r for r in race_events if r["category"] in {"RACE_A", "RACE_B"} and r["days_until"] <= 7]
        race_week_target = None
        if race_week_candidates:
            a_races = [r for r in race_week_candidates if r["category"] == "RACE_A"]
            race_week_target = a_races[0] if a_races else race_week_candidates[0]
        
        race_week = {"active": False}
        if race_week_target:
            race_week = self._build_race_week(
                race_event=race_week_target,
                current_ctl=current_ctl,
                current_atl=current_atl,
                current_tsb=current_tsb,
                activities_7d=activities_7d,
                today_date=today_date
            )
        
        return {
            "next_race": next_race,
            "all_races": all_races,
            "taper_alert": taper_alert,
            "race_week": race_week
        }
    
    def _build_race_week(self, race_event: Dict, current_ctl: float,
                          current_atl: float, current_tsb: float,
                          activities_7d: List[Dict], today_date) -> Dict:
        """
        Build race-week protocol data for D-7 through D-0.
        
        All load targets are relative to CTL. Normal weekly TSS = CTL × 7.
        Race-week TSS budget: 40-55% of normal weekly TSS (RACE_A) or 50-65% (RACE_B).
        
        TSB projection uses PMC decay: CTL_decay = e^(-1/42), ATL_decay = e^(-1/7).
        Assumes zero training load for remaining days to project race-day TSB.
        """
        
        evt_date = datetime.strptime(race_event["date"], "%Y-%m-%d").date()
        days_until = race_event["days_until"]
        category = race_event["category"]
        moving_time = race_event.get("moving_time_seconds")
        
        # Current day label
        current_day = f"D-{days_until}" if days_until > 0 else "D-0"
        
        # CTL baseline and normal weekly TSS
        ctl_baseline = current_ctl if current_ctl else 0
        normal_weekly_tss = round(ctl_baseline * 7, 1)
        
        # Race-week TSS budget (relative to category)
        if category == "RACE_A":
            budget_min_pct, budget_max_pct = 0.40, 0.55
        else:  # RACE_B
            budget_min_pct, budget_max_pct = 0.50, 0.65
        
        budget_min = round(normal_weekly_tss * budget_min_pct)
        budget_max = round(normal_weekly_tss * budget_max_pct)
        
        # Race-week TSS spent: sum TSS from activities within race week window
        race_week_start = evt_date - timedelta(days=7)
        tss_spent = 0
        for act in activities_7d:
            act_date_str = act.get("start_date_local", "")[:10]
            if act_date_str:
                try:
                    act_date = datetime.strptime(act_date_str, "%Y-%m-%d").date()
                    if race_week_start <= act_date <= today_date:
                        tss_spent += act.get("icu_training_load", 0) or 0
                except ValueError:
                    continue
        tss_spent = round(tss_spent)
        
        # TSB projection for race day (assume zero load for remaining days)
        ctl_decay = math.exp(-1/42)   # ~0.9765
        atl_decay = math.exp(-1/7)    # ~0.8668
        
        proj_ctl = current_ctl if current_ctl else 0
        proj_atl = current_atl if current_atl else 0
        for _ in range(days_until):
            proj_ctl *= ctl_decay
            proj_atl *= atl_decay
        projected_tsb = round(proj_ctl - proj_atl, 1)
        
        # Event duration classification
        if moving_time is not None:
            if moving_time < 5400:
                duration_class = "short_intense"
            elif moving_time <= 10800:
                duration_class = "medium"
            else:
                duration_class = "long_endurance"
        else:
            # Default by category when not set
            duration_class = "long_endurance" if category == "RACE_A" else "medium"
        
        # TSB target range by duration class
        tsb_targets = {
            "short_intense": {"min": 5, "max": 15},
            "medium": {"min": 10, "max": 20},
            "long_endurance": {"min": 10, "max": 25}
        }
        tsb_range = tsb_targets.get(duration_class, {"min": 10, "max": 25})
        
        # RACE_B: lower TSB target by 5
        if category == "RACE_B":
            tsb_range = {"min": max(0, tsb_range["min"] - 5), "max": tsb_range["max"] - 5}
        
        # Day-by-day decision tree
        day_protocol = self._get_day_protocol(days_until, ctl_baseline, duration_class, category)
        
        # Carb loading
        carb_applicable = False
        if moving_time is not None:
            carb_applicable = moving_time >= 5400
        elif category == "RACE_A":
            carb_applicable = True  # Default assumption for A races
        
        carb_active = carb_applicable and days_until <= 4
        carb_start_date = (evt_date - timedelta(days=4)).strftime("%Y-%m-%d")
        
        # Opener day (D-2)
        opener_date = (evt_date - timedelta(days=2)).strftime("%Y-%m-%d")
        opener_intensity = "lighter" if duration_class == "long_endurance" else (
            "more_intense" if duration_class == "short_intense" else "standard"
        )
        
        # Go/no-go: TSB status
        if projected_tsb >= tsb_range["min"]:
            tsb_status = "green"
            go_notes = []
        elif projected_tsb >= tsb_range["min"] - 10:
            tsb_status = "flag"
            go_notes = [f"Projected race-day TSB {projected_tsb} is below target range {tsb_range['min']}-{tsb_range['max']}. Consider additional rest."]
        else:
            tsb_status = "flag"
            go_notes = [f"Projected race-day TSB {projected_tsb} is significantly below target range {tsb_range['min']}-{tsb_range['max']}. Fatigue may impact performance."]
        
        return {
            "active": True,
            "event_name": race_event["name"],
            "event_date": race_event["date"],
            "event_category": category,
            "event_type": race_event.get("type", "Unknown"),
            "event_duration_class": duration_class,
            "event_moving_time_seconds": moving_time,
            "days_until_event": days_until,
            "current_day": current_day,
            "ctl_baseline": round(ctl_baseline, 1),
            "normal_weekly_tss": normal_weekly_tss,
            "race_week_tss_budget": {"min": budget_min, "max": budget_max},
            "race_week_tss_spent": tss_spent,
            "race_week_tss_remaining": {
                "min": max(0, budget_min - tss_spent),
                "max": max(0, budget_max - tss_spent)
            },
            "projected_race_day_tsb": projected_tsb,
            "tsb_target_range": tsb_range,
            "today": day_protocol,
            "carb_loading": {
                "applicable": carb_applicable,
                "active": carb_active,
                "starts": "D-4",
                "start_date": carb_start_date,
                "note": "10-12 g·kg⁻¹/day. No depletion phase needed." if carb_applicable else None
            },
            "opener": {
                "day": "D-2",
                "date": opener_date,
                "intensity": opener_intensity
            },
            "go_no_go": {
                "tsb_status": tsb_status,
                "notes": go_notes
            }
        }
    
    def _get_day_protocol(self, days_until: int, ctl: float, duration_class: str, category: str) -> Dict:
        """
        Return today's race-week protocol based on days until event.
        Load targets as TSS = percentage of CTL.
        """
        # Day protocol definitions: (label, min_pct, max_pct, zones, purpose)
        protocols = {
            7: ("Last key session", 0.75, 1.00, "3-5 efforts Z4-Z5 (1-3 min)", "Fitness confirmation. Verify strong power/HR response."),
            6: ("Recovery", 0.00, 0.30, "Z1-Z2 only", "Active recovery."),
            5: ("Moderate endurance", 0.40, 0.60, "Z1-Z2 + 2-3 race-pace touches", "Maintain feel without adding fatigue."),
            4: ("Easy / rest", 0.00, 0.40, "Z1-Z2 only", "Volume reduction. Carb loading begins if applicable."),
            3: ("Easy / rest", 0.00, 0.40, "Z1-Z2 only", "Taper tantrums expected (D-4 to D-2). Normal — not lost fitness."),
            2: ("Opener", 0.30, 0.50, "3-5 efforts Z4-Z6 (20-60s), high cadence, full recovery", "Neuromuscular activation."),
            1: ("Rest / minimal", 0.00, 0.20, "Z1 only if active", "Final rest, logistics, equipment check."),
            0: ("Race day", 0.00, 0.00, "Race effort", "Go/no-go assessment. Execute race plan.")
        }
        
        # Default for days > 7 (shouldn't happen in race week, but defensive)
        if days_until > 7:
            return {
                "label": "Pre-race-week",
                "load_target_tss": None,
                "zones": "Normal training",
                "purpose": "Race week protocol not yet active for this day."
            }
        
        label, min_pct, max_pct, zones, purpose = protocols.get(days_until, protocols[0])
        
        # Adjust opener intensity by duration class
        if days_until == 2:
            if duration_class == "long_endurance":
                zones = "3-4 efforts Z4 only (20-60s), moderate cadence, full recovery"
                purpose = "Light neuromuscular activation. Preserve glycogen."
            elif duration_class == "short_intense":
                zones = "5-6 efforts Z4-Z6 (10-30s), high cadence, full recovery"
                purpose = "Full neuromuscular activation for short, intense effort."
        
        # For long endurance events, prefer easy endurance over complete rest on D-4/D-3
        if days_until in (3, 4) and duration_class == "long_endurance":
            min_pct = 0.20  # Nudge minimum up — easy spin preferred over full rest
            purpose = f"{purpose} Easy endurance preferred over complete rest for long events."
        
        min_tss = round(ctl * min_pct)
        max_tss = round(ctl * max_pct)
        
        return {
            "label": label,
            "load_target_tss": {"min": min_tss, "max": max_tss},
            "zones": zones,
            "purpose": purpose
        }
    
    def _generate_race_alerts(self, race_calendar: Dict) -> List[Dict]:
        """Generate race-specific alerts for the alerts array."""
        alerts = []
        
        # Taper onset alert
        taper = race_calendar.get("taper_alert", {})
        if taper.get("active"):
            alerts.append({
                "metric": "race_taper",
                "value": taper.get("days_until"),
                "severity": "info",
                "threshold": "RACE_A within 8-14 days",
                "context": taper.get("message", "Taper onset detected."),
                "persistence_days": None,
                "tier": 1
            })
        
        # Race-week alerts
        rw = race_calendar.get("race_week", {})
        if rw.get("active"):
            # Daily status alert
            today_proto = rw.get("today", {})
            load = today_proto.get("load_target_tss", {})
            alerts.append({
                "metric": "race_week",
                "value": rw.get("days_until_event"),
                "severity": "info",
                "threshold": f"{rw.get('event_category')} within 7 days",
                "context": (
                    f"Race week {rw.get('current_day')} of '{rw.get('event_name')}'. "
                    f"Today: {today_proto.get('label', '?')}, "
                    f"{load.get('min', 0)}-{load.get('max', 0)} TSS. "
                    f"{today_proto.get('zones', '')}"
                ),
                "persistence_days": None,
                "tier": 1
            })
            
            # TSB projection warning
            projected = rw.get("projected_race_day_tsb")
            tsb_range = rw.get("tsb_target_range", {})
            if projected is not None and tsb_range:
                if projected < tsb_range.get("min", 0):
                    alerts.append({
                        "metric": "race_week_tsb",
                        "value": projected,
                        "severity": "warning",
                        "threshold": f"TSB target {tsb_range.get('min')}-{tsb_range.get('max')}",
                        "context": (
                            f"Projected race-day TSB {projected} is below target range "
                            f"{tsb_range.get('min')}-{tsb_range.get('max')}. "
                            f"Consider additional rest to reach target."
                        ),
                        "persistence_days": None,
                        "tier": 1
                    })
        
        return alerts
    
    def _compute_weekly_summary(self, activities: List[Dict], wellness: List[Dict]) -> Dict:
        """Compute weekly training summary from actual activity data"""
        total_tss = sum(act.get("icu_training_load", 0) for act in activities if act.get("icu_training_load"))
        total_seconds = sum(act.get("moving_time", 0) for act in activities)
        total_hours = total_seconds / 3600

        avg_hrv = None
        avg_rhr = None
        if wellness:
            hrv_values = [w.get("hrv") for w in wellness if self._is_valid_hrv(w.get("hrv"))]
            rhr_values = [w.get("restingHR") for w in wellness if w.get("restingHR")]
            avg_hrv = round(sum(hrv_values) / len(hrv_values), 1) if hrv_values else None
            avg_rhr = round(sum(rhr_values) / len(rhr_values), 1) if rhr_values else None

        return {
            "total_training_hours": round(total_hours, 2),
            "total_training_formatted": self._format_duration(int(total_seconds) // 60 * 60),
            "total_tss": round(total_tss, 0),
            "activities_count": len(activities),
            "avg_hrv": avg_hrv,
            "avg_resting_hr": avg_rhr
        }
    
    def _compute_activity_summary(self, activities: List[Dict], days_back: int = 7,
                                  athlete_units: Optional[Dict[str, str]] = None) -> Dict:
        """Compute summary by activity type with human-readable format.
        
        athlete_units (v3.109): when provided, each by_activity_type entry gets a
        display.distance block. Canonical distance_km stays unchanged for any
        consumer that calculates from this surface.
        """
        by_type = defaultdict(lambda: {"count": 0, "seconds": 0, "tss": 0, "distance_km": 0})
        
        for act in activities:
            activity_type = act.get("type", "Unknown")
            by_type[activity_type]["count"] += 1
            
            time_seconds = act.get("moving_time", 0)
            
            by_type[activity_type]["seconds"] += time_seconds
            by_type[activity_type]["tss"] += act.get("icu_training_load", 0) or 0
            by_type[activity_type]["distance_km"] += (act.get("distance", 0) or 0) / 1000
        
        activity_breakdown = {}
        total_seconds = 0
        
        for activity_type, data in sorted(by_type.items()):
            distance_km = round(data["distance_km"], 1)
            entry = {
                "duration_decimal_hours": round(data["seconds"] / 3600, 2),
                "count": data["count"],
                "tss": round(data["tss"], 0),
                "distance_km": distance_km,
                "display": {
                    "distance": self._to_display(distance_km, "distance", athlete_units),
                }
            }
            activity_breakdown[activity_type] = entry
            total_seconds += data["seconds"]
        
        return {
            "period_description": f"Last {days_back} days of training (including today)",
            "note": "Duration calculated from API moving_time field.",
            "total_duration_decimal_hours": round(total_seconds / 3600, 2),
            "total_activities": len(activities),
            "by_activity_type": activity_breakdown
        }
    
    def publish_to_github(self, data: Dict, filepath: str = "latest.json", 
                         commit_message: str = None) -> str:
        """Publish data to GitHub repository"""
        if not self.github_token or not self.github_repo:
            raise ValueError("GitHub token and repo required for publishing")
        
        if not commit_message:
            commit_message = f"Update training data - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github+json"
        }
        
        url = f"{self.GITHUB_API_URL}/repos/{self.github_repo}/contents/{filepath}"
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                current_file = response.json()
                current_sha = current_file["sha"]
                
                current_content = base64.b64decode(current_file["content"]).decode()
                new_content = json.dumps(data, indent=2, default=str)
                
                if current_content == new_content:
                    print("⏭️  No changes detected, skipping update")
                    raw_url = f"https://raw.githubusercontent.com/{self.github_repo}/main/{filepath}"
                    return raw_url
            else:
                current_sha = None
        except Exception as e:
            print(f"⚠️  Could not check existing file: {e}")
            current_sha = None
        
        content_json = json.dumps(data, indent=2, default=str)
        content_base64 = base64.b64encode(content_json.encode()).decode()
        
        payload = {
            "message": commit_message,
            "content": content_base64,
            "branch": "main"
        }
        
        if current_sha:
            payload["sha"] = current_sha
        
        response = requests.put(url, headers=headers, json=payload)
        response.raise_for_status()
        
        raw_url = f"https://raw.githubusercontent.com/{self.github_repo}/main/{filepath}"
        return raw_url
    
    def save_to_file(self, data: Dict, filepath: str = "latest.json"):
        """Save data to local JSON file"""
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Data saved to {filepath}")
        return filepath


# === Local Setup & Update Helpers ===

SECTION11_REPO_RAW = "https://raw.githubusercontent.com/CrankAddict/section-11/main"

# Directories/files to exclude from manifest generation
_MANIFEST_EXCLUDE_DIRS = {".git", ".github", "__pycache__", "node_modules"}
_MANIFEST_EXCLUDE_FILES = {"manifest.json", ".DS_Store"}


def _compute_file_hash(filepath):
    """Compute SHA256 hash of a file. Returns hex digest string."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def _fetch_upstream_manifest():
    """Fetch manifest.json from the official Section 11 repo.
    Returns manifest dict or None on failure. Caller handles errors."""
    try:
        response = requests.get(f"{SECTION11_REPO_RAW}/manifest.json", timeout=30)
        response.raise_for_status()
        manifest = response.json()
        if manifest.get("files"):
            return manifest
        return None
    except Exception:
        return None


def _compare_files(upstream_files, section11_dir):
    """Compare upstream manifest hashes against local files in section11/.
    Returns (needs_update, current) where each is a list of dicts.
    Detects changed files (hash mismatch) and new files (missing locally)."""
    needs_update = []
    current = []
    
    for path, info in upstream_files.items():
        upstream_hash = info.get("hash", "")
        description = info.get("description", "")
        local_path = section11_dir / path
        
        if not local_path.exists():
            needs_update.append({
                "path": path, "status": "new",
                "description": description
            })
        else:
            try:
                local_hash = _compute_file_hash(local_path)
            except Exception:
                local_hash = ""
            
            if local_hash != upstream_hash:
                needs_update.append({
                    "path": path, "status": "changed",
                    "description": description
                })
            else:
                current.append({
                    "path": path, "description": description
                })
    
    return needs_update, current


def _find_orphaned_files(upstream_files, section11_dir):
    """Find local files inside section11/ that are no longer in the upstream manifest.
    Returns a sorted list of relative path strings.
    Excludes manifest.json (local-only), .tmp files, and hidden files/directories."""
    manifest_paths = set(upstream_files.keys())
    orphaned = []

    for root, dirs, files in os.walk(section11_dir):
        # Skip hidden directories (e.g. .git, .DS_Store folders)
        dirs[:] = [d for d in dirs if not d.startswith('.')]

        for fname in files:
            # Skip hidden files, .tmp files, and manifest.json
            if fname.startswith('.'):
                continue
            if fname.endswith('.tmp'):
                continue

            full_path = Path(root) / fname
            rel_path = str(full_path.relative_to(section11_dir))

            if rel_path == "manifest.json":
                continue

            if rel_path not in manifest_paths:
                orphaned.append(rel_path)

    return sorted(orphaned)


def _find_empty_dirs(section11_dir):
    """Find directories inside section11/ that contain no visible files or subdirectories.
    Walks bottom-up so nested empty dirs are caught. Returns sorted list of relative path strings.
    Skips hidden directories at the top level of the walk."""
    empty_dirs = []

    # Bottom-up walk so we catch nested empties
    for root, dirs, files in os.walk(section11_dir, topdown=False):
        rel_dir = Path(root).relative_to(section11_dir)

        # Don't flag section11/ itself
        if rel_dir == Path('.'):
            continue

        # Skip hidden directories
        if any(part.startswith('.') for part in rel_dir.parts):
            continue

        # Visible files = non-hidden, non-.tmp
        visible_files = [f for f in files if not f.startswith('.') and not f.endswith('.tmp')]
        # Visible subdirs = non-hidden
        visible_dirs = [d for d in dirs if not d.startswith('.')]

        if not visible_files and not visible_dirs:
            empty_dirs.append(str(rel_dir))

    return sorted(empty_dirs)


def do_generate_manifest():
    """
    Generate manifest.json from the current repo directory.
    
    Maintainer command — walks the repo, computes SHA256 hashes for all files,
    and writes manifest.json. Preserves existing descriptions.
    Run from the repo root before committing.
    """
    repo_dir = Path.cwd()
    manifest_path = repo_dir / "manifest.json"
    
    # Load existing manifest to preserve descriptions
    existing_descriptions = {}
    if manifest_path.exists():
        try:
            with open(manifest_path, 'r') as f:
                old_manifest = json.load(f)
            for path, info in old_manifest.get("files", {}).items():
                desc = info.get("description")
                if desc:
                    existing_descriptions[path] = desc
        except Exception:
            pass
    
    # Walk the repo and hash all files
    files = {}
    for root, dirs, filenames in os.walk(repo_dir):
        # Exclude directories
        dirs[:] = [d for d in dirs if d not in _MANIFEST_EXCLUDE_DIRS]
        
        for filename in filenames:
            if filename in _MANIFEST_EXCLUDE_FILES:
                continue
            
            filepath = Path(root) / filename
            rel_path = filepath.relative_to(repo_dir).as_posix()
            
            # Skip hidden files
            if any(part.startswith('.') for part in rel_path.split('/')):
                continue
            
            try:
                file_hash = _compute_file_hash(filepath)
                entry = {"hash": file_hash}
                
                # Preserve existing description if present
                if rel_path in existing_descriptions:
                    entry["description"] = existing_descriptions[rel_path]
                
                files[rel_path] = entry
            except Exception as e:
                print(f"   ⚠️ Could not hash {rel_path}: {e}")
    
    # Sort by path for clean diffs
    sorted_files = dict(sorted(files.items()))
    
    manifest = {
        "scope": "All tracked files in the Section 11 repository. --update compares file hashes to detect changes and new files.",
        "files": sorted_files
    }
    
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
        f.write('\n')
    
    print(f"✅ manifest.json generated — {len(sorted_files)} files tracked")


def do_init():
    """
    Download and extract the full Section 11 repo to section11/.
    
    Standalone function — does not require Intervals.icu credentials.
    Downloads the repo as a zip from GitHub, extracts to section11/,
    and removes the bootstrap sync.py as the last step.
    """
    data_dir = Path.cwd()
    target_dir = data_dir / "section11"
    
    # Guard: already exists
    if target_dir.exists():
        print("Section 11: section11/ already exists in this directory")
        print("   To update: python section11/examples/sync.py --update")
        print("   To reinstall: delete section11/ and run --init again")
        return
    
    # Download zip
    zip_url = "https://github.com/CrankAddict/section-11/archive/refs/heads/main.zip"
    print("📦 Downloading Section 11 repository...")
    
    try:
        response = requests.get(zip_url, timeout=60)
        response.raise_for_status()
    except Exception as e:
        print(f"Section 11: download failed — {e}")
        print("   Alternative: git clone https://github.com/CrankAddict/section-11.git section11")
        return
    
    print(f"   Downloaded ({len(response.content) // 1024}KB)")
    
    # Extract to temp directory first, then move (atomic)
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "repo.zip"
            with open(zip_path, 'wb') as f:
                f.write(response.content)
            
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(tmp_dir)
            
            # GitHub zips have a top-level folder like "section-11-main/"
            extracted = [d for d in Path(tmp_dir).iterdir() 
                        if d.is_dir() and d.name != '__MACOSX']
            if len(extracted) != 1:
                print(f"Section 11: unexpected zip structure — expected 1 directory, found {len(extracted)}")
                return
            
            # Move extracted folder to section11/
            shutil.move(str(extracted[0]), str(target_dir))
    except Exception as e:
        print(f"Section 11: extraction failed — {e}")
        # Clean up partial extraction if it exists
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        return
    
    print(f"   ✅ Extracted to section11/")
    
    # Delete bootstrap sync.py — LAST STEP, only after extraction fully succeeded
    bootstrap_path = data_dir / "sync.py"
    repo_sync = target_dir / "examples" / "sync.py"
    bootstrap_removed = False
    
    if bootstrap_path.exists() and repo_sync.exists():
        # Verify bootstrap isn't the repo copy (safety check)
        try:
            if bootstrap_path.resolve() != repo_sync.resolve():
                bootstrap_path.unlink()
                bootstrap_removed = True
        except Exception as e:
            print(f"   ⚠️ Could not remove bootstrap sync.py: {e}")
    
    # Final message
    print(f"\n✅ Setup complete.")
    print(f"   sync.py is now at: section11/examples/sync.py")
    if bootstrap_removed:
        print(f"   Bootstrap copy removed.")
    print(f"\n   From now on, run:")
    print(f"      python section11/examples/sync.py --output latest.json")


def do_update():
    """
    Check for updates and pull changed files from the official Section 11 repo.
    
    Standalone function — does not require Intervals.icu credentials.
    Fetches manifest.json from GitHub, compares file hashes against local copies
    in section11/, and downloads only changed or new files after confirmation.
    """
    data_dir = Path.cwd()
    target_dir = data_dir / "section11"
    
    # Guard: section11/ must exist
    if not target_dir.exists():
        print("Section 11: section11/ not found in this directory")
        print("   Run --init first to set up the local data directory")
        return
    
    # Fetch manifest.json from upstream
    print("🔍 Checking for Section 11 updates...")
    manifest = _fetch_upstream_manifest()
    if not manifest:
        print("Section 11: could not fetch manifest from GitHub")
        return
    
    upstream_files = manifest.get("files", {})
    
    # Compare hashes against local files
    needs_update, current = _compare_files(upstream_files, target_dir)
    
    # Show updates or all-current message
    if not needs_update:
        print(f"✅ All {len(current)} files are current")
    else:
        # Show diff table
        print(f"\n   Updates available ({len(needs_update)} file{'s' if len(needs_update) != 1 else ''}):\n")

        # Calculate column widths for alignment
        path_width = max(len(u["path"]) for u in needs_update)

        for u in needs_update:
            path_padded = u["path"].ljust(path_width)
            desc = f"   {u['description']}" if u.get('description') else ""
            print(f"   {path_padded}  [{u['status']}]{desc}")

        if current:
            print(f"\n   Already current ({len(current)}):\n")
            for c in current[:10]:  # Show first 10 to avoid wall of text
                print(f"   ✅ {c['path']}")
            if len(current) > 10:
                print(f"   ... and {len(current) - 10} more")

        # Ask for confirmation
        print()
        try:
            answer = input(f"   Pull {len(needs_update)} update{'s' if len(needs_update) != 1 else ''}? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n   Cancelled")
            return

        if answer not in ("y", "yes"):
            print("   Cancelled")
            return

        # Download changed files
        print()
        updated = []
        failed = []

        for u in needs_update:
            file_url = f"{SECTION11_REPO_RAW}/{u['path']}"
            target_path = target_dir / u["path"]

            try:
                resp = requests.get(file_url, timeout=30)
                resp.raise_for_status()

                # Ensure target directory exists (for new files in new directories)
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # Write to temp file, then atomic replace
                tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
                with open(tmp_path, 'wb') as f:
                    f.write(resp.content)
                os.replace(str(tmp_path), str(target_path))

                updated.append(u)
                print(f"   ✅ {u['path']}  [{u['status']}]")
            except Exception as e:
                failed.append(u)
                print(f"   ❌ {u['path']}  failed: {e}")
                # Clean up temp file if it exists
                tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except Exception:
                        pass

        # Save updated manifest.json to section11/
        try:
            manifest_target = target_dir / "manifest.json"
            tmp_manifest = manifest_target.with_suffix(".json.tmp")
            with open(tmp_manifest, 'w') as f:
                json.dump(manifest, f, indent=2)
            os.replace(str(tmp_manifest), str(manifest_target))
        except Exception as e:
            print(f"   ⚠️ Could not save manifest.json locally: {e}")

        # Summary
        if failed:
            print(f"\n   Updated {len(updated)} file{'s' if len(updated) != 1 else ''}, {len(failed)} failed")
        elif updated:
            print(f"\n   ✅ {len(updated)} file{'s' if len(updated) != 1 else ''} updated")

        # --- Cache invalidation: sync.py schema change ---
        sync_updated = any(u["path"] == "examples/sync.py" for u in updated)
        if sync_updated:
            cache_cleared = []
            for cache_file in ("history.json", "intervals.json", "routes.json"):
                cache_path = data_dir / cache_file
                if cache_path.exists():
                    try:
                        cache_path.unlink()
                        cache_cleared.append(cache_file)
                    except Exception as e:
                        print(f"   ⚠️  Could not delete {cache_file}: {e}")
            if cache_cleared:
                print(f"\n   🔄 sync.py updated → cleared {', '.join(cache_cleared)}")
                print(f"      Timer users: full data after 2 cycles (~2 min)")
                print(f"      Manual users: run sync twice to rebuild")

    # --- Orphan cleanup (runs regardless of whether files were updated) ---
    orphaned_files = _find_orphaned_files(upstream_files, target_dir)
    empty_dirs = _find_empty_dirs(target_dir)

    if orphaned_files or empty_dirs:
        total = len(orphaned_files) + len(empty_dirs)
        print(f"\n   Orphaned items ({total} — not in repo):\n")

        # Build display list with tags
        all_items = [(p, "[removed from repo]") for p in orphaned_files]
        all_items += [(d + "/", "[empty directory]") for d in empty_dirs]

        path_width = max(len(item[0]) for item in all_items)
        for name, tag in all_items:
            print(f"   {name.ljust(path_width)}  {tag}")

        print()
        try:
            answer = input(f"   Remove {total} orphaned item{'s' if total != 1 else ''}? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n   Skipped")
            return

        if answer not in ("y", "yes"):
            print("   Skipped")
            return

        removed = 0

        # Delete orphaned files first
        for p in orphaned_files:
            full_path = target_dir / p
            try:
                full_path.unlink()
                removed += 1
                print(f"   🗑️  {p}")
            except Exception as e:
                print(f"   ❌ {p}  failed: {e}")

        # Remove empty parent directories left behind by file deletions
        for p in orphaned_files:
            parent = (target_dir / p).parent
            while parent != target_dir:
                try:
                    parent.rmdir()  # Only succeeds if empty
                    print(f"   🗑️  {parent.relative_to(target_dir)}/  [empty directory]")
                except OSError:
                    break
                parent = parent.parent

        # Remove standalone empty directories (sorted deepest-first to handle nesting)
        for d in sorted(empty_dirs, key=lambda x: x.count(os.sep), reverse=True):
            dir_path = target_dir / d
            try:
                if dir_path.exists():
                    dir_path.rmdir()
                    removed += 1
                    print(f"   🗑️  {d}/")
            except OSError as e:
                print(f"   ❌ {d}/  failed: {e}")

        if removed:
            print(f"\n   🗑️  {removed} orphaned item{'s' if removed != 1 else ''} removed")


def notify_if_updates_available():
    """
    Silent, rate-limited check for Section 11 updates during normal sync runs.
    
    Runs at most once per 24 hours. Fetches manifest.json from upstream,
    compares file hashes against local section11/ files, prints a one-line
    notification if updates are available. Completely silent on any failure —
    this must never interrupt a sync run.
    """
    try:
        config_path = Path.cwd() / ".sync_config.json"
        section11_dir = Path.cwd() / "section11"
        
        # Only relevant for local setups with section11/
        if not section11_dir.exists():
            return
        
        # Load config for rate limiting
        config = {}
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
        
        # Rate limit: once per 24 hours
        last_check = config.get("last_manifest_check")
        if last_check:
            try:
                last_dt = datetime.fromisoformat(last_check)
                if datetime.now() - last_dt < timedelta(hours=24):
                    return  # Checked recently, skip
            except (ValueError, TypeError):
                pass  # Malformed timestamp, proceed with check
        
        # Fetch manifest
        manifest = _fetch_upstream_manifest()
        if not manifest:
            return  # Silent failure
        
        # Compare hashes against local files
        needs_update, _ = _compare_files(manifest.get("files", {}), section11_dir)
        
        # Update timestamp regardless of result
        config["last_manifest_check"] = datetime.now().isoformat()
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Notify if updates available
        if needs_update:
            print(f"\n⚠️  {len(needs_update)} Section 11 update{'s' if len(needs_update) != 1 else ''} available — run: python section11/examples/sync.py --update")
    
    except Exception:
        pass  # Never interrupt a sync run


# === Lockfile for automated sync ===

_lockfile_path = None  # Module-level so atexit handler can find it


def _is_pid_alive(pid):
    """Check if a process with the given PID is still running."""
    try:
        os.kill(int(pid), 0)
        return True  # Process exists (we own it)
    except PermissionError:
        return True  # Process exists (owned by another user)
    except (OSError, ValueError, TypeError):
        return False  # Process doesn't exist or invalid PID


def _acquire_lockfile():
    """
    Acquire the sync lockfile. Returns True if acquired, False if another
    instance is running. Handles stale lockfiles from crashed runs.
    
    Stale detection:
    - PID in lockfile is dead → stale, override with warning
    - Lockfile older than 10 minutes regardless of PID → stale, override
    - PID alive and age < 10 minutes → another instance running, exit
    """
    global _lockfile_path
    lockfile = Path.cwd() / ".sync.lock"
    
    if lockfile.exists():
        try:
            with open(lockfile, 'r') as f:
                lock_data = json.load(f)
        except Exception:
            # Can't read lockfile — treat as stale
            print("Section 11: removing unreadable lockfile")
            lockfile.unlink(missing_ok=True)
            lock_data = None
        
        if lock_data:
            lock_pid = lock_data.get("pid")
            lock_time = lock_data.get("started")
            
            # Check if lock is stale by age (>10 minutes)
            stale_by_age = False
            if lock_time:
                try:
                    lock_dt = datetime.fromisoformat(lock_time)
                    age_minutes = (datetime.now() - lock_dt).total_seconds() / 60
                    if age_minutes > 10:
                        stale_by_age = True
                except (ValueError, TypeError):
                    stale_by_age = True  # Can't parse timestamp, treat as stale
            else:
                stale_by_age = True  # No timestamp, treat as stale
            
            # Check if owning process is alive
            pid_alive = _is_pid_alive(lock_pid) if lock_pid else False
            
            if pid_alive and not stale_by_age:
                # Legitimate lock — another instance is running
                return False
            
            # Stale lock — override
            if stale_by_age:
                print(f"Section 11: lockfile is stale (>10 min) — overriding")
            elif not pid_alive:
                print(f"Section 11: lockfile owner (PID {lock_pid}) is not running — overriding stale lock")
    
    # Write new lockfile
    _lockfile_path = lockfile
    try:
        with open(lockfile, 'w') as f:
            json.dump({"pid": os.getpid(), "started": datetime.now().isoformat()}, f)
        atexit.register(_release_lockfile)
        return True
    except Exception as e:
        print(f"Section 11: could not create lockfile — {e}")
        return True  # Proceed anyway, don't block sync over a lockfile issue


def _release_lockfile():
    """Remove the lockfile. Called via atexit on normal exit."""
    global _lockfile_path
    if _lockfile_path and _lockfile_path.exists():
        try:
            # Only remove if we still own it (check PID)
            with open(_lockfile_path, 'r') as f:
                lock_data = json.load(f)
            if lock_data.get("pid") == os.getpid():
                _lockfile_path.unlink(missing_ok=True)
        except Exception:
            pass  # Best effort cleanup


def _rotate_log_if_needed():
    """Rotate sync.log if over 1MB. Keeps the last 200 lines."""
    try:
        log_path = Path.cwd() / "sync.log"
        if not log_path.exists():
            return
        if log_path.stat().st_size < 1_000_000:  # 1MB
            return
        with open(log_path, 'r') as f:
            lines = f.readlines()
        with open(log_path, 'w') as f:
            f.writelines(lines[-200:])
    except Exception:
        pass  # Never block sync over a log issue


def main():
    parser = argparse.ArgumentParser(description="Sync Intervals.icu data to GitHub or local file")
    parser.add_argument("--setup", action="store_true", help="Initial setup wizard")
    parser.add_argument("--init", action="store_true", help="Download Section 11 repo to section11/ (first-time local setup)")
    parser.add_argument("--update", action="store_true", help="Check for and pull Section 11 updates")
    parser.add_argument("--athlete-id", help="Intervals.icu athlete ID")
    parser.add_argument("--intervals-key", help="Intervals.icu API key")
    parser.add_argument("--github-token", help="GitHub Personal Access Token")
    parser.add_argument("--github-repo", help="GitHub repo (format: username/repo)")
    parser.add_argument("--days", type=int, default=7, help="Days of data to export (default: 7)")
    parser.add_argument("--output", help="Save to local file instead of GitHub")
    parser.add_argument("--debug", action="store_true", help="Show debug output for API fields")
    parser.add_argument("--week-start", choices=["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                        default=None, help="Training week start day (default: mon, or from config)")
    parser.add_argument("--generate-history", action="store_true", help="Force generate history.json (pulls up to 3 years)")
    parser.add_argument("--generate-manifest", action="store_true", help="Generate manifest.json from repo files (maintainer use)")
    parser.add_argument("--lockfile", action="store_true", help="Prevent overlapping runs (recommended for automated timers)")
    
    args = parser.parse_args()
    
    if args.setup:
        print("=== Intervals.icu Sync Setup ===\n")
        athlete_id = input("Intervals.icu Athlete ID (e.g., i123456): ")
        intervals_key = input("Intervals.icu API Key: ")
        github_token = input("GitHub Personal Access Token (or press Enter to skip): ")
        github_repo = input("GitHub Repository (username/repo, or press Enter to skip): ")
        
        config = {
            "athlete_id": athlete_id,
            "intervals_key": intervals_key,
        }
        if github_token:
            config["github_token"] = github_token
        if github_repo:
            config["github_repo"] = github_repo
        
        week_input = input("Training week starts on (mon/tue/wed/thu/fri/sat/sun, default: mon): ").strip().lower()
        if week_input in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
            config["week_start"] = week_input
        
        zone_pref_input = input("Zone preference overrides (e.g. run:hr,cycling:power, or press Enter for default): ").strip()
        if zone_pref_input:
            config["zone_preference"] = zone_pref_input
            
        with open(".sync_config.json", "w") as f:
            json.dump(config, f, indent=2)
        print("\n✅ Config saved to .sync_config.json")
        print("\nUsage:")
        print("  Export locally:    python sync.py --output latest.json")
        print("  Push to GitHub:    python sync.py")
        print("  Generate history:  python sync.py --generate-history --output history.json")
        return
    
    if args.init:
        do_init()
        return
    
    if args.update:
        do_update()
        return
    
    if args.generate_manifest:
        do_generate_manifest()
        return
    
    # Rotate sync.log if it's grown too large
    _rotate_log_if_needed()
    
    # Lockfile: prevent overlapping runs (for automated timers)
    if args.lockfile:
        if not _acquire_lockfile():
            return  # Another instance is running
    
    config = {}
    if os.path.exists(".sync_config.json"):
        with open(".sync_config.json") as f:
            config = json.load(f)
    
    athlete_id = args.athlete_id or config.get("athlete_id") or os.getenv("ATHLETE_ID")
    intervals_key = args.intervals_key or config.get("intervals_key") or os.getenv("INTERVALS_KEY")
    github_token = args.github_token or config.get("github_token") or os.getenv("GITHUB_TOKEN")
    github_repo = args.github_repo or config.get("github_repo") or os.getenv("GITHUB_REPO")
    
    # Week start: CLI → config file → env var → default (Monday/ISO)
    week_day_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    week_start_raw = args.week_start or config.get("week_start") or os.getenv("WEEK_START") or "mon"
    week_start_day = week_day_map.get(week_start_raw.lower(), 0)
    week_start_name = {v: k for k, v in week_day_map.items()}.get(week_start_day, "mon")
    
    # Zone preference: config file → env var → default (power preferred)
    # Format: "run:hr,cycling:power" → {"run": "hr", "cycling": "power"}
    zone_pref_raw = config.get("zone_preference") or os.getenv("ZONE_PREFERENCE") or ""
    zone_preference = {}
    if zone_pref_raw:
        for pair in zone_pref_raw.split(","):
            pair = pair.strip()
            if ":" in pair:
                sport, basis = pair.split(":", 1)
                sport = sport.strip().lower()
                basis = basis.strip().lower()
                if basis in ("power", "hr"):
                    zone_preference[sport] = basis
                else:
                    print(f"   ⚠️  Ignoring invalid zone preference '{pair}' — basis must be 'power' or 'hr'")
            elif pair:
                print(f"   ⚠️  Ignoring invalid zone preference '{pair}' — expected format sport:basis")
    
    zone_pref_display = ", ".join(f"{s}:{b}" for s, b in zone_preference.items()) if zone_preference else "default (power preferred)"
    
    print(f"📋 Configuration:")
    print(f"   Athlete ID: {athlete_id[:5] + '...' if athlete_id else 'NOT SET'}")
    print(f"   Intervals Key: {intervals_key[:5] + '...' if intervals_key else 'NOT SET'}")
    print(f"   GitHub Repo: {github_repo or 'NOT SET'}")
    print(f"   GitHub Token: {'SET' if github_token else 'NOT SET'}")
    print(f"   Days: {args.days}")
    print(f"   Week start: {week_start_name}")
    print(f"   Zone preference: {zone_pref_display}")
    print(f"   Version: {IntervalsSync.VERSION}")
    
    if not athlete_id or not intervals_key:
        print("\n❌ Error: Missing credentials.")
        print("   Run: python sync.py --setup")
        return
    
    sync = IntervalsSync(athlete_id, intervals_key, github_token, github_repo, 
                         debug=args.debug, week_start_day=week_start_day,
                         zone_preference=zone_preference)
    
    # Manual history generation
    if args.generate_history:
        print(f"\n📊 Generating history.json (up to 3 years)...")
        history = sync.generate_history()
        dr = history.get("data_range", {})
        print(f"\n✅ history.json generated")
        print(f"   Range: {dr.get('earliest')} → {dr.get('latest')} ({dr.get('total_months')} months)")
        print(f"   FTP changes tracked: {len(history.get('ftp_timeline', []))}")
        print(f"   Data gaps found: {len(history.get('data_gaps', []))}")
        
        # Also publish to GitHub if credentials available
        if github_token and github_repo and not args.output:
            print("\n📤 Publishing history.json to GitHub...")
            sync.publish_to_github(history, filepath="history.json",
                                   commit_message=f"Generate history.json - {datetime.now().strftime('%Y-%m-%d')}")
            print("   ✅ history.json pushed to GitHub")
        return
    
    if not args.output and (not github_token or not github_repo):
        print("\n❌ Error: Missing GitHub credentials for push.")
        print("   Either use --output to save locally, or configure GitHub in --setup")
        return
    
    print(f"\n🔄 Fetching {args.days} days of data (extended 28 days for ACWR)...")
    
    # === AUTO HISTORY GENERATION (must precede collect_training_data so latest.json reads fresh history metadata) ===
    if sync.should_generate_history():
        try:
            print("\n📊 Auto-generating history.json...")
            history = sync.generate_history()
            if args.output:
                history_path = sync.data_dir / sync.HISTORY_FILE
                with open(history_path, 'w') as f:
                    json.dump(history, f, indent=2, default=str)
                print(f"   ✅ history.json saved to {history_path}")
            else:
                sync.publish_to_github(history, filepath="history.json",
                                       commit_message=f"Auto-generate history.json - {datetime.now().strftime('%Y-%m-%d')}")
                print("   ✅ history.json auto-generated and pushed to GitHub")
        except Exception as e:
            print(f"   ⚠️ History generation failed (non-critical): {e}")
    
    data = sync.collect_training_data(days_back=args.days)
    
    # Extract derived metrics for display
    dm = data.get("derived_metrics", {})
    alerts = data.get("alerts", [])
    
    # Common display function
    def print_summary():
        print(f"\n📊 Derived metrics:")
        print(f"   ACWR: {dm.get('acwr')} ({dm.get('acwr_interpretation')})")
        print(f"   Recovery Index: {dm.get('recovery_index')}")
        print(f"   Monotony: {dm.get('monotony')} ({dm.get('monotony_interpretation')})")
        print(f"   Strain: {dm.get('strain')}")
        print(f"   Gray Zone %: {dm.get('grey_zone_percentage')}%")
        print(f"   Quality Intensity %: {dm.get('quality_intensity_percentage')}%")
        print(f"   Easy Time Ratio: {dm.get('easy_time_ratio')} (target ~0.80)")
        tid = dm.get('seiler_tid_7d', {})
        tid_ps = dm.get('seiler_tid_7d_primary', {})
        print(f"   Seiler TID: {tid.get('classification')} (PI: {tid.get('polarization_index')}) — Z1:{tid.get('z1_pct')}% Z2:{tid.get('z2_pct')}% Z3:{tid.get('z3_pct')}%")
        if tid_ps:
            print(f"   Seiler TID ({tid_ps.get('sport')}): {tid_ps.get('classification')} (PI: {tid_ps.get('polarization_index')}) — Z1:{tid_ps.get('z1_pct')}% Z2:{tid_ps.get('z2_pct')}% Z3:{tid_ps.get('z3_pct')}%")
        print(f"   Consistency: {dm.get('consistency_index')}")
        print(f"   Phase: {dm.get('phase_detected')}")
        print(f"\n📈 Performance (from API):")
        print(f"   eFTP: {dm.get('eftp')}W")
        print(f"   W': {dm.get('w_prime_kj')}kJ")
        print(f"   P-max: {dm.get('p_max')}W")
        print(f"   VO2max: {dm.get('vo2max')}")
        bi_indoor = dm.get('benchmark_indoor', {})
        bi_outdoor = dm.get('benchmark_outdoor', {})
        print(f"   Indoor FTP:  {bi_indoor.get('current_ftp')}W → Benchmark: {bi_indoor.get('benchmark_percentage') or 'N/A (need 8 weeks)'}")
        print(f"   Outdoor FTP: {bi_outdoor.get('current_ftp')}W → Benchmark: {bi_outdoor.get('benchmark_percentage') or 'N/A (need 8 weeks)'}")
        
        # Display alerts
        if alerts:
            print(f"\n⚠️  Alerts ({len(alerts)}):")
            for alert in alerts:
                icon = "🔴" if alert["severity"] == "alarm" else "🟡" if alert["severity"] == "warning" else "ℹ️"
                print(f"   {icon} [{alert['severity'].upper()}] {alert['metric']}: {alert['context']}")
        else:
            print(f"\n✅ No alerts — green light")
        
        # Display history confidence
        history_info = data.get("history", {})
        if history_info.get("available"):
            print(f"\n📚 History: available ({history_info.get('history_confidence')} confidence, {history_info.get('total_months')}mo)")
        else:
            print(f"\n📚 History: not available (will auto-generate on this run)")
    
    if args.output:
        filepath = sync.save_to_file(data, args.output)
        print(f"   🔒 Athlete ID: REDACTED")
        print(f"\n✅ Data saved to {filepath}")
        print_summary()
        print(f"\n💡 Tip: Paste contents to AI, or upload the file directly")
        
        # === SAVE INTERVALS.JSON (local mode) ===
        intervals_data = getattr(sync, '_intervals_data', None)
        if intervals_data and intervals_data.get("activities"):
            intervals_path = sync.data_dir / sync.INTERVALS_FILE
            with open(intervals_path, 'w') as f:
                json.dump(intervals_data, f, indent=2, default=str)
            print(f"   📊 intervals.json saved ({len(intervals_data['activities'])} activities)")
        
        # === SAVE ROUTES.JSON (local mode) ===
        routes_data = getattr(sync, '_routes_data', None)
        if routes_data is not None:
            routes_path = sync.data_dir / sync.ROUTES_FILE
            with open(routes_path, 'w') as f:
                json.dump(routes_data, f, indent=2, default=str)
            print(f"   🗺️  routes.json saved ({len(routes_data.get('events', []))} event(s))")
    else:
        raw_url = sync.publish_to_github(data)
        
        print(f"\n✅ Data published to GitHub")
        print(f"   🔒 Athlete ID: REDACTED")
        print_summary()
        print(f"\n📊 Static URL for LLMs:")
        print(f"   {raw_url}")
        print(f"\n💬 Example prompt:")
        print(f'   "Analyze my training data from {raw_url}"')
        
        # === PUBLISH INTERVALS.JSON (GitHub mode) ===
        intervals_data = getattr(sync, '_intervals_data', None)
        if intervals_data and intervals_data.get("activities"):
            # Save locally for incremental cache on next run
            intervals_path = sync.data_dir / sync.INTERVALS_FILE
            with open(intervals_path, 'w') as f:
                json.dump(intervals_data, f, indent=2, default=str)
            try:
                sync.publish_to_github(intervals_data, filepath="intervals.json",
                                       commit_message=f"Update intervals.json - {datetime.now().strftime('%Y-%m-%d')}")
                print(f"   📊 intervals.json pushed ({len(intervals_data['activities'])} activities)")
            except Exception as e:
                print(f"   ⚠️ intervals.json push failed (non-critical): {e}")
        
        # === PUBLISH ROUTES.JSON (GitHub mode) ===
        routes_data = getattr(sync, '_routes_data', None)
        if routes_data is not None:
            # Save locally for cache on next run
            routes_path = sync.data_dir / sync.ROUTES_FILE
            with open(routes_path, 'w') as f:
                json.dump(routes_data, f, indent=2, default=str)
            try:
                sync.publish_to_github(routes_data, filepath="routes.json",
                                       commit_message=f"Update routes.json - {datetime.now().strftime('%Y-%m-%d')}")
                print(f"   🗺️  routes.json pushed ({len(routes_data.get('events', []))} event(s))")
            except Exception as e:
                print(f"   ⚠️ routes.json push failed (non-critical): {e}")
        
        # === UPDATE NOTIFICATIONS ===
        try:
            print("\n🔔 Checking for upstream updates...")
            sync.check_upstream_updates()
        except Exception as e:
            if args.debug:
                print(f"   ⚠️ Update check failed (non-critical): {e}")
    
    # === MANIFEST UPDATE CHECK (local setups, once per 24h) ===
    notify_if_updates_available()


if __name__ == "__main__":
    main()
