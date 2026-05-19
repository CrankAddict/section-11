#!/usr/bin/env python3
"""
pull.py - Read activity data from Intervals.icu on demand.

Part of Section 11 (https://github.com/CrankAddict/section-11).
For agentic AI platforms with code execution, or for humans/AIs who want
the raw GPS/altitude data behind a `terrain_summary` for deeper analysis.

Subcommands:
  trace      Fetch per-second streams (latlng, altitude, time, distance, …)
  units      Show the athlete's unit preferences (sanity-check helper)

This is a READ-ONLY tool. Unlike push.py, there is no --confirm gate
because nothing is mutated on the Intervals.icu side.

Usage:
  python pull.py trace --activity-id i142557875
  python pull.py trace --activity-id i142557875 --types latlng,altitude
  python pull.py trace --activity-id i142557875 --out trace.json
  python pull.py units

Credentials (checked in order):
  1. CLI args: --athlete-id, --api-key
  2. .sync_config.json (same file sync.py and push.py use)
  3. Environment: ATHLETE_ID, INTERVALS_KEY

Output:
  trace          JSON streams response from Intervals to stdout (or --out file)
  units          Pretty-printed unit settings to stdout

Notes on the streams response shape:
  Intervals returns a list of stream objects. Each has:
    - type:   stream name ("latlng", "altitude", "watts", …)
    - data:   primary array of values (1Hz)
    - data2:  secondary array, ONLY populated for "latlng" where
              data = latitudes, data2 = longitudes (NOT the Strava
              paired-array convention — they are two parallel arrays)
  GPS dropouts produce None entries at matching indices in lat/lng.
  Altitude is independent of GPS (barometric on most Garmin devices)
  and may have fewer Nones than latlng.

Available stream types (verified, may vary by activity):
  time, watts, cadence, heartrate, distance, altitude, latlng,
  velocity_smooth, temp, torque, left_pedal_smoothness,
  left_torque_effectiveness, dfa_a1, respiration, artifacts
  (Pro/supporter accounts also see: wind_speed, wind_direction,
  gusts, Bearing, A Wind, yaw_angle on outdoor activities)
"""

import argparse
import json
import os
import sys
from typing import Optional, Tuple


_requests = None


def _ensure_requests():
    """Import `requests` on first use. Raise a clear error if it's missing."""
    global _requests
    if _requests is None:
        try:
            import requests
        except ImportError:
            raise RuntimeError(
                "The `requests` library is not installed in the Python "
                "interpreter running pull.py. Install it with "
                "`pip install requests`, or run pull.py from the same "
                "venv/environment as sync.py."
            )
        _requests = requests
    return _requests


class IntervalsPull:
    """Read-only client for Intervals.icu activity data."""

    BASE_URL = "https://intervals.icu/api/v1"
    VERSION = "0.1"

    def __init__(self, athlete_id: str, api_key: str):
        if not athlete_id or not api_key:
            raise ValueError("athlete_id and api_key are required")
        self.athlete_id = athlete_id
        self.api_key = api_key

    def _auth(self) -> Tuple[str, str]:
        """HTTP Basic auth tuple. User is the literal string 'API_KEY'."""
        return ("API_KEY", self.api_key)

    def fetch_streams(self, activity_id: str, types: Optional[str] = None) -> dict:
        """
        Fetch per-second streams for an activity.

        Returns a dict with:
          success:   bool
          streams:   list of stream objects (when success=True)
          status:    HTTP status code
          error:     short message (when success=False)
        """
        requests = _ensure_requests()
        url = f"{self.BASE_URL}/activity/{activity_id}/streams.json"
        params = {}
        if types:
            params["types"] = types
        try:
            resp = requests.get(url, auth=self._auth(), params=params, timeout=60)
        except requests.exceptions.Timeout:
            return {"success": False, "error": "timeout", "status": None}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"network: {str(e)[:120]}", "status": None}

        if resp.status_code != 200:
            return {
                "success": False,
                "status": resp.status_code,
                "error": f"http_{resp.status_code}: {resp.text[:200]}"
            }
        try:
            data = resp.json()
        except ValueError:
            return {"success": False, "status": 200, "error": "non-json response"}
        if not isinstance(data, list):
            return {"success": False, "status": 200, "error": f"unexpected shape: {type(data).__name__}"}
        return {"success": True, "status": 200, "streams": data}

    def fetch_athlete(self) -> dict:
        """
        Fetch the athlete object (used for unit preference inspection).

        Returns:
          success: bool
          athlete: dict (when success=True)
          error:   str (when success=False)
        """
        requests = _ensure_requests()
        url = f"{self.BASE_URL}/athlete/0"
        try:
            resp = requests.get(url, auth=self._auth(), timeout=30)
        except requests.exceptions.Timeout:
            return {"success": False, "error": "timeout"}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"network: {str(e)[:120]}"}
        if resp.status_code != 200:
            return {"success": False, "error": f"http_{resp.status_code}"}
        try:
            return {"success": True, "athlete": resp.json()}
        except ValueError:
            return {"success": False, "error": "non-json response"}


def _load_credentials(args) -> Tuple[Optional[str], Optional[str]]:
    """Load credentials from CLI args, config file, or environment."""
    config = {}
    if os.path.exists(".sync_config.json"):
        try:
            with open(".sync_config.json") as f:
                config = json.load(f)
        except Exception:
            config = {}

    athlete_id = (
        getattr(args, "athlete_id", None)
        or config.get("athlete_id")
        or os.getenv("ATHLETE_ID")
    )
    api_key = (
        getattr(args, "api_key", None)
        or config.get("intervals_key")
        or os.getenv("INTERVALS_KEY")
    )
    return athlete_id, api_key


def _output(result: dict, out_path: Optional[str] = None):
    """Write result as JSON to a file (if --out given) or stdout."""
    payload = json.dumps(result, indent=2)
    if out_path:
        with open(out_path, "w") as f:
            f.write(payload)
        # Print a small confirmation line to stderr so stdout stays clean
        # for any caller that might still want to capture file path.
        print(f"wrote {out_path} ({len(payload)} bytes)", file=sys.stderr)
    else:
        print(payload)
    sys.exit(0 if result.get("success") else 1)


def _cmd_trace(args, puller: IntervalsPull):
    if not args.activity_id:
        _output({"success": False, "error": "--activity-id is required"})
    types = args.types  # comma-separated list or None
    result = puller.fetch_streams(args.activity_id, types=types)
    _output(result, out_path=args.out)


def _cmd_units(args, puller: IntervalsPull):
    result = puller.fetch_athlete()
    if not result.get("success"):
        _output(result)
    athlete = result["athlete"]
    units = {
        "wind_speed": athlete.get("wind_speed"),
        "fahrenheit": athlete.get("fahrenheit"),
        "rain": athlete.get("rain"),
        "measurement_preference": athlete.get("measurement_preference"),
        "weight_pref_lb": athlete.get("weight_pref_lb"),
        "height_units": athlete.get("height_units"),
    }
    _output({"success": True, "units": units}, out_path=args.out)


def main():
    parser = argparse.ArgumentParser(
        prog="pull.py",
        description="Read activity data from Intervals.icu on demand (read-only)."
    )
    parser.add_argument("--athlete-id", help="Intervals.icu athlete ID")
    parser.add_argument("--api-key", help="Intervals.icu API key")

    subparsers = parser.add_subparsers(dest="command", required=True)

    trace_p = subparsers.add_parser(
        "trace",
        help="Fetch per-second streams (latlng, altitude, etc.) for one activity."
    )
    trace_p.add_argument("--activity-id", required=True,
                         help="Activity ID (e.g. i142557875)")
    trace_p.add_argument("--types", default=None,
                         help="Comma-separated stream types (default: all available). "
                              "Common useful subset: 'latlng,altitude,time,distance'")
    trace_p.add_argument("--out", default=None,
                         help="Write JSON to this path instead of stdout")

    units_p = subparsers.add_parser(
        "units",
        help="Show the athlete's unit preferences (wind, temp, rain, etc.)"
    )
    units_p.add_argument("--out", default=None,
                         help="Write JSON to this path instead of stdout")

    args = parser.parse_args()

    athlete_id, api_key = _load_credentials(args)
    if not athlete_id or not api_key:
        _output({
            "success": False,
            "error": "Missing credentials. Provide via --athlete-id/--api-key, "
                     ".sync_config.json, or ATHLETE_ID/INTERVALS_KEY env vars."
        })

    puller = IntervalsPull(athlete_id=athlete_id, api_key=api_key)

    if args.command == "trace":
        _cmd_trace(args, puller)
    elif args.command == "units":
        _cmd_units(args, puller)
    else:
        parser.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()
