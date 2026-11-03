#!/usr/bin/env python3
"""
push.py - Manage planned workouts on Intervals.icu calendar.

Part of Section 11 (https://github.com/CrankAddict/section-11).
For agentic AI platforms with code execution or GitHub Actions.

Subcommands:
  push           Add workouts to calendar (default if no subcommand given)
  list           Show planned workouts for a date range
  move           Move a workout to a different date
  delete         Remove a workout from the calendar
  set-threshold  Update sport-specific thresholds (FTP, LTHR, etc.)
  annotate       Add notes to completed activities or planned workouts

Write operations default to PREVIEW mode.
Add --confirm to execute. Agents: always preview first, show the
athlete, then --confirm only after approval.

Usage:
  python push.py push --json week.json                # preview
  python push.py push --json week.json --confirm      # execute
  python push.py list                                 # this week
  python push.py list --newest +13                    # next two weeks
  python push.py move --event-id 123 --date 2026-03-06 --confirm
  python push.py delete --event-id 123 --confirm
  python push.py set-threshold --sport Ride --ftp 295 --confirm
  python push.py annotate --activity-id abc --message "Knee pain" --confirm
  python push.py annotate --activity-id abc --message "Knee pain" --chat --confirm
  python push.py annotate --event-id 123 --message "Focus cadence" --confirm
  python push.py --json week.json --confirm           # backward compat

Credentials (checked in order):
  1. CLI args: --athlete-id, --api-key
  2. .sync_config.json (same file sync.py uses)
  3. Environment: ATHLETE_ID, INTERVALS_KEY

Output: JSON to stdout for agent parsing.
"""

import argparse
import base64
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class IntervalsPush:
    """Manage planned workouts on Intervals.icu calendar."""

    BASE_URL = "https://intervals.icu/api/v1"
    VERSION = "0.3"

    VALID_TYPES = {
        "Ride", "VirtualRide", "MountainBikeRide", "GravelRide", "EBikeRide",
        "Run", "VirtualRun", "TrailRun",
        "Swim",
        "NordicSki", "VirtualSki",
        "Rowing",
        "WeightTraining",
        "Walk", "Hike",
        "Workout", "Other",
    }

    VALID_CATEGORIES = {"WORKOUT", "RACE_A", "RACE_B", "RACE_C", "NOTE"}

    # Maps sync.py sport families to Intervals.icu activity types for API calls.
    # Agents see families in JSON ("cycling"); API needs types ("Ride").
    FAMILY_TO_TYPE = {
        "cycling": "Ride",
        "run": "Run",
        "swim": "Swim",
        "walk": "Walk",
        "ski": "NordicSki",
        "rowing": "Rowing",
    }

    # Valid threshold fields for set-threshold
    THRESHOLD_FIELDS = {"ftp", "indoor_ftp", "lthr", "max_hr", "threshold_pace"}

    def __init__(self, athlete_id: str, api_key: str):
        if not athlete_id or not api_key:
            raise ValueError("athlete_id and api_key are required")
        self.athlete_id = athlete_id
        self.auth = base64.b64encode(f"API_KEY:{api_key}".encode()).decode()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Basic {self.auth}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _url(self, endpoint: str) -> str:
        return f"{self.BASE_URL}/athlete/{self.athlete_id}/{endpoint}"

    def _handle_error(self, e: Exception) -> str:
        """Extract readable error from requests exception."""
        error_msg = str(e)
        if hasattr(e, "response") and e.response is not None:
            try:
                detail = e.response.json()
                error_msg = f"{e.response.status_code}: {detail}"
            except Exception:
                error_msg = f"{e.response.status_code}: {e.response.text[:200]}"
        return error_msg

    def _get(self, endpoint: str, params: dict = None) -> any:
        """GET from Intervals.icu API."""
        import requests
        response = requests.get(self._url(endpoint), headers=self._headers(), params=params)
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint: str, payload) -> any:
        """POST to Intervals.icu API."""
        import requests
        response = requests.post(self._url(endpoint), headers=self._headers(), json=payload)
        response.raise_for_status()
        return response.json()

    def _put(self, endpoint: str, payload: dict) -> any:
        """PUT to Intervals.icu API."""
        import requests
        response = requests.put(self._url(endpoint), headers=self._headers(), json=payload)
        response.raise_for_status()
        return response.json()

    def _delete(self, endpoint: str) -> bool:
        """DELETE on Intervals.icu API. Returns True on success."""
        import requests
        response = requests.delete(self._url(endpoint), headers=self._headers())
        response.raise_for_status()
        return True

    # ── Validation ──────────────────────────────────────────────────

    def validate_workout(self, workout: dict) -> Tuple[bool, Optional[str]]:
        """Validate a workout dict. Returns (True, None) or (False, error)."""
        name = workout.get("name")
        if not name or not name.strip():
            return False, "name is required"

        date = workout.get("date")
        if not date:
            return False, "date is required (YYYY-MM-DD)"

        try:
            workout_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            return False, f"invalid date format: {date} (expected YYYY-MM-DD)"

        today = datetime.now().date()
        if workout_date < today:
            return False, f"date {date} is in the past - planned workouts must be today or future"

        wtype = workout.get("type", "Ride")
        if wtype not in self.VALID_TYPES:
            return False, f"invalid type: {wtype} - valid: {sorted(self.VALID_TYPES)}"

        category = workout.get("category", "WORKOUT")
        if category not in self.VALID_CATEGORIES:
            return False, f"invalid category: {category} - valid: {sorted(self.VALID_CATEGORIES)}"

        target = workout.get("target")
        if target is not None and target not in {"POWER", "HR", "PACE"}:
            return False, f"invalid target: {target} - valid: POWER, HR, PACE"

        duration = workout.get("duration_minutes")
        if duration is not None:
            if not isinstance(duration, (int, float)) or duration <= 0:
                return False, f"duration_minutes must be positive, got: {duration}"
            if duration > 720:
                return False, f"duration_minutes {duration} exceeds 12h - likely an error"

        tss = workout.get("tss")
        if tss is not None:
            if not isinstance(tss, (int, float)) or tss < 0:
                return False, f"tss must be non-negative, got: {tss}"
            if tss > 500:
                return False, f"tss {tss} exceeds 500 - likely an error"

        desc = workout.get("description", "")
        if desc:
            valid, desc_error = self._validate_description(desc)
            if not valid:
                return False, f"description syntax: {desc_error}"

        return True, None

    def _validate_description(self, description: str) -> Tuple[bool, Optional[str]]:
        """Basic validation of Intervals.icu workout description syntax."""
        lines = description.strip().split("\n")
        has_step = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("-"):
                has_step = True
                if not stripped[1:].strip():
                    return False, "empty step line (dash with no content)"
            elif re.match(r'^(\d+x|.+\s+\d+x)\s*$', stripped, re.IGNORECASE):
                continue
            else:
                continue
        if not has_step:
            return False, "no step lines found (steps must start with -)"
        return True, None

    def _build_event(self, workout: dict) -> dict:
        """Convert a validated workout dict to an Intervals.icu event payload."""
        event = {
            "category": workout.get("category", "WORKOUT"),
            "start_date_local": f"{workout['date']}T00:00:00",
            "name": workout["name"],
            "type": workout.get("type", "Ride"),
        }

        description = workout.get("description", "")
        if description:
            event["description"] = description
            event["workout_doc"] = {}

        target = workout.get("target")
        if target:
            event["target"] = target

        duration = workout.get("duration_minutes")
        if duration:
            event["moving_time"] = int(duration * 60)

        tss = workout.get("tss")
        if tss is not None:
            event["icu_training_load"] = tss

        color = workout.get("color")
        if color:
            event["color"] = color

        indoor = workout.get("indoor")
        if indoor is not None:
            event["indoor"] = indoor

        external_id = workout.get("external_id")
        if external_id:
            event["external_id"] = str(external_id)

        return event

    @staticmethod
    def _summarize_event(evt: dict) -> dict:
        """Extract compact summary from an Intervals.icu event."""
        moving_time = evt.get("moving_time")
        duration = round(moving_time / 60) if moving_time else None
        return {
            "id": evt.get("id"),
            "name": evt.get("name"),
            "date": (evt.get("start_date_local") or "")[:10],
            "type": evt.get("type"),
            "category": evt.get("category"),
            "duration_minutes": duration,
            "tss": evt.get("icu_training_load"),
        }

    # ── Push (create) ──────────────────────────────────────────────

    def push_workout(self, workout: dict) -> dict:
        """Validate and push a single workout."""
        return self.push_workouts([workout])

    def push_workouts(self, workouts: list) -> dict:
        """Validate and push multiple workouts. Uses bulk endpoint with upsert=true."""
        errors = []
        for i, w in enumerate(workouts):
            valid, error = self.validate_workout(w)
            if not valid:
                label = w.get("name", f"workout[{i}]")
                errors.append(f"{label}: {error}")
        if errors:
            return {"success": False, "error": "; ".join(errors)}

        events = [self._build_event(w) for w in workouts]

        try:
            response = self._post("events/bulk?upsert=true", events)
            results = []
            if isinstance(response, list):
                results = [self._summarize_event(evt) for evt in response]
            return {"success": True, "count": len(results), "events": results}
        except Exception as e:
            return {"success": False, "error": self._handle_error(e)}

    def preview_push(self, workouts: list) -> dict:
        """Validate workouts and return preview without writing."""
        errors = []
        for i, w in enumerate(workouts):
            valid, error = self.validate_workout(w)
            if not valid:
                label = w.get("name", f"workout[{i}]")
                errors.append(f"{label}: {error}")
        if errors:
            return {"success": False, "mode": "preview", "error": "; ".join(errors)}

        events = [self._build_event(w) for w in workouts]
        summary = []
        for w in workouts:
            summary.append({
                "name": w.get("name"),
                "date": w.get("date"),
                "type": w.get("type", "Ride"),
                "duration_minutes": w.get("duration_minutes"),
                "tss": w.get("tss"),
            })

        return {
            "success": True,
            "mode": "preview",
            "count": len(summary),
            "summary": summary,
            "message": "Preview only - add --confirm to write to calendar",
        }

    # ── List (read) ────────────────────────────────────────────────

    def list_events(self, oldest: str = None, newest: str = None, category: str = None) -> dict:
        """
        List planned events in a date range.

        Defaults: oldest=today, newest=today+6 (rolling 7 days).
        """
        today = datetime.now().date()
        if oldest is None:
            oldest = today.isoformat()
        if newest is None:
            newest = (today + timedelta(days=6)).isoformat()

        params = {"oldest": oldest, "newest": newest}
        if category:
            params["category"] = category

        try:
            response = self._get("events", params=params)
            events = []
            if isinstance(response, list):
                events = [self._summarize_event(evt) for evt in response]
            return {
                "success": True,
                "oldest": oldest,
                "newest": newest,
                "count": len(events),
                "events": events,
            }
        except Exception as e:
            return {"success": False, "error": self._handle_error(e)}

    # ── Move (update date) ─────────────────────────────────────────

    def get_event(self, event_id: int) -> dict:
        """Fetch a single event by ID. Returns the raw event dict or error."""
        try:
            response = self._get(f"events/{event_id}")
            return {"success": True, "event": response}
        except Exception as e:
            return {"success": False, "error": self._handle_error(e)}

    def update_event(self, event_id: int, updates: dict) -> dict:
        """Partial update of an event. Returns updated event summary."""
        try:
            response = self._put(f"events/{event_id}", updates)
            return {"success": True, "event": self._summarize_event(response)}
        except Exception as e:
            return {"success": False, "error": self._handle_error(e)}

    def preview_move(self, event_id: int, new_date: str) -> dict:
        """Preview moving a workout to a new date."""
        # Validate new date
        try:
            target_date = datetime.strptime(new_date, "%Y-%m-%d").date()
        except ValueError:
            return {"success": False, "mode": "preview", "error": f"invalid date: {new_date}"}

        today = datetime.now().date()
        if target_date < today:
            return {"success": False, "mode": "preview", "error": f"date {new_date} is in the past"}

        # Fetch current event to show what's moving
        current = self.get_event(event_id)
        if not current["success"]:
            return {"success": False, "mode": "preview", "error": current["error"]}

        evt = current["event"]
        old_date = (evt.get("start_date_local") or "")[:10]

        return {
            "success": True,
            "mode": "preview",
            "event_id": event_id,
            "name": evt.get("name"),
            "from_date": old_date,
            "to_date": new_date,
            "message": "Preview only - add --confirm to move this workout",
        }

    def move_event(self, event_id: int, new_date: str) -> dict:
        """Move a workout to a new date."""
        # Validate
        try:
            target_date = datetime.strptime(new_date, "%Y-%m-%d").date()
        except ValueError:
            return {"success": False, "error": f"invalid date: {new_date}"}

        today = datetime.now().date()
        if target_date < today:
            return {"success": False, "error": f"date {new_date} is in the past"}

        return self.update_event(event_id, {
            "start_date_local": f"{new_date}T00:00:00",
        })

    # ── Delete ─────────────────────────────────────────────────────

    def preview_delete(self, event_id: int) -> dict:
        """Preview deleting a workout."""
        current = self.get_event(event_id)
        if not current["success"]:
            return {"success": False, "mode": "preview", "error": current["error"]}

        evt = current["event"]
        return {
            "success": True,
            "mode": "preview",
            "event_id": event_id,
            "name": evt.get("name"),
            "date": (evt.get("start_date_local") or "")[:10],
            "type": evt.get("type"),
            "message": "Preview only - add --confirm to delete this workout",
        }

    def delete_event(self, event_id: int) -> dict:
        """Delete a single event."""
        try:
            self._delete(f"events/{event_id}")
            return {"success": True, "deleted": event_id}
        except Exception as e:
            return {"success": False, "error": self._handle_error(e)}

    # ── Raw URL helpers (for non-athlete endpoints) ────────────────

    def _get_raw(self, url: str) -> any:
        """GET from an absolute Intervals.icu URL."""
        import requests
        response = requests.get(url, headers=self._headers())
        response.raise_for_status()
        return response.json()

    def _post_raw(self, url: str, payload) -> any:
        """POST to an absolute Intervals.icu URL."""
        import requests
        response = requests.post(url, headers=self._headers(), json=payload)
        response.raise_for_status()
        return response.json()

    def _put_raw(self, url: str, payload: dict) -> any:
        """PUT to an absolute Intervals.icu URL."""
        import requests
        response = requests.put(url, headers=self._headers(), json=payload)
        response.raise_for_status()
        return response.json()

    # ── Set threshold ──────────────────────────────────────────────

    def _resolve_sport_type(self, sport: str) -> str:
        """Resolve a sport family name or activity type to the API type."""
        # If it's already a valid activity type, use it
        if sport in self.VALID_TYPES:
            return sport
        # Try family mapping (case-insensitive)
        mapped = self.FAMILY_TO_TYPE.get(sport.lower())
        if mapped:
            return mapped
        return sport  # pass through, let API reject if invalid

    def get_sport_settings(self, sport_type: str) -> dict:
        """Fetch current sport settings for a sport type."""
        try:
            response = self._get(f"sport-settings/{sport_type}")
            return {"success": True, "settings": response}
        except Exception as e:
            return {"success": False, "error": self._handle_error(e)}

    def preview_set_threshold(self, sport: str, updates: dict) -> dict:
        """Preview threshold update: shows current → new values."""
        sport_type = self._resolve_sport_type(sport)

        # Validate fields
        invalid = set(updates.keys()) - self.THRESHOLD_FIELDS
        if invalid:
            return {
                "success": False, "mode": "preview",
                "error": f"invalid threshold fields: {sorted(invalid)} - valid: {sorted(self.THRESHOLD_FIELDS)}",
            }
        if not updates:
            return {"success": False, "mode": "preview", "error": "no threshold fields provided"}

        # Fetch current values
        current = self.get_sport_settings(sport_type)
        if not current["success"]:
            return {"success": False, "mode": "preview", "error": current["error"]}

        settings = current["settings"]
        changes = {}
        for field, new_val in updates.items():
            old_val = settings.get(field)
            changes[field] = {"from": old_val, "to": new_val}

        return {
            "success": True,
            "mode": "preview",
            "sport": sport_type,
            "changes": changes,
            "message": "Preview only - add --confirm to update thresholds",
        }

    def set_threshold(self, sport: str, updates: dict) -> dict:
        """Update sport-specific thresholds."""
        sport_type = self._resolve_sport_type(sport)

        invalid = set(updates.keys()) - self.THRESHOLD_FIELDS
        if invalid:
            return {"success": False, "error": f"invalid fields: {sorted(invalid)}"}
        if not updates:
            return {"success": False, "error": "no threshold fields provided"}

        try:
            response = self._put(f"sport-settings/{sport_type}", updates)
            # Return the updated values for confirmation
            result = {}
            for field in updates:
                result[field] = response.get(field)
            return {"success": True, "sport": sport_type, "updated": result}
        except Exception as e:
            return {"success": False, "error": self._handle_error(e)}

    # ── Annotate ───────────────────────────────────────────────────

    def get_activity_messages(self, activity_id: str) -> dict:
        """Fetch messages/notes for a completed activity."""
        try:
            url = f"{self.BASE_URL}/activity/{activity_id}/messages"
            response = self._get_raw(url)
            messages = []
            if isinstance(response, list):
                messages = [{"text": m.get("content", m.get("text", "")), "created": m.get("created")} for m in response]
            return {"success": True, "messages": messages}
        except Exception as e:
            return {"success": False, "error": self._handle_error(e)}

    def get_activity(self, activity_id: str) -> dict:
        """Fetch a completed activity by ID."""
        try:
            url = f"{self.BASE_URL}/activity/{activity_id}"
            response = self._get_raw(url)
            return {"success": True, "activity": response}
        except Exception as e:
            return {"success": False, "error": self._handle_error(e)}

    def preview_annotate_activity(self, activity_id: str, message: str, chat: bool = False) -> dict:
        """Preview adding a note to a completed activity."""
        if not message or not message.strip():
            return {"success": False, "mode": "preview", "error": "message is required"}

        result = {
            "success": True,
            "mode": "preview",
            "target": "activity_chat" if chat else "activity_description",
            "activity_id": activity_id,
            "message": message.strip(),
            "note": "Preview only - add --confirm to post this note",
        }

        if not chat:
            # Fetch activity to show current description context
            current = self.get_activity(activity_id)
            if current["success"]:
                act = current["activity"]
                result["name"] = act.get("name")
                result["date"] = (act.get("start_date_local") or "")[:10]

        return result

    def annotate_activity(self, activity_id: str, message: str, chat: bool = False) -> dict:
        """Add a note to a completed activity. Default: description. --chat: messages endpoint."""
        if not message or not message.strip():
            return {"success": False, "error": "message is required"}

        if chat:
            return self._annotate_activity_chat(activity_id, message)
        return self._annotate_activity_description(activity_id, message)

    def _annotate_activity_chat(self, activity_id: str, message: str) -> dict:
        """Post a note to a completed activity's messages/chat."""
        try:
            url = f"{self.BASE_URL}/activity/{activity_id}/messages"
            self._post_raw(url, {"content": message.strip()})
            return {
                "success": True,
                "target": "activity_chat",
                "activity_id": activity_id,
                "message": message.strip(),
            }
        except Exception as e:
            return {"success": False, "error": self._handle_error(e)}

    def _annotate_activity_description(self, activity_id: str, message: str) -> dict:
        """Prepend a NOTE: line to a completed activity's description."""
        try:
            current = self.get_activity(activity_id)
            if not current["success"]:
                return {"success": False, "error": current["error"]}

            act = current["activity"]
            existing_desc = act.get("description") or ""
            note_line = f"NOTE: {message.strip()}"

            if existing_desc:
                new_desc = f"{note_line}\n\n{existing_desc}"
            else:
                new_desc = note_line

            url = f"{self.BASE_URL}/activity/{activity_id}"
            self._put_raw(url, {"description": new_desc})
            return {
                "success": True,
                "target": "activity_description",
                "activity_id": activity_id,
                "message": message.strip(),
            }
        except Exception as e:
            return {"success": False, "error": self._handle_error(e)}

    def preview_annotate_event(self, event_id: int, message: str) -> dict:
        """Preview adding a NOTE: line to a planned workout's description."""
        if not message or not message.strip():
            return {"success": False, "mode": "preview", "error": "message is required"}

        # Fetch current event to show context
        current = self.get_event(event_id)
        if not current["success"]:
            return {"success": False, "mode": "preview", "error": current["error"]}

        evt = current["event"]
        return {
            "success": True,
            "mode": "preview",
            "target": "event",
            "event_id": event_id,
            "name": evt.get("name"),
            "date": (evt.get("start_date_local") or "")[:10],
            "message": message.strip(),
            "note": "Preview only - add --confirm to add this note",
        }

    def annotate_event(self, event_id: int, message: str) -> dict:
        """Add a NOTE: line to a planned workout's description."""
        if not message or not message.strip():
            return {"success": False, "error": "message is required"}

        # Fetch current event
        current = self.get_event(event_id)
        if not current["success"]:
            return {"success": False, "error": current["error"]}

        evt = current["event"]
        existing_desc = evt.get("description") or ""
        note_line = f"NOTE: {message.strip()}"

        # Prepend NOTE: line to description
        if existing_desc:
            new_desc = f"{note_line}\n\n{existing_desc}"
        else:
            new_desc = note_line

        return self.update_event(event_id, {"description": new_desc})


# ── CLI ────────────────────────────────────────────────────────────

def _load_credentials(args) -> Tuple[Optional[str], Optional[str]]:
    """Load credentials from CLI args, config file, or environment."""
    config = {}
    if os.path.exists(".sync_config.json"):
        with open(".sync_config.json") as f:
            config = json.load(f)

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


def _resolve_date(value: str) -> str:
    """Resolve a date string. Supports YYYY-MM-DD and +N (days from today)."""
    if value.startswith("+"):
        days = int(value[1:])
        return (datetime.now().date() + timedelta(days=days)).isoformat()
    return value


def _output(result: dict):
    """Print result JSON and exit with appropriate code."""
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("success") else 1)


def _build_workouts_from_args(args) -> list:
    """Build workout list from CLI args or --json file."""
    if args.json:
        try:
            with open(args.json) as f:
                data = json.load(f)
            return data if isinstance(data, list) else [data]
        except Exception as e:
            _output({"success": False, "error": f"Failed to read {args.json}: {e}"})

    if not args.name or not args.date:
        _output({
            "success": False,
            "error": "--name and --date are required (or use --json for file input)",
        })

    description = args.description.replace("\\n", "\n") if args.description else ""

    workout = {
        "name": args.name,
        "date": args.date,
        "type": args.type,
        "description": description,
        "category": args.category,
    }
    if args.duration:
        workout["duration_minutes"] = args.duration
    if args.tss is not None:
        workout["tss"] = args.tss
    if args.target:
        workout["target"] = args.target
    if args.indoor:
        workout["indoor"] = True

    return [workout]


def _cmd_push(args, pusher: IntervalsPush):
    """Handle push subcommand."""
    workouts = _build_workouts_from_args(args)

    if not args.confirm:
        _output(pusher.preview_push(workouts))
    else:
        _output(pusher.push_workouts(workouts))


def _cmd_list(args, pusher: IntervalsPush):
    """Handle list subcommand."""
    oldest = _resolve_date(args.oldest) if args.oldest else None
    newest = _resolve_date(args.newest) if args.newest else None
    _output(pusher.list_events(oldest=oldest, newest=newest, category=args.category))


def _cmd_move(args, pusher: IntervalsPush):
    """Handle move subcommand."""
    if not args.confirm:
        _output(pusher.preview_move(args.event_id, args.date))
    else:
        _output(pusher.move_event(args.event_id, args.date))


def _cmd_delete(args, pusher: IntervalsPush):
    """Handle delete subcommand."""
    if not args.confirm:
        _output(pusher.preview_delete(args.event_id))
    else:
        _output(pusher.delete_event(args.event_id))


def _cmd_set_threshold(args, pusher: IntervalsPush):
    """Handle set-threshold subcommand."""
    updates = {}
    if args.ftp is not None:
        updates["ftp"] = args.ftp
    if args.indoor_ftp is not None:
        updates["indoor_ftp"] = args.indoor_ftp
    if args.lthr is not None:
        updates["lthr"] = args.lthr
    if args.max_hr is not None:
        updates["max_hr"] = args.max_hr
    if args.threshold_pace is not None:
        updates["threshold_pace"] = args.threshold_pace

    if not updates:
        _output({"success": False, "error": "provide at least one threshold field (--ftp, --indoor-ftp, --lthr, --max-hr, --threshold-pace)"})

    if not args.confirm:
        _output(pusher.preview_set_threshold(args.sport, updates))
    else:
        _output(pusher.set_threshold(args.sport, updates))


def _cmd_annotate(args, pusher: IntervalsPush):
    """Handle annotate subcommand."""
    if args.activity_id and args.event_id:
        _output({"success": False, "error": "provide --activity-id OR --event-id, not both"})
    if not args.activity_id and not args.event_id:
        _output({"success": False, "error": "provide --activity-id (completed) or --event-id (planned)"})

    if args.activity_id:
        chat = getattr(args, "chat", False)
        if not args.confirm:
            _output(pusher.preview_annotate_activity(args.activity_id, args.message, chat=chat))
        else:
            _output(pusher.annotate_activity(args.activity_id, args.message, chat=chat))
    else:
        if not args.confirm:
            _output(pusher.preview_annotate_event(args.event_id, args.message))
        else:
            _output(pusher.annotate_event(args.event_id, args.message))


def main():
    parser = argparse.ArgumentParser(
        description="Manage planned workouts on Intervals.icu calendar"
    )
    parser.add_argument("--athlete-id", help="Intervals.icu athlete ID")
    parser.add_argument("--api-key", help="Intervals.icu API key")

    subparsers = parser.add_subparsers(dest="command")

    # ── push ──
    push_parser = subparsers.add_parser("push", help="Add workouts to calendar")
    push_parser.add_argument("--name", help="Workout name (required unless --json)")
    push_parser.add_argument("--date", help="Date YYYY-MM-DD (required unless --json)")
    push_parser.add_argument("--type", default="Ride", help="Activity type (default: Ride)")
    push_parser.add_argument("--description", default="", help="Workout description")
    push_parser.add_argument("--duration", type=float, help="Planned duration in minutes")
    push_parser.add_argument("--tss", type=float, help="Planned TSS")
    push_parser.add_argument("--target", choices=["POWER", "HR", "PACE"], help="Target mode")
    push_parser.add_argument("--category", default="WORKOUT", help="Event category")
    push_parser.add_argument("--indoor", action="store_true", help="Mark as indoor")
    push_parser.add_argument("--json", type=str, help="JSON file with workout(s)")
    push_parser.add_argument("--confirm", action="store_true", help="Execute write (default is preview)")

    # ── list ──
    list_parser = subparsers.add_parser("list", help="Show planned workouts")
    list_parser.add_argument("--oldest", help="Start date YYYY-MM-DD or +N days (default: today)")
    list_parser.add_argument("--newest", help="End date YYYY-MM-DD or +N days (default: +6)")
    list_parser.add_argument("--category", help="Filter by category (e.g. WORKOUT, RACE_A)")

    # ── move ──
    move_parser = subparsers.add_parser("move", help="Move a workout to a different date")
    move_parser.add_argument("--event-id", type=int, required=True, help="Event ID to move")
    move_parser.add_argument("--date", required=True, help="New date YYYY-MM-DD")
    move_parser.add_argument("--confirm", action="store_true", help="Execute write (default is preview)")

    # ── delete ──
    delete_parser = subparsers.add_parser("delete", help="Remove a workout")
    delete_parser.add_argument("--event-id", type=int, required=True, help="Event ID to delete")
    delete_parser.add_argument("--confirm", action="store_true", help="Execute write (default is preview)")

    # ── set-threshold ──
    thresh_parser = subparsers.add_parser("set-threshold", help="Update sport thresholds")
    thresh_parser.add_argument("--sport", required=True, help="Sport family (cycling, run, swim) or activity type (Ride, Run)")
    thresh_parser.add_argument("--ftp", type=int, help="Functional Threshold Power")
    thresh_parser.add_argument("--indoor-ftp", type=int, dest="indoor_ftp", help="Indoor FTP")
    thresh_parser.add_argument("--lthr", type=int, help="Lactate Threshold Heart Rate")
    thresh_parser.add_argument("--max-hr", type=int, dest="max_hr", help="Maximum Heart Rate")
    thresh_parser.add_argument("--threshold-pace", type=float, dest="threshold_pace", help="Threshold pace")
    thresh_parser.add_argument("--confirm", action="store_true", help="Execute write (default is preview)")

    # ── annotate ──
    annotate_parser = subparsers.add_parser("annotate", help="Add notes to activities or planned workouts")
    annotate_parser.add_argument("--activity-id", dest="activity_id", help="Completed activity ID (from sync.py output)")
    annotate_parser.add_argument("--event-id", type=int, dest="event_id", help="Planned workout event ID")
    annotate_parser.add_argument("--message", required=True, help="Note text to add")
    annotate_parser.add_argument("--chat", action="store_true", help="Post to activity chat/messages instead of description (activity only)")
    annotate_parser.add_argument("--confirm", action="store_true", help="Execute write (default is preview)")

    # Backward compatibility: if no subcommand in argv, default to push.
    # Must insert 'push' at the right position (after top-level flags like
    # --athlete-id/--api-key, before subcommand-specific flags like --json).
    known_commands = {"push", "list", "move", "delete", "set-threshold", "annotate"}
    # Top-level flags that consume a value
    top_level_value_flags = {"--athlete-id", "--api-key"}

    argv = sys.argv[1:]
    has_subcommand = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in top_level_value_flags:
            i += 2  # skip flag + value
        elif arg in known_commands:
            has_subcommand = True
            break
        elif arg in ("-h", "--help"):
            break  # let argparse handle help naturally
        else:
            break

    if not has_subcommand and not any(a in ("-h", "--help") for a in argv):
        sys.argv.insert(1 + i, "push")

    args = parser.parse_args()

    # Load credentials
    athlete_id, api_key = _load_credentials(args)
    if not athlete_id or not api_key:
        _output({
            "success": False,
            "error": "Missing credentials. Provide via --athlete-id/--api-key, .sync_config.json, or env vars ATHLETE_ID/INTERVALS_KEY",
        })

    pusher = IntervalsPush(athlete_id, api_key)

    if args.command == "push":
        _cmd_push(args, pusher)
    elif args.command == "list":
        _cmd_list(args, pusher)
    elif args.command == "move":
        _cmd_move(args, pusher)
    elif args.command == "delete":
        _cmd_delete(args, pusher)
    elif args.command == "set-threshold":
        _cmd_set_threshold(args, pusher)
    elif args.command == "annotate":
        _cmd_annotate(args, pusher)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
