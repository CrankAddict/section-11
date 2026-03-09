#!/usr/bin/env python3
"""
Intervals.icu → GitHub/Local JSON Export
Exports training data for LLM access.
Supports both automated GitHub sync and manual local export.

Version 3.77 - Hash-based manifest for --update (all repo files tracked, no manual version bumps)
  - --generate-manifest: maintainer command, walks repo, hashes all files, writes manifest.json
  - --update: compares SHA256 hashes instead of version strings, detects new files automatically
  - notify/GitHub Issues: hash-based change detection
  - local_versions removed from .sync_config.json (local file hashes are the truth)

Version 3.76 - Bug fixes: workout summary off-by-one, deload phase detection
  - Workout summary parser: trailing solo work step (final rep, no paired rest) was silently dropped
    in both _detect_alternating_in_nested (Pattern A) and _try_alternating_block (Pattern B).
    e.g., 13×30s reported as 12×30s. Both paths now consume the orphaned trailing rep.
  - Phase detection Path C: retrospective deload when plan coverage is 0%.
    Existing paths required planned_tss_delta (Path A) or ctl_slope > 1.0 (Path B, unrealistic
    during deload). Path C: completed-week TSS ≤ 80% of prior-3-week avg + prior build evidence.
    Build evidence uses [-4:-1] slices to exclude the current deload week from averages.
    No hard-day gate — deload weeks legitimately contain reduced-volume quality sessions.
    Validated against 26 weeks: catches all confirmed deloads, zero false positives.

Version 3.75 - Working directory awareness + local setup
  - Data files (history.json, ftp_history.json) now write to caller's working directory, not script's directory
  - Enables running sync.py from a parent directory: python section11/examples/sync.py --output latest.json
  - No change for users who run sync.py from its own directory
  - Migration: if you run sync.py from a parent directory, move history.json and ftp_history.json to your working directory
  - --init flag: download the full Section 11 repo to section11/ for local-only setups (no GitHub needed)
  - --update flag: check for updates from official repo, show diff, pull changed files after confirmation
  - Manifest check on sync runs: once per 24h, silent notification if updates available
  - --lockfile flag: prevent overlapping runs for automated timers (stale detection via PID + 10-min age)
  - Update notifications: manifest.json preferred, changelog.json fallback (backward compatible)
  - Bootstrap flow: python sync.py --setup → python sync.py --init → use section11/examples/sync.py going forward

Version 3.73 - Phase detection: week-aligned prospective windows
  - Stream 2 windows aligned to training week instead of rolling 7-day from today
  - Fixes mid-week deload misclassification: rolling window leaked next week's build sessions
  - Configurable week start: .sync_config.json "week_start", WEEK_START env var, or --week-start CLI
  - Default Monday (ISO). Set once in config, never think about it again
  - Current week window: today → week end. Next week: next full training week
  - Planned TSS delta projected to full-week equivalent from remaining days
  - Hard sessions and plan coverage scoped to current week remainder only

Version 3.72 - Readiness Decision (AAS formalization)
  - Pre-computed go/modify/skip via P0-P3 priority ladder (safety → overload → fatigue → green light)
  - 7 signals evaluated: HRV, RHR, Sleep, TSB, ACWR, Feel, RI — green/amber/red/unavailable
  - Phase modifiers: Build loosens (3 amber), Taper/Race week tighten (1 amber), others default (2)
  - Structured modification output: triggers + adjustment directions (intensity/volume/cap_zone)
  - Wires into existing tier-1 alerts (P0/P1) — no duplication
  - Top-level readiness_decision object in output JSON, alongside alerts

Version 3.71 - HRRc (heart rate recovery) integration
  - Added icu_hrr (HRRc) field to formatted activity output as "hrrc"
  - Added _calculate_hrrc_trend(): 7d/28d aggregate HRRc in capability namespace
  - Qualifying: icu_hrr not null, min 1 session/7d, min 3 sessions/28d
  - Trend: >10% difference = improving/declining (conservative for field noise)
  - Display only — not wired into readiness_decision signals

Version 3.7 - Phase detection v2: dual-stream architecture (retrospective + prospective)
  - Stream 1: 4-week lookback from weekly_180d — CTL slope, ACWR trend, hard-day density, monotony
  - Stream 2: planned workouts + race calendar — planned TSS delta, hard sessions, race proximity
  - 8 phase states: Build/Base/Peak/Taper/Deload/Recovery/Overreached/null
  - Confidence scoring (high/medium/low), reason codes, hysteresis from previous_phase
  - weekly_180d enriched: per-week phase_detected, acwr, monotony, intensity_basis_breakdown
  - Overreached false-positive fixes, Peak/Deload gate refinements

Version 3.6.5 - Real IDs + Coach Notes
  - Activity/event IDs always real (opaque keys, not PII). Athlete ID still REDACTED when anonymized
  - coach_notes array: NOTE: lines parsed from activity/event descriptions
  - chat_notes array: fetches activity messages endpoint when has_messages is true
  - Enables push.py v0.3 annotate round-trip (write via push.py, read via sync.py)

Version 3.6.4 - READ_THIS_FIRST display_formatting instruction, report template XhYm alignment
Version 3.6.3 - Human-readable _formatted fields (duration, sleep, training hours), floored to minutes
Version 3.6.2 - Workout summary parser (Pattern A/B), tiered planned workout detail (0-7d full, 8-42d skeleton)
Version 3.6.1 - Hard day HR zone fallback (2-rung ladder), intensity_basis audit field
Version 3.6.0 - Efficiency Factor (EF) tracking, 7d/28d aggregate with trend

Version 3.5.1 - HRV outlier filter (_is_valid_hrv(), 10-250ms range), applied to baselines/RI/summaries
Version 3.5.0 - Race calendar (90-day, RACE_A/B/C), race-week protocol (D-7 to D-0), TSB projection

Version 3.4.1 - KeyError fix, defensive .get(), anonymization improvements
Version 3.4.0 - Aggregate durability (7d/28d decoupling), dual-timeframe TID, capability namespace
Version 3.3.4 - Seiler TID classification, Treff PI, multi-sport TID, 7→3 zone mapping
Version 3.3.0 - Graduated alerts, history.json, notifications, smart fitness metrics, ACWR/monotony/strain
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


class IntervalsSync:
    """Sync Intervals.icu data to GitHub repository or local file"""
    
    INTERVALS_BASE_URL = "https://intervals.icu/api/v1"
    GITHUB_API_URL = "https://api.github.com"
    FTP_HISTORY_FILE = "ftp_history.json"
    HISTORY_FILE = "history.json"
    UPSTREAM_REPO = "CrankAddict/section-11"
    CHANGELOG_FILE = "changelog.json"
    VERSION = "3.77"

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
    
    # Training week start day (Python weekday: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6)
    # Default Monday (ISO). Override via .sync_config.json, WEEK_START env var, or --week-start CLI arg.
    WEEK_START_DAY = 0
    
    def __init__(self, athlete_id: str, intervals_api_key: str, github_token: str = None, 
                 github_repo: str = None, debug: bool = False, week_start_day: int = None):
        self.athlete_id = athlete_id
        self.intervals_auth = base64.b64encode(f"API_KEY:{intervals_api_key}".encode()).decode()
        self.github_token = github_token
        self.github_repo = github_repo
        self.debug = debug
        self.script_dir = Path(__file__).parent
        self.data_dir = Path.cwd()  # Data files (history.json, ftp_history.json) write to caller's working directory
        self.week_start_day = week_start_day if week_start_day is not None else self.WEEK_START_DAY
    
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
    
    def collect_training_data(self, days_back: int = 7, anonymize: bool = False) -> Dict:
        """Collect all training data for LLM analysis"""
        # Extended range for ACWR calculation (need 28 days minimum)
        days_for_acwr = 28
        oldest_extended = (datetime.now() - timedelta(days=days_for_acwr - 1)).strftime("%Y-%m-%d")
        oldest_display = (datetime.now() - timedelta(days=days_back - 1)).strftime("%Y-%m-%d")
        newest = datetime.now().strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        
        print("Fetching athlete data...")
        athlete = self._intervals_get("")
        
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
        
        # Build race calendar (v3.5.0) — moved before derived metrics for phase detection
        print("Building race calendar...")
        race_calendar = self._build_race_calendar(
            future_events=future_events,
            current_ctl=ctl,
            current_atl=atl,
            current_tsb=tsb,
            activities_7d=activities_display,
            today=today
        )
        
        # Format planned workouts — used by both phase detection and output
        formatted_planned_workouts = self._format_events(near_future_events, anonymize, today=today)
        
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
            race_calendar=race_calendar
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
                "capability_metrics_note": "The 'capability' block in derived_metrics contains durability trend (aggregate decoupling 7d/28d), efficiency factor trend (aggregate EF 7d/28d), HRRc trend (heart rate recovery 7d/28d), and TID comparison (7d vs 28d distribution drift). These measure HOW the athlete expresses fitness, not just load. Use these for coaching context alongside traditional load metrics. Durability and EF trend direction matters more than absolute values. HRRc is display only — higher = better parasympathetic recovery.",
                "readiness_decision_note": "The 'readiness_decision' block contains a pre-computed go/modify/skip recommendation with priority level (P0=safety, P1=overload, P2=fatigue, P3=green), individual signal statuses, phase-adjusted thresholds, and structured modification guidance. Use this as the baseline for pre-workout recommendations. Override with explanation in the coach note if the AI's contextual judgment disagrees.",
                "quick_stats": {
                    "total_training_hours": round(sum(act.get("moving_time", 0) for act in activities_display) / 3600, 2),
                    "total_training_formatted": self._format_duration(int(sum(act.get("moving_time", 0) for act in activities_display)) // 60 * 60),
                    "total_activities": len(activities_display),
                    "total_tss": round(sum(act.get("icu_training_load", 0) for act in activities_display if act.get("icu_training_load")), 0)
                }
            },
            "metadata": {
                "athlete_id": "REDACTED" if anonymize else self.athlete_id,
                "last_updated": datetime.now().isoformat(),
                "data_range_days": days_back,
                "extended_range_days": days_for_acwr,
                "version": self.VERSION
            },
            "alerts": alerts,
            "readiness_decision": readiness_decision,
            "history": history_info,
            "summary": self._compute_activity_summary(activities_display, days_back),
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
                    "resting_hr": latest_wellness.get("restingHR") or athlete.get("icu_resting_hr"),
                    "hrv": latest_wellness.get("hrv"),
                    "sleep_quality": latest_wellness.get("sleepQuality"),
                    "sleep_hours": round(latest_wellness.get("sleepSecs", 0) / 3600, 2) if latest_wellness.get("sleepSecs") else None,
                    "sleep_formatted": self._format_duration(int(latest_wellness.get("sleepSecs", 0)) // 60 * 60) if latest_wellness.get("sleepSecs") else None
                }
            },
            "derived_metrics": derived_metrics,
            "recent_activities": self._format_activities(activities_display, anonymize),
            "wellness_data": self._format_wellness(wellness),
            "planned_workouts": formatted_planned_workouts,
            "workout_summary_stats": getattr(self, '_summary_stats', {}),
            "weekly_summary": self._compute_weekly_summary(activities_display, wellness),
            "race_calendar": race_calendar
        }
        
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
    
    def _calculate_derived_metrics(self, activities_7d: List[Dict], activities_28d: List[Dict],
                                    wellness_7d: List[Dict], wellness_extended: List[Dict],
                                    current_ctl: float, current_atl: float, current_tsb: float,
                                    past_events: List[Dict], activities_for_consistency: List[Dict],
                                    power_model: Dict,
                                    benchmark_indoor: Tuple[Optional[float], Optional[int], Optional[int]],
                                    benchmark_outdoor: Tuple[Optional[float], Optional[int], Optional[int]],
                                    vo2max: float,
                                    formatted_planned_workouts: List[Dict] = None,
                                    race_calendar: Dict = None) -> Dict:
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
        
        # === GREY ZONE PERCENTAGE (Z3 - to be minimized in polarized training) ===
        # Reference: Seiler - "too much pain for too little gain"
        grey_zone_percentage = round((z3_time / total_zone_time) * 100, 1) if total_zone_time > 0 else None
        
        # === QUALITY INTENSITY PERCENTAGE (Z4+ per Seiler's model) ===
        # Reference: Seiler's Zone 3 = above LT2 = Z4+ in 7-zone model
        # This is the "hard" work that should be ~20% in polarized training
        quality_intensity_percentage = round((z4_plus_time / total_zone_time) * 100, 1) if total_zone_time > 0 else None
        
        # === POLARISATION INDEX ===
        # Formula: (Z1 + Z2) / Total - measures how much time is "easy"
        # Target: ~80% for polarized training
        polarisation_index = round((z1_time + z2_time) / total_zone_time, 2) if total_zone_time > 0 else None
        
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

        # === CONSISTENCY INDEX ===
        consistency_index, consistency_details = self._calculate_consistency_index(
            activities_for_consistency, past_events
        )
        
        # === HARD DAYS THIS WEEK ===
        # Uses _classify_hard_day() for consistent power/HR evaluation.
        # Power: 5-rung cumulative ladder (Seiler/Foster)
        # HR fallback: 2-rung conservative ladder (above LT2 only)
        hard_days_this_week = 0
        activities_by_date_7d = {}
        for a in activities_7d:
            a_date = a.get("start_date_local", "")[:10]
            if a_date not in activities_by_date_7d:
                activities_by_date_7d[a_date] = []
            activities_by_date_7d[a_date].append(a)
        
        for date_str, day_acts in activities_by_date_7d.items():
            day_zones_by_basis = {}
            for a in day_acts:
                zones, basis = self._get_activity_zones(a)
                if zones and basis:
                    if basis not in day_zones_by_basis:
                        day_zones_by_basis[basis] = {}
                    for zid, secs in zones.items():
                        day_zones_by_basis[basis][zid] = day_zones_by_basis[basis].get(zid, 0) + secs
            
            is_hard, _basis = self._classify_hard_day(day_zones_by_basis)
            if is_hard:
                hard_days_this_week += 1
        
        # === PHASE DETECTION v2 (dual-stream) ===
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Load weekly_180d lookback from history.json
        weekly_rows = self._load_weekly_rows_for_phase()
        previous_phase = None
        if weekly_rows:
            previous_phase = weekly_rows[-1].get("phase_detected")
        
        phase_result = self._detect_phase_v2(
            weekly_rows=weekly_rows,
            planned_workouts=formatted_planned_workouts,
            race_calendar=race_calendar,
            previous_phase=previous_phase,
            today=today
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
                "total_hours": round(total_zone_time / 3600, 2)
            },
            "grey_zone_percentage": grey_zone_percentage,
            "grey_zone_note": "Gray Zone % (Z3/tempo) - minimize in polarized training",
            "quality_intensity_percentage": quality_intensity_percentage,
            "quality_intensity_note": "Quality Intensity % (Z4+/threshold+) - target ~20% in polarized training",
            "polarisation_index": polarisation_index,
            "polarisation_note": "Easy time (Z1+Z2) / Total - target ~80% in polarized training",
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
        elif acwr <= 1.3:
            return "optimal"
        elif acwr <= 1.5:
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

    @staticmethod
    def _get_activity_zones(activity: Dict) -> tuple:
        """
        Extract zone times from a single activity.
        
        Returns (zones_dict, basis) where:
        - zones_dict: {"z1": secs, "z2": secs, ...} 
        - basis: "power" | "hr" | None
        
        Power zones (icu_zone_times): list of {"id": "Z3", "secs": 600}
        HR zones (icu_hr_zone_times): flat array of seconds [0, 120, 300, 180, 60]
        
        Power preferred. HR fallback only when power unavailable.
        HR zones typically 5-zone (indices 0-4 → z1-z5), sometimes 7.
        """
        # Try power zones first
        icu_zone_times = activity.get("icu_zone_times", [])
        if icu_zone_times:
            pz = {}
            for zone in icu_zone_times:
                zone_id = zone.get("id", "").lower()
                secs = zone.get("secs", 0)
                if zone_id in ("z1", "z2", "z3", "z4", "z5", "z6", "z7"):
                    pz[zone_id] = secs
            if pz:
                return (pz, "power")
        
        # Fallback to HR zones
        icu_hr_zone_times = activity.get("icu_hr_zone_times", [])
        if icu_hr_zone_times:
            zone_labels = ("z1", "z2", "z3", "z4", "z5", "z6", "z7")
            hz = {}
            for idx, secs in enumerate(icu_hr_zone_times):
                if idx < len(zone_labels) and secs:
                    hz[zone_labels[idx]] = secs
            if hz:
                return (hz, "hr")
        
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
        
        Uses _get_activity_zones() for consistent power/HR fallback.
        """
        z1_time = 0
        z2_time = 0
        z3_time = 0
        z4_plus_time = 0
        total_time = 0
        
        for act in activities:
            zones, _basis = self._get_activity_zones(act)
            
            if zones:
                z1_time += zones.get("z1", 0)
                z2_time += zones.get("z2", 0)
                z3_time += zones.get("z3", 0)
                z4_plus_time += (zones.get("z4", 0) + zones.get("z5", 0) + 
                               zones.get("z6", 0) + zones.get("z7", 0))
                total_time += sum(zones.values())
        
        return {
            "z1_time": z1_time,
            "z2_time": z2_time,
            "z3_time": z3_time,
            "z4_plus_time": z4_plus_time,
            "total_time": total_time
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

        Uses power zones when available, falls back to HR zones.

        Args:
            activities: List of activity dicts with zone data
            sport_family_filter: If set, only include activities matching
                                 this sport family (from SPORT_FAMILIES)

        Returns dict with z1_seconds, z2_seconds, z3_seconds, total_seconds
        """
        sz1 = 0
        sz2 = 0
        sz3 = 0

        for act in activities:
            # Apply sport family filter if specified
            if sport_family_filter:
                activity_type = act.get("type", "Unknown")
                if self.SPORT_FAMILIES.get(activity_type, "other") != sport_family_filter:
                    continue

            zones = None

            # Power zones (preferred)
            icu_zone_times = act.get("icu_zone_times", [])
            if icu_zone_times:
                pz = {}
                for zone in icu_zone_times:
                    zone_id = zone.get("id", "").lower()
                    secs = zone.get("secs", 0)
                    if zone_id in ["z1", "z2", "z3", "z4", "z5", "z6", "z7"]:
                        pz[zone_id] = secs
                if pz:
                    zones = pz

            # HR zones (fallback)
            if not zones:
                icu_hr_zone_times = act.get("icu_hr_zone_times", [])
                if icu_hr_zone_times:
                    zone_labels = ["z1", "z2", "z3", "z4", "z5", "z6", "z7"]
                    hz = {}
                    for idx, secs in enumerate(icu_hr_zone_times):
                        if idx < len(zone_labels) and secs:
                            hz[zone_labels[idx]] = secs
                    if hz:
                        zones = hz

            if zones:
                sz1 += zones.get("z1", 0) + zones.get("z2", 0)
                sz2 += zones.get("z3", 0)
                sz3 += (zones.get("z4", 0) + zones.get("z5", 0) +
                        zones.get("z6", 0) + zones.get("z7", 0))

        total = sz1 + sz2 + sz3
        return {
            "z1_seconds": sz1,
            "z2_seconds": sz2,
            "z3_seconds": sz3,
            "total_seconds": total
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
        """
        zones = self._aggregate_seiler_zones(activities, sport_family_filter)
        total = zones["total_seconds"]

        if total == 0:
            return {
                "z1_seconds": 0,
                "z2_seconds": 0,
                "z3_seconds": 0,
                "z1_pct": None,
                "z2_pct": None,
                "z3_pct": None,
                "polarization_index": None,
                "classification": None
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
            "classification": classification
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
                dec = act.get("icu_hr_decoupling") or act.get("decoupling")
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

        if self.debug:
            print(f"  Durability: 7d={mean_7d} ({len(vals_7d)} sessions), "
                  f"28d={mean_28d} ({len(vals_28d)} sessions), trend={trend}")

        return {
            "mean_decoupling_7d": mean_7d,
            "mean_decoupling_28d": mean_28d,
            "high_drift_count_7d": high_drift_7d,
            "high_drift_count_28d": high_drift_28d,
            "qualifying_sessions_7d": len(vals_7d),
            "qualifying_sessions_28d": len(vals_28d),
            "trend": trend,
            "note": ("Steady-state power sessions only (VI <= 1.05, VI > 0, "
                     ">= 90min, power data). Negative decoupling = strong "
                     "durability. Trend compares 7d vs 28d mean "
                     "(+/-1% = stable).")
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
                    hrrc = hrrc.get("value") or hrrc.get("hrr")
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
                          today: str = None, dossier_declared: Optional[str] = None) -> Dict:
        """
        Dual-stream phase detection (v2).
        
        Stream 1: Completed history — rolling 4-week lookback from weekly_180d rows.
        Stream 2: Planned calendar — next 7-14 days of planned workouts + race calendar.
        
        Returns full phase output structure with confidence and reason_codes.
        
        Phase states: Build, Base, Peak, Taper, Deload, Recovery, Overreached, null.
        """
        if today is None:
            today = datetime.now().strftime("%Y-%m-%d")
        
        reason_codes = []
        
        # Compute features from both streams
        s1 = self._phase_stream1_features(weekly_rows)
        s2 = self._phase_stream2_features(planned_workouts, race_calendar, s1, today)
        
        # Data quality assessment
        data_quality = self._phase_data_quality(weekly_rows, s1, reason_codes)
        
        # Classification
        phase, confidence, extra_reasons = self._phase_classify(
            s1, s2, previous_phase, data_quality
        )
        reason_codes.extend(extra_reasons)
        
        # Phase duration: count consecutive weeks of same phase from recent weekly rows
        phase_duration = 0
        if phase and weekly_rows:
            for row in reversed(weekly_rows):
                if row.get("phase_detected") == phase:
                    phase_duration += 1
                else:
                    break
        
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
    
    def _phase_stream1_features(self, weekly_rows: List[Dict]) -> Dict:
        """
        Extract Stream 1 (retrospective) features from weekly_180d rows.
        Uses last 4 weeks for trend detection.
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
            "suggested_phase": None
        }
        
        if not weekly_rows:
            return result
        
        # Use last 4 weeks (or fewer if not available)
        recent = weekly_rows[-4:] if len(weekly_rows) >= 4 else weekly_rows
        
        # CTL slope: linear trend over available weeks
        ctl_values = [r.get("ctl_end") for r in recent if r.get("ctl_end") is not None]
        result["ctl_values"] = ctl_values
        if len(ctl_values) >= 2:
            # Simple slope: (last - first) / n_weeks
            result["ctl_slope"] = round((ctl_values[-1] - ctl_values[0]) / len(ctl_values), 2)
        
        # TSS values for trend
        result["tss_values"] = [r.get("total_tss", 0) or 0 for r in recent]
        
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
        # Path A: Current week ACWR > 1.5 (acute spike, Gabbett danger zone)
        # Path B: Sustained elevated monotony (>2.5) + ACWR trending up or >1.3
        if mono_trend == "elevated":
            # Use CURRENT week's ACWR, not historical max — a spike 3 weeks ago
            # that's since resolved should not keep triggering Overreached
            current_acwr = recent_rows[-1].get("acwr") if recent_rows else None
            if current_acwr is not None and current_acwr > 1.5:
                return "Overreached"
            # Sustained pattern: elevated monotony + ACWR still above normal
            if current_acwr is not None and current_acwr > 1.3 and acwr_trend == "rising":
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
                                 stream1: Dict, today: str) -> Dict:
        """
        Extract Stream 2 (prospective) features from planned workouts and race calendar.
        
        Windows are aligned to the training week (configurable via
        .sync_config.json, WEEK_START env var, or --week-start CLI;
        default Monday/ISO). This prevents mid-week contamination where
        a deload week's window leaks into the next build week.
        
        - Current week remainder: today → last day of training week
        - Next week: next full training week (7 days)
        """
        result = {
            "planned_tss_delta": None,
            "hard_sessions_planned": 0,
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
        
        for pw in planned_workouts:
            pw_date_str = (pw.get("date") or "")[:10]
            if not pw_date_str or pw_date_str == "unknown":
                continue
            try:
                pw_date = datetime.strptime(pw_date_str, "%Y-%m-%d")
            except ValueError:
                continue
            
            # Current week remainder (today through Saturday)
            if today_date <= pw_date <= current_week_end:
                current_week_workouts.append(pw)
                current_week_tss += (pw.get("planned_tss") or 0)
            # Next full training week (Sunday through Saturday)
            elif next_week_start <= pw_date <= next_week_end:
                next_week_workouts.append(pw)
        
        # Plan coverage: sessions / expected sessions
        # TODO(v3.71): expected_sessions should use avg activity_count from weekly_180d rows
        # (available in rows but not currently passed through stream1 features).
        # Hard-coded 5 means athletes training 7×/week get coverage >1.0, and 3×/week get 0.6.
        # Impact is limited: plan_coverage only adjusts confidence, not classification.
        tss_values = stream1.get("tss_values", [])
        weeks_avail = stream1.get("weeks_available", 0)
        expected_sessions = 5
        if weeks_avail > 0:
            pass  # Future: extract from weekly_rows activity_count average
        
        result["plan_coverage_current_week"] = round(
            len(current_week_workouts) / expected_sessions, 2
        ) if expected_sessions > 0 else 0.0
        result["plan_coverage_next_week"] = round(
            len(next_week_workouts) / expected_sessions, 2
        ) if expected_sessions > 0 else 0.0
        
        # Planned TSS delta: current week remainder planned / avg of prior 3 weeks actual
        avg_tss_prev_21d = None
        if tss_values and len(tss_values) >= 3:
            avg_tss_prev_21d = statistics.mean(tss_values[-3:])
        elif tss_values:
            avg_tss_prev_21d = statistics.mean(tss_values)
        
        # Scale: project current week remainder to full-week equivalent
        # so it's comparable to the historical weekly average.
        # days_remaining = days_to_week_end + 1 (inclusive of today)
        days_remaining = days_to_week_end + 1
        if avg_tss_prev_21d and avg_tss_prev_21d > 0 and current_week_tss > 0 and days_remaining > 0:
            projected_week_tss = current_week_tss * (7 / days_remaining)
            result["planned_tss_delta"] = round(projected_week_tss / avg_tss_prev_21d, 2)
        
        # Next week TSS delta (for Deload confirmation: does load resume?)
        next_week_tss = sum(pw.get("planned_tss") or 0 for pw in next_week_workouts)
        if avg_tss_prev_21d and avg_tss_prev_21d > 0 and next_week_tss > 0:
            result["next_week_tss_delta"] = round(next_week_tss / avg_tss_prev_21d, 2)
        
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
        
        # Planned week continues pattern (Stream 2) — only if enough planned sessions
        if next_7d_sessions >= 3:
            if s2.get("hard_sessions_planned", 0) >= 2:
                build_score += 1
            elif s2.get("hard_sessions_planned", 0) <= 1:
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
        latest_hrv = derived_metrics.get("latest_hrv")
        latest_rhr = derived_metrics.get("latest_rhr")
        hrv_baseline_7d = derived_metrics.get("hrv_baseline_7d")
        rhr_baseline_7d = derived_metrics.get("rhr_baseline_7d")
        
        # --- ACWR Alerts ---
        if acwr is not None:
            if acwr <= 0.75 or acwr >= 1.35:
                alerts.append({
                    "metric": "acwr",
                    "value": acwr,
                    "severity": "alarm",
                    "threshold": "0.75 / 1.35",
                    "context": f"ACWR {acwr} outside safe range. Injury/overreach risk elevated.",
                    "persistence_days": None,
                    "tier": 2
                })
            elif acwr <= 0.8 or acwr >= 1.3:
                alerts.append({
                    "metric": "acwr",
                    "value": acwr,
                    "severity": "warning",
                    "threshold": "0.8 / 1.3",
                    "context": f"ACWR {acwr} at edge of optimal range. Monitor closely. Alarm at 0.75/1.35.",
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
            elif ri < 0.7:
                alerts.append({
                    "metric": "recovery_index",
                    "value": ri,
                    "severity": "warning",
                    "threshold": 0.7,
                    "context": f"RI {ri} < 0.7. Monitor — if persists >3 days, deload review required.",
                    "persistence_days": None,
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
        
        # --- Durability Alerts (v3.4.0) ---
        # Aggregate decoupling trend from capability metrics
        capability = derived_metrics.get("capability", {})
        durability = capability.get("durability", {})
        dur_mean_7d = durability.get("mean_decoupling_7d")
        dur_mean_28d = durability.get("mean_decoupling_28d")
        dur_trend = durability.get("trend")
        dur_high_drift_7d = durability.get("high_drift_count_7d", 0)

        # Alarm: sustained high decoupling (28d mean > 5%)
        if dur_mean_28d is not None and dur_mean_28d > 5.0:
            alerts.append({
                "metric": "durability",
                "value": dur_mean_28d,
                "severity": "alarm",
                "threshold": "28d mean > 5%",
                "context": f"Sustained high decoupling ({dur_mean_28d}% 28d mean). Aerobic efficiency concern — review volume and recovery.",
                "persistence_days": None,
                "tier": 3
            })
        # Warning: declining trend with >2% delta
        elif (dur_trend == "declining" and dur_mean_7d is not None
              and dur_mean_28d is not None
              and (dur_mean_7d - dur_mean_28d) > 2.0):
            alerts.append({
                "metric": "durability",
                "value": dur_mean_7d,
                "severity": "warning",
                "threshold": "7d > 28d by > 2%",
                "context": f"Durability declining: 7d mean decoupling {dur_mean_7d}% vs 28d {dur_mean_28d}%. Check fatigue and recovery.",
                "persistence_days": None,
                "tier": 3
            })

        # Warning: repeated poor durability (>= 3 high-drift sessions in 7d)
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
    
    def _get_latest_feel(self, activities: List[Dict]) -> Optional[int]:
        """Get most recent non-null feel value from activities.
        Intervals.icu convention: 1=Strong(best), 5=Weak(worst)."""
        for act in reversed(activities):
            feel = act.get("feel")
            if feel is not None:
                return feel
        return None
    
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
          P1 — Acute overload: ACWR > 1.5, compound TSB+HRV, RI < 0.7 + persistent alerts → Skip/Modify
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
        
        # Feel from most recent activity (1=Strong/best, 5=Weak/worst)
        feel = self._get_latest_feel(activities)
        
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
        
        # Sleep signal
        if sleep_hours is not None:
            sleep_red = sleep_hours < 5 or (sleep_quality is not None and sleep_quality >= 4)
            sleep_amber = (not sleep_red) and (sleep_hours < 7 or (sleep_quality is not None and sleep_quality >= 3))
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
        if acwr is not None:
            if acwr > 1.5:
                acwr_status = "red"
            elif acwr > 1.3:
                acwr_status = "amber"
            elif acwr < 0.8:
                acwr_status = "amber"
            else:
                acwr_status = "green"
            signals["acwr"] = {"status": acwr_status, "value": acwr}
        else:
            signals["acwr"] = {"status": "unavailable", "value": None}
        
        # Feel signal (1=Strong/best, 5=Weak/worst — Intervals.icu convention)
        if feel is not None:
            if feel >= 5:
                feel_status = "red"
            elif feel >= 4:
                feel_status = "amber"
            else:
                feel_status = "green"
            signals["feel"] = {"status": feel_status, "value": feel}
        else:
            signals["feel"] = {"status": "unavailable", "value": None}
        
        # RI signal (Section 8: >= 0.8 good, 0.6-0.79 moderate fatigue, < 0.6 deload)
        if ri is not None:
            if ri < 0.6:
                ri_status = "red"
            elif ri < 0.8:
                ri_status = "amber"
            else:
                ri_status = "green"
            signals["ri"] = {"status": ri_status, "value": ri}
        else:
            signals["ri"] = {"status": "unavailable", "value": None}
        
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
        
        if acwr is not None and acwr > 1.5:
            p1_skip_reasons.append(f"ACWR {acwr} > 1.5")
        
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
        if acwr is not None and acwr > 1.3:
            p1_modify_reasons.append(f"ACWR {acwr} > 1.3")
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
                "modification": self._build_modification(["acwr"] if acwr and acwr > 1.3 else amber_signals),
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
        has_feel = "feel" in triggers
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
        
        # Feel-only: reduce intensity
        if has_feel:
            return {"triggers": triggers, "suggested_adjustments": {"intensity": "reduce", "volume": "preserve", "cap_zone": None}}
        
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
        daily_90d = self._build_daily_tier(activities_by_date, wellness_by_date, days=90)
        
        # === 180-DAY WEEKLY ===
        print("  Building 180-day weekly tier...")
        weekly_180d = self._build_weekly_tier(activities_by_date, wellness_by_date, days=180)
        
        # === PHASE BACKFILL ===
        # Retroactively classify phase for each weekly row using trailing 4-week window.
        # Stream 2 (planned calendar) is unavailable for historical weeks — confidence is limited.
        empty_race_cal = {"next_race": None, "all_races": [], "taper_alert": {"active": False}, "race_week": {"active": False}}
        for i in range(len(weekly_180d)):
            lookback = weekly_180d[max(0, i-3):i+1]
            prev_phase = weekly_180d[i-1].get("phase_detected") if i > 0 else None
            result = self._detect_phase_v2(
                weekly_rows=lookback,
                planned_workouts=[],
                race_calendar=empty_race_cal,
                previous_phase=prev_phase,
                today=weekly_180d[i]["week_start"]
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
                    activities_by_date, wellness_by_date, days=days_back
                )
            else:
                monthly_tiers[f"monthly_{label}"] = []
        
        # === SUMMARIES ===
        summaries = self._build_history_summaries(daily_90d, weekly_180d, monthly_tiers)
        
        history = {
            "generated_at": now.isoformat(),
            "source": "Intervals.icu API",
            "sync_version": self.VERSION,
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
                          days: int) -> List[Dict]:
        """Build daily resolution rows for the 90-day tier."""
        rows = []
        now = datetime.now()
        
        for i in range(days - 1, -1, -1):
            date = (now - timedelta(days=i))
            date_str = date.strftime("%Y-%m-%d")
            
            day_activities = activities_by_date.get(date_str, [])
            wellness = wellness_by_date.get(date_str, {})
            
            total_tss = sum(a.get("icu_training_load", 0) or 0 for a in day_activities)
            total_seconds = sum(a.get("moving_time", 0) or 0 for a in day_activities)
            activity_types = list(set(a.get("type", "Unknown") for a in day_activities)) if day_activities else ["Rest"]
            
            # Hard day detection via shared classifier (power + HR fallback)
            day_zones_by_basis = {}
            for a in day_activities:
                zones, basis = self._get_activity_zones(a)
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
                "feel": None,  # Not available in wellness, only in activities
                "weight_kg": wellness.get("weight"),
                "is_hard_day": is_hard,
                "intensity_basis": intensity_basis
            })
            
            # Check feel from activities
            for a in day_activities:
                feel = a.get("feel")
                if feel:
                    rows[-1]["feel"] = feel
                    break
        
        return rows
    
    def _build_weekly_tier(self, activities_by_date: Dict, wellness_by_date: Dict,
                           days: int) -> List[Dict]:
        """Build weekly aggregate rows for the 180-day tier."""
        rows = []
        now = datetime.now()
        
        # Calculate weeks
        start_date = now - timedelta(days=days)
        # Align to Monday
        start_monday = start_date - timedelta(days=start_date.weekday())
        
        current = start_monday
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
                    
                    zones, basis = self._get_activity_zones(a)
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
                    if feel:
                        week_feel.append(feel)
                
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
            
            rows.append({
                "week_start": current.strftime("%Y-%m-%d"),
                "total_hours": round(week_seconds / 3600, 2),
                "total_tss": round(week_tss, 0),
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
                "weight_kg": round(week_weight[-1], 1) if week_weight else None,
                "monotony": week_monotony,
                "intensity_basis_breakdown": intensity_basis_counts if hard_days > 0 else None,
                "acwr": None,  # computed in post-pass below
                "phase_detected": None  # populated by _detect_phase_v2
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
                            days: int) -> List[Dict]:
        """Build monthly aggregate rows for 1/2/3-year tiers."""
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
                    
                    zones, basis = self._get_activity_zones(a)
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
            
            # Determine dominant phase (simplified: based on CTL trend and zone distribution)
            dominant_phase = "Unknown"
            if ctl_values and len(ctl_values) >= 2:
                ctl_trend = ctl_values[-1] - ctl_values[0]
                qi_pct = (z4_plus_time / total_zone_time * 100) if total_zone_time > 0 else 0
                
                if ctl_trend > 3 and qi_pct > 15:
                    dominant_phase = "Build"
                elif ctl_trend > 1:
                    dominant_phase = "Base"
                elif ctl_trend < -3:
                    dominant_phase = "Recovery"
                else:
                    dominant_phase = "Maintenance"
            
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
    
    def _format_activities(self, activities: List[Dict], anonymize: bool = False) -> List[Dict]:
        """Format activities for LLM analysis"""
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
            if anonymize:
                if act.get("type", "") in self.OUTDOOR_TYPES:
                    activity_name = "Training Session"
            
            raw_hrrc = act.get("icu_hrr")
            if isinstance(raw_hrrc, dict):
                raw_hrrc = raw_hrrc.get("value") or raw_hrrc.get("hrr")
            
            activity = {
                "id": act.get("id", f"unknown_{i+1}"),
                "date": act.get("start_date_local", "unknown"),
                "type": act.get("type", "Unknown"),
                "name": activity_name,
                "duration_hours": round((act.get("moving_time") or 0) / 3600, 2),
                "distance_km": round((act.get("distance") or 0) / 1000, 2),
                "tss": act.get("icu_training_load"),
                "intensity_factor": act.get("icu_intensity"),
                "avg_power": avg_power,
                "normalized_power": norm_power,
                "avg_hr": avg_hr,
                "max_hr": max_hr,
                "avg_cadence": avg_cadence,
                "avg_speed": avg_speed,
                "max_speed": max_speed,
                "avg_pace": avg_pace,
                "avg_temp": avg_temp,
                "weather": weather,
                "humidity": humidity,
                "wind_speed": wind_speed,
                "work_kj": work_kj,
                "calories": calories,
                "carbs_used": carbs_used,
                "carbs_ingested": carbs_ingested,
                "variability_index": variability_index,
                "decoupling": decoupling,
                "efficiency_factor": act.get("icu_efficiency_factor"),
                "hrrc": raw_hrrc,
                "elevation_m": act.get("total_elevation_gain"),
                "feel": act.get("feel"),
                "rpe": act.get("icu_rpe"),
                "zone_distribution": zone_dist
            }

            # Parse NOTE: lines from activity description (v0.3 — coach annotations)
            raw_desc = act.get("description") or ""
            if raw_desc.strip():
                coach_notes = []
                for line in raw_desc.split("\n"):
                    stripped = line.strip()
                    if stripped.upper().startswith("NOTE:"):
                        note_text = stripped[5:].strip()
                        if note_text:
                            coach_notes.append(note_text)
                    elif stripped:
                        break  # stop at first non-NOTE, non-blank line
                if coach_notes:
                    activity["coach_notes"] = coach_notes

            # Fetch activity chat messages if available (v0.3 — --chat annotations)
            if act.get("has_messages"):
                activity_id = act.get("id")
                if activity_id:
                    notes = self._get_activity_messages(activity_id)
                    if notes:
                        activity["chat_notes"] = notes
            
            formatted.append(activity)
        
        return formatted
    
    def _format_wellness(self, wellness: List[Dict]) -> List[Dict]:
        """Format wellness data"""
        formatted = []
        for w in wellness:
            entry = {
                "date": w.get("id", "unknown"),
                "weight_kg": w.get("weight"),
                "resting_hr": w.get("restingHR"),
                "hrv_rmssd": w.get("hrv"),
                "hrv_sdnn": w.get("hrvSdnn"),
                "sleep_hours": round(w["sleepSecs"] / 3600, 2) if w.get("sleepSecs") else None,
                "sleep_formatted": self._format_duration(int(w["sleepSecs"]) // 60 * 60) if w.get("sleepSecs") else None,
                "sleep_quality": w.get("sleepQuality"),
                "sleep_score": w.get("sleepScore"),
                "mental_energy": w.get("mentalEnergy"),
                "fatigue": w.get("fatigue"),
                "soreness": w.get("soreness"),
                "avg_sleeping_hr": w.get("avgSleepingHR"),
                "vo2max": w.get("vo2max")
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
    
    def _format_events(self, events: List[Dict], anonymize: bool = False, today: str = None) -> List[Dict]:
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
                "planned_tss": evt.get("icu_training_load"),
                "duration_hours": round((evt.get("moving_time") or 0) / 3600, 2),
                "duration_formatted": self._format_duration(int(evt.get("moving_time") or 0)),
                "workout_summary": summary
            }

            if coach_notes:
                entry["coach_notes"] = coach_notes
            
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
                              activities_7d: List[Dict], today: str) -> Dict:
        """
        Build race calendar with 3-layer awareness (v3.5.0).
        
        Layer 1: All races within 90-day window (always present)
        Layer 2: Taper onset alerts when RACE_A is 8-14 days out
        Layer 3: Race-week protocol when RACE_A/B is ≤7 days out
        
        References: Section 11A Race-Week Protocol
        Scientific basis: Mujika & Padilla (2003), Bosquet et al. (2007), Altini (HRV)
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
                            race_events.append({
                                "name": evt.get("name", "Unnamed Race"),
                                "date": start,
                                "category": cat,
                                "type": evt.get("type", "Unknown"),
                                "days_until": days_until,
                                "moving_time_seconds": evt.get("moving_time"),
                                "distance_meters": evt.get("distance"),
                                "_raw": evt  # Keep raw for race-week building
                            })
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
    
    def _compute_activity_summary(self, activities: List[Dict], days_back: int = 7) -> Dict:
        """Compute summary by activity type with human-readable format"""
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
            activity_breakdown[activity_type] = {
                "duration_decimal_hours": round(data["seconds"] / 3600, 2),
                "count": data["count"],
                "tss": round(data["tss"], 0),
                "distance_km": round(data["distance_km"], 1)
            }
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
    
    # Nothing to update
    if not needs_update:
        print(f"✅ All {len(current)} files are current")
        return
    
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
    parser.add_argument("--anonymize", action="store_true", default=True, help="Remove identifying information (default: enabled)")
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
    
    print(f"📋 Configuration:")
    print(f"   Athlete ID: {athlete_id[:5] + '...' if athlete_id else 'NOT SET'}")
    print(f"   Intervals Key: {intervals_key[:5] + '...' if intervals_key else 'NOT SET'}")
    print(f"   GitHub Repo: {github_repo or 'NOT SET'}")
    print(f"   GitHub Token: {'SET' if github_token else 'NOT SET'}")
    print(f"   Days: {args.days}")
    print(f"   Week start: {week_start_name}")
    print(f"   Version: {IntervalsSync.VERSION}")
    
    if not athlete_id or not intervals_key:
        print("\n❌ Error: Missing credentials.")
        print("   Run: python sync.py --setup")
        return
    
    sync = IntervalsSync(athlete_id, intervals_key, github_token, github_repo, 
                         debug=args.debug, week_start_day=week_start_day)
    
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
    
    data = sync.collect_training_data(days_back=args.days, anonymize=args.anonymize)
    
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
        print(f"   Polarisation: {dm.get('polarisation_index')} (target ~0.80)")
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
        if args.anonymize:
            print(f"   🔒 Anonymization: ENABLED")
        print(f"\n✅ Data saved to {filepath}")
        print_summary()
        print(f"\n💡 Tip: Paste contents to AI, or upload the file directly")
        
        # === AUTO HISTORY GENERATION (local mode) ===
        if sync.should_generate_history():
            try:
                print("\n📊 Auto-generating history.json...")
                history = sync.generate_history()
                history_path = sync.data_dir / sync.HISTORY_FILE
                with open(history_path, 'w') as f:
                    json.dump(history, f, indent=2, default=str)
                print(f"   ✅ history.json saved to {history_path}")
            except Exception as e:
                print(f"   ⚠️ History generation failed (non-critical): {e}")
    else:
        raw_url = sync.publish_to_github(data)
        
        print(f"\n✅ Data published to GitHub")
        if args.anonymize:
            print(f"   🔒 Anonymization: ENABLED")
        print_summary()
        print(f"\n📊 Static URL for LLMs:")
        print(f"   {raw_url}")
        print(f"\n💬 Example prompt:")
        print(f'   "Analyze my training data from {raw_url}"')
        
        # === AUTO HISTORY GENERATION (Sundays/Mondays, first two runs after midnight) ===
        if sync.should_generate_history():
            try:
                print("\n📊 Auto-generating history.json...")
                history = sync.generate_history()
                sync.publish_to_github(history, filepath="history.json",
                                       commit_message=f"Auto-generate history.json - {datetime.now().strftime('%Y-%m-%d')}")
                print("   ✅ history.json auto-generated and pushed to GitHub")
            except Exception as e:
                print(f"   ⚠️ History generation failed (non-critical): {e}")
        
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
