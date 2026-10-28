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
import math
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


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
                "interpreter running push.py. Install it with "
                "`pip install requests`, or run push.py from the same "
                "venv/environment as sync.py."
            )
        _requests = requests
    return _requests


class WriteStatusError(Exception):
    """
    A write returned a status that is neither an acceptance nor a definitive refusal.

    Carries the numeric status so the classifier never has to read formatted error
    text to decide what happened.
    """

    def __init__(self, status, detail):
        super().__init__(detail)
        self.status = status
        self.detail = detail


class RequestBudgetRefused(Exception):
    """No request was sent; preserve prior data and attempt state."""


# Shared request controller. Keep this block identical in both standalone scripts.
class RequestBudget:
    PROVIDER_DAILY_LIMIT = 8000
    EXTERNAL_RESERVE = 1000
    SYNC_DAILY_LIMIT = 7000
    WINDOW_SECONDS = 900
    WINDOW_LIMIT = 200
    RUN_LIMIT = 128
    SEND_INTERVAL = 0.5
    CORE_PER_RUN = 4
    UNKNOWN_RUN_LIMIT = 3
    STATE_ENV = "SECTION11_STATE_DIR"
    SCOPE = "local_data_folder_key_athlete"

    @staticmethod
    def fingerprint(athlete_id, api_key):
        import hashlib
        identity = json.dumps([str(athlete_id).strip(), api_key.strip()],
                              separators=(",", ":")).encode()
        return hashlib.sha256(identity).hexdigest()[:32]

    @classmethod
    def state_base(cls, data_dir, environ=None):
        env = os.environ if environ is None else environ
        if data_dir is None:
            raise OSError("data folder unavailable")
        if env.get(cls.STATE_ENV):
            return Path(env[cls.STATE_ENV]).expanduser() / "request-budget"
        return Path(data_dir) / "state" / "request-budget"

    def __init__(self, data_dir, caller, error_type, identity, clock=None, sleep=None, jitter=None):
        from datetime import timezone as utc_timezone
        import random
        self.utc = utc_timezone.utc
        self.root = None
        self.data_dir = Path(data_dir).resolve() if data_dir is not None else None
        # Even an explicit shared base must not coordinate different data folders.
        import hashlib
        self.identity = hashlib.sha256(json.dumps(
            [str(self.data_dir), identity], separators=(",", ":")).encode()).hexdigest()[:32]
        self.caller, self.error_type = caller, error_type
        self.clock = clock or time.time
        self.sleep = sleep or time.sleep
        self.jitter = jitter or random.random
        self.count = 0
        self.core_count = 0
        self.degraded = False
        self._last_local_send = None
        self._local_hold = 0
        self.stopped = False
        self.refused = False
        self.refusals = 0
        self.started = False
        self._handle = None
        self._reserved = False
        self._write_sent = False
        try:
            self.root = self.state_base(self.data_dir).resolve() / self.identity
        except OSError:
            self._degrade()

    def _degrade(self):
        if not self.degraded:
            import sys
            print("Warning: private request state unavailable; capacity unknown; "
                  "at most 3 core reads, no optional reads or writes this run.",
                  file=sys.stderr)
        self.degraded = True

    def _load_storage(self):
        if self.degraded:
            return
        try:
            self._load()
        except self.error_type:
            raise
        except OSError:
            self._degrade()

    def _save_storage(self):
        try:
            self._save()
        except OSError:
            self._degrade()

    def _refuse(self, reason):
        self.refused = True
        self.refusals += 1
        raise self.error_type("request budget: " + reason)

    def _atomic(self, path, value):
        import tempfile
        fd, name = tempfile.mkstemp(prefix=".state-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                json.dump(value, out, separators=(",", ":"), allow_nan=False)
                out.flush()
                os.fsync(out.fileno())
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def _lock(self):
        from contextlib import contextmanager

        @contextmanager
        def locked():
            if self.degraded:
                yield
                return
            if self._handle is not None:
                yield
                return
            handle = None
            try:
                self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
                if os.name != "nt":
                    os.chmod(self.root, 0o700)
                    os.chmod(self.root.parent, 0o700)
                    os.chmod(self.root.parent.parent, 0o700)
                fd = os.open(self.root / "ledger.lock", os.O_RDWR | os.O_CREAT, 0o600)
                handle = os.fdopen(fd, "a+b")
                if os.name != "nt":
                    os.fchmod(handle.fileno(), 0o600)
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0, 2)
                    if handle.tell() == 0:
                        handle.write(b"0")
                        handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                if handle is not None:
                    handle.close()
                self._degrade()
                yield
                return
            self._handle = handle
            try:
                yield
            finally:
                self._handle = None
                handle.close()
        return locked()

    def _day(self, stamp):
        return datetime.fromtimestamp(stamp, self.utc).strftime("%Y-%m-%d")

    @staticmethod
    def _number(value):
        return type(value) in (float, int) and math.isfinite(value) and value >= 0

    def _load(self):
        now = self.clock()
        if not self._number(now):
            self._refuse("invalid clock")
        anchor_path = self.root / "ledger.anchor"
        state_path = self.root / "ledger.json"
        try:
            anchor = json.loads(anchor_path.read_text())
            if not self._number(anchor["high_water"]) or not self._number(anchor.get("hold_until", 0)):
                raise ValueError()
            high = max(now, anchor["high_water"])
        except FileNotFoundError:
            if state_path.exists():
                self._refuse("missing recovery anchor")
            high = now
            anchor = None
        except (ValueError, KeyError, TypeError):
            self._refuse("invalid recovery anchor")
        day = self._day(high)
        try:
            state = json.loads(state_path.read_text())
            def require(valid):
                if not valid:
                    raise ValueError("invalid private state")
            require(state["version"] == 1 and isinstance(state["days"], dict))
            require(self._number(state["high_water"]) and self._number(state["hold_until"]))
            require(type(state["backoff"]) is int and 0 <= state["backoff"] <= 5)
            require(isinstance(state["window"], list))
            require(all(self._number(t) for t in state["window"]))
            require(self._number(state["last_send"]))
            require(isinstance(state["runs"], list) and all(self._number(t) for t in state["runs"]))
            for key, row in state["days"].items():
                require(self._day(datetime.strptime(key, "%Y-%m-%d").replace(tzinfo=self.utc).timestamp()) == key)
                require(isinstance(row, dict))
                for caller in ("sync", "push"):
                    require(isinstance(row[caller], dict))
                    require(all(type(n) is int and n >= 0 for n in row[caller].values()))
            high = max(high, state["high_water"])
            day = self._day(high)
        except (FileNotFoundError, ValueError, KeyError, TypeError):
            # A durable anchor distinguishes first use from lost/corrupt state.
            # Exhaust the anchored day; repeated restarts cannot replenish it.
            state = {"version": 1, "days": {}, "window": [], "runs": [],
                     "high_water": high, "hold_until": high if anchor else 0,
                     "last_send": high if anchor else 0, "backoff": 0,
                     "last_run": {}}
            if anchor:
                anchored_day = self._day(anchor["high_water"])
                state["days"][anchored_day] = {
                    "sync": {"recovery_unknown": self.SYNC_DAILY_LIMIT},
                    "push": {"recovery_unknown": self.EXTERNAL_RESERVE}}
                state["hold_until"] = max(anchor["high_water"] + self.WINDOW_SECONDS,
                                          anchor.get("hold_until", 0))
        state["high_water"] = high
        state["window"] = [t for t in state["window"] if t > high - self.WINDOW_SECONDS]
        state["days"].setdefault(day, {"sync": {}, "push": {}})
        # Preserve all daily counts. The only reset is selecting a later UTC day.
        if not self.started:
            if self.caller == "sync":
                state["runs"] = (state["runs"] + [high])[-16:]
            state["last_run"] = {"caller": self.caller, "count": 0, "core": 0, "at": high}
            self.started = True
        self.state, self.now, self.day = state, high, day
        self._save()
        if now < high:
            self._refuse("clock rollback; waiting for the recorded clock")

    def _save(self):
        # Write anchor first: interruption cannot turn a lost state into first use.
        self._atomic(self.root / "ledger.anchor", {"high_water": self.state["high_water"],
                                                 "hold_until": self.state["hold_until"]})
        self._atomic(self.root / "ledger.json", self.state)

    def _effective_allowances(self):
        reported = getattr(self, "state", {}).get("provider_limit", self.PROVIDER_DAILY_LIMIT)
        if type(reported) is not int or reported < 0:
            reported = self.PROVIDER_DAILY_LIMIT
        daily = min(self.PROVIDER_DAILY_LIMIT, reported)
        return daily, min(self.SYNC_DAILY_LIMIT, max(0, daily - self.EXTERNAL_RESERVE))

    def _remaining(self):
        row = self.state["days"][self.day]
        sync = sum(row["sync"].values())
        total = sync + sum(row["push"].values())
        daily, sync_limit = self._effective_allowances()
        return min(daily - total, sync_limit - sync) if self.caller == "sync" else daily - total

    def expected_core(self):
        if hasattr(self, "scheduled_reserve"):
            return self.scheduled_reserve()
        runs = self.state["runs"]
        gaps = [b - a for a, b in zip(runs, runs[1:]) if b > a]
        # Until spacing is observed, use the existing 30-minute hosted cadence.
        spacing = max(60, min(gaps[-8:])) if gaps else 1800
        tomorrow = (datetime.fromtimestamp(self.now, self.utc).replace(
            hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).timestamp()
        future = max(0, math.ceil((tomorrow - self.now) / spacing) - 1)
        current = max(0, self.CORE_PER_RUN - self.core_count)
        return future * self.CORE_PER_RUN + current

    def _admit(self, priority, needed=1, method="get"):
        hold = max(self._local_hold, getattr(self, "state", {}).get("hold_until", 0))
        if self.stopped or self.clock() < hold:
            self._refuse("provider hold active")
        if self.degraded:
            if priority != "core" or method != "get" or self.count + needed > self.UNKNOWN_RUN_LIMIT:
                self._refuse("capacity unknown; conservative core-read allowance only")
            return
        if self.count + needed > self.RUN_LIMIT:
            self._refuse("invocation allowance exhausted")
        if len(self.state["window"]) + needed > self.WINDOW_LIMIT:
            self._refuse("rolling allowance exhausted")
        if self._remaining() < needed:
            self._refuse("daily allowance exhausted")
        if priority == "optional" and self._remaining() < needed + self.expected_core():
            self._refuse("remaining allowance reserved for core reads")

    def reserve_write(self):
        from contextlib import contextmanager

        @contextmanager
        def reserved():
            if self._reserved:
                yield
                return
            with self._lock():
                self._load_storage()
                if self.degraded:
                    self._refuse("capacity unknown; cannot reserve a verified write")
                self._admit("core", 3)
                self._reserved, self._write_sent = True, False
                try:
                    yield
                finally:
                    self._reserved = False
        return reserved()

    def _hold(self, response):
        from email.utils import parsedate_to_datetime
        received = self.clock()
        raw = str(getattr(response, "headers", {}).get("Retry-After", "")).strip()
        delay = None
        if raw.isascii() and raw.isdigit():
            delay = int(raw)
        elif raw:
            try:
                stamp = parsedate_to_datetime(raw)
                if stamp.tzinfo is not None:
                    delay = max(0, stamp.timestamp() - received)
            except (ValueError, TypeError, OverflowError):
                pass
        state = getattr(self, "state", {})
        if delay is None:
            delay = min(900, 60 * 2 ** state.get("backoff", 0) * (1 + self.jitter() * .25))
        self._local_hold = max(self._local_hold, received + delay)
        self.stopped = True
        if not self.degraded:
            self.state["backoff"] = min(5, self.state["backoff"] + 1)
            self.state["high_water"] = max(self.state["high_water"], received)
            self.state["hold_until"] = max(self.state["hold_until"], self._local_hold)
            self._save_storage()

    def private_log(self, line):
        if self.degraded or self.root is None:
            return
        try:
            fd = os.open(self.root / "budget.log", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as out:
                if os.name != "nt":
                    os.fchmod(out.fileno(), 0o600)
                out.write(line + "\n")
        except OSError:
            self._degrade()

    def _provider_headers(self, response):
        if self.degraded:
            return
        headers = getattr(response, "headers", {})
        seen = self.state.setdefault("header_days", {}).setdefault(self._day(self.clock()), [])
        for name in ("X-RateLimit-Limit", "X-RateLimit-Remaining"):
            raw = headers.get(name)
            if raw is None:
                continue
            safe = "".join(c for c in str(raw)[:256] if " " <= c <= "~")
            if name not in seen:
                self.private_log("Provider header " + name + ": " + safe)
                seen.append(name)
            if name == "X-RateLimit-Limit":
                parts = safe.split(",")
                if len(parts) == 2 and all(p.strip().isascii() and p.strip().isdigit() for p in parts):
                    self.state["provider_limit"] = min(
                        self.state.get("provider_limit", self.PROVIDER_DAILY_LIMIT), int(parts[1]))
        self._save_storage()

    def _dirty_write(self, url):
        from urllib.parse import urlsplit
        path = urlsplit(url).path.split("/")
        if path[3:4] == ["activity"] and len(path) > 4:
            groups = ["activities", "messages:" + path[4]]
        elif len(path) > 5 and path[5] == "events":
            groups = ["calendar", "health_events", "wellness"]
        else:
            groups = ["profile", "wellness", "calendar", "aggregate_curves"]
        dirty = self.state.setdefault("dirty", {})
        generation = self.state.get("dirty_generation", 0) + 1
        self.state["dirty_generation"] = generation
        for group in groups:
            dirty[group] = generation
        self._save_storage()
        if self.degraded:
            self._refuse("dirty generation could not be persisted")

    def request(self, transport, method, url, endpoint_class, priority="optional", **kwargs):
        # No automatic redirects: a second send must never escape admission.
        kwargs["allow_redirects"] = False
        with self._lock():
            self._load_storage()
            needed = 1
            if self._reserved and not self._write_sent:
                needed = 3 if method == "get" else 2
            if method != "get" and not self._reserved:
                self._refuse("write has no pre-read/write/verification reservation")
            self._admit(priority, needed, method)
            last = max(self._last_local_send or 0, getattr(self, "state", {}).get("last_send", 0))
            delay = max(0, last + self.SEND_INTERVAL - self.clock())
            if delay:
                self.sleep(delay)
                self._load_storage()
                self._admit(priority, needed, method)
                if self.clock() < last + self.SEND_INTERVAL:
                    self._refuse("pacing clock did not advance")
            if not self.degraded:
                row = self.state["days"][self.day][self.caller]
                row[endpoint_class] = row.get(endpoint_class, 0) + 1
                self.state["window"].append(self.now)
                self.state["last_send"] = self.now
                self.state["last_run"] = {"caller": self.caller, "count": self.count + 1,
                                          "core": self.core_count + int(priority == "core"), "at": self.now}
                self._save_storage()
                if self.degraded:
                    self._admit(priority, needed, method)
            self.count += 1
            self.core_count += int(priority == "core")
            self._last_local_send = self.clock()
            if method != "get":
                self._dirty_write(url)
                self._write_sent = True
            response = getattr(transport, method)(url, **kwargs)
            self._provider_headers(response)
            if response.status_code == 429:
                self._hold(response)
            elif not self.degraded and 200 <= response.status_code < 300:
                self.state["backoff"] = 0
                self._save_storage()
            return response

    def summary(self):
        if self.degraded:
            return (f"Intervals requests: run={self.count}, today=unknown, allowance_left=unknown, "
                    f"hold_until={self._local_hold or 'unknown'}, private_state=unavailable, scope={self.SCOPE}")
        if not self.started:
            return f"Intervals requests: run=0, today=unknown, allowance_left=unknown, hold_until=unknown, scope={self.SCOPE}"
        with self._lock():
            self._load_storage()
            if self.degraded:
                return self.summary()
            total = sum(sum(v.values()) for v in self.state["days"][self.day].values())
            hold = self.state["hold_until"] if self.state["hold_until"] > self.now else None
            return (f"Intervals requests: run={self.count}, today={total}, "
                    f"allowance_left={max(0, self._remaining())}, hold_until={hold}, scope={self.SCOPE}")
# End shared request controller.

def budgeted_write(operation):
    """Reserve the whole safety sequence without changing preview commands."""
    from functools import wraps

    @wraps(operation)
    def run(self, *args, **kwargs):
        reserved = False
        try:
            with self.request_budget.reserve_write():
                reserved = True
                return operation(self, *args, **kwargs)
        except RequestBudgetRefused as error:
            outcome = "unknown" if reserved and self.request_budget._write_sent else "not_applied"
            return {"success": False, "outcome": outcome, "error": str(error)}
    return run


class IntervalsPush:
    """Manage planned workouts on Intervals.icu calendar."""

    BASE_URL = "https://intervals.icu/api/v1"
    VERSION = "0.8"

    # Athlete path ID (v0.7). Intervals.icu uses `i` + digits for current accounts,
    # digits only for early accounts (their Strava athlete ID), and `0` for the
    # athlete that owns the API key. The ID is sent exactly as given: no `i` is added
    # or removed. Only `i` and ASCII digits pass, so no other text reaches the URL
    # path. This does not prove which athlete is targeted: the server decides what
    # the key may reach, and a coach's key can reach coached athletes.
    ATHLETE_ID_PATTERN = re.compile(r"i?[0-9]+")

    # --- HTTP policy (v0.6) ---
    # (connect, read) tuples. The connect leg bounds the connection phase and the
    # read leg bounds per-read inactivity, both as implemented by requests/urllib3.
    # The read leg is an inactivity timeout between socket reads, not a total
    # body-transfer deadline, so neither is a wall-clock bound on a call.
    READ_TIMEOUT = (5, 30)
    WRITE_TIMEOUT = (5, 30)
    # Safe reads only. No write is ever retried.
    READ_RETRY_STATUSES = (429, 500, 502, 503, 504)
    READ_RETRY_MAX_ATTEMPTS = 3
    READ_RETRY_BACKOFF_SECS = (1, 2)
    # Admission cap measured with time.monotonic() from the start of the call,
    # including completed request time and completed sleeps. It gates whether a
    # further attempt may begin; it does not stop an in-flight request. There is no
    # run-wide budget because one CLI invocation performs one operation.
    READ_RETRY_ADMISSION_CAP_SECS = 45
    # Statuses that definitively refuse a write. No verification read is needed and
    # nothing was applied. 410 sits here with 404: the resource is gone, so the write
    # was refused, and for a delete that is the requested end state.
    DEFINITIVE_WRITE_STATUSES = (400, 401, 403, 404, 409, 410, 422)

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

    def __init__(self, athlete_id: str, api_key: str, data_dir=None):
        if not athlete_id or not api_key:
            raise ValueError("athlete_id and api_key are required")
        # The rejected value is never echoed: a misplaced API key would land in logs.
        if not isinstance(athlete_id, str):
            raise ValueError(
                f"athlete_id must be a string, got {type(athlete_id).__name__}. "
                "Quote it in .sync_config.json. "
                "Check .sync_config.json / ATHLETE_ID / --athlete-id."
            )
        athlete_id = athlete_id.strip()
        api_key = api_key.strip()
        if not self.ATHLETE_ID_PATTERN.fullmatch(athlete_id):
            raise ValueError(
                "athlete_id is not a valid Intervals.icu athlete ID. Use it exactly as "
                "shown in Intervals.icu Settings: `i` followed by digits (e.g. "
                "`i123456`), or digits only for some early accounts. "
                "Check .sync_config.json / ATHLETE_ID / --athlete-id."
            )
        self.athlete_id = athlete_id
        self._budget_identity = RequestBudget.fingerprint(athlete_id, api_key)
        self.auth = base64.b64encode(f"API_KEY:{api_key}".encode()).decode()
        self.data_dir = self.find_data_dir(data_dir)

    _budget_factory = RequestBudget

    @staticmethod
    def find_data_dir(explicit=None):
        if explicit is not None:
            return Path(explicit).expanduser().resolve()
        source = Path(__file__).resolve()
        for parent in source.parents:
            if parent.name == "section11" and (parent.parent / "latest.json").is_file():
                return parent.parent
        cwd = Path.cwd()
        return cwd if (cwd / "latest.json").is_file() else None

    @property
    def request_budget(self):
        if not hasattr(self, "_request_budget"):
            if self.data_dir is None:
                print("Warning: data folder not found; use --data-dir or run beside latest.json. "
                      "Request capacity is unknown.", file=sys.stderr)
            self._request_budget = self._budget_factory(
                self.data_dir, "push", RequestBudgetRefused, self._budget_identity)
        return self._request_budget

    def _intervals_request(self, method, url, **kwargs):
        from urllib.parse import urlsplit
        if urlsplit(url).hostname != "intervals.icu":
            raise ValueError("unexpected API origin")
        endpoint = "verification" if self.request_budget._write_sent else "pre_read"
        if method != "get":
            endpoint = "write_" + method
        return self.request_budget.request(
            _ensure_requests(), method, url, endpoint, "core", **kwargs)

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
        if isinstance(e, WriteStatusError):
            return e.detail
        if hasattr(e, "response") and e.response is not None:
            return self._status_detail(e.response)
        return str(e)

    # ── HTTP policy helpers (v0.6) ────────────────────────────────
    #
    # These duplicate the CONCEPTS in sync.py deliberately. push.py is distributed
    # as a standalone copied script and must never import from sync.py, so the
    # policy is restated here rather than shared. Keep the two in step by hand.

    @staticmethod
    def _exception_types():
        """
        (Timeout, ConnectionError, HTTPError, RequestException) from whatever
        `requests` is bound.

        A test double may stand in for the whole module and carry no `exceptions`
        attribute. Resolving the classes once, up front, keeps an `except` clause
        from raising AttributeError while another exception is propagating; the
        sentinel makes those handlers simply never match.
        """
        requests = _ensure_requests()
        exc = getattr(requests, "exceptions", None)
        if exc is None:
            class _Unmatchable(Exception):
                pass
            return (_Unmatchable, _Unmatchable, _Unmatchable, _Unmatchable)
        return (exc.Timeout, exc.ConnectionError, exc.HTTPError, exc.RequestException)

    @staticmethod
    def _parse_retry_after(value) -> Optional[int]:
        """
        Parse an HTTP Retry-After header: delta-seconds or HTTP-date. Returns
        non-negative seconds, or None when absent or unparseable. Same contract as
        sync.py's helper; duplicated for standalone portability.
        """
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return None
        try:
            secs = int(raw)
            return secs if secs >= 0 else None
        except ValueError:
            pass
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(raw)
            if dt is None:
                return None
            ref = datetime.now(dt.tzinfo) if dt.tzinfo is not None else datetime.now()
            delta = (dt - ref).total_seconds()
            return int(delta) if delta > 0 else 0
        except Exception:
            return None

    def _read_retry_delay(self, attempt: int, retry_after_secs: Optional[int]) -> int:
        """Retry-After may raise the ladder delay but never lower it."""
        ladder = self.READ_RETRY_BACKOFF_SECS
        delay = ladder[min(attempt - 1, len(ladder) - 1)]
        if retry_after_secs is not None:
            delay = max(delay, int(retry_after_secs))
        return delay

    def _admit_read_retry(self, attempt: int, started_at: float, delay: int) -> bool:
        """
        Decide before sleeping whether attempt+1 may begin. A Retry-After too large
        to fit inside the admission window therefore ends the call immediately
        instead of sleeping and then declining to retry.
        """
        if attempt >= self.READ_RETRY_MAX_ATTEMPTS:
            return False
        return (time.monotonic() - started_at) + delay < self.READ_RETRY_ADMISSION_CAP_SECS

    def _read_with_retry(self, send):
        """
        Bounded safe read. Returns the final response; the caller still calls
        raise_for_status(). The original exception object is re-raised on exhausted
        transport failure, preserving its requests exception subclass.
        """
        Timeout, ConnectionError_, HTTPError_, _RequestException = self._exception_types()
        started_at = time.monotonic()
        attempt = 0
        while True:
            attempt += 1
            error = None
            response = None
            retry_after = None
            try:
                response = send()
            except (Timeout, ConnectionError_) as e:
                error = e
            else:
                if response.status_code == 429:
                    return response
                if response.status_code not in self.READ_RETRY_STATUSES:
                    return response
                if response.status_code in (429, 503):
                    retry_after = self._parse_retry_after(
                        response.headers.get("Retry-After"))

            delay = self._read_retry_delay(attempt, retry_after)
            if not self._admit_read_retry(attempt, started_at, delay):
                if error is not None:
                    raise error
                return response
            time.sleep(delay)

    def _write_once(self, send) -> Tuple[str, any, Optional[int]]:
        """
        Issue exactly one write and classify the result. There is no reissue path.

        Returns (state, payload, status):
            ("ok", value, status)          the server returned an explicit 2xx
            ("definitive", error, status)  a refusal that proves nothing was applied
            ("ambiguous", cause, status)   outcome unknown; the caller must verify

        Only DEFINITIVE_WRITE_STATUSES prove non-application without a verification
        read. Everything else that can happen after the request leaves this process
        is ambiguous, because the server may have committed the change and the
        response may have been lost on the way back. That includes a 429 or 5xx, a
        redirect or any other unexpected status, a chunked or truncated response, and
        any other requests exception this code does not specifically recognise.

        Unexpected non-requests exceptions are NOT caught. A bug in this file must
        surface as a traceback, not as a false claim about remote state.
        """
        Timeout, ConnectionError_, HTTPError_, RequestException_ = \
            self._exception_types()
        try:
            return ("ok", send(), None)
        except WriteStatusError as e:
            if e.status in self.DEFINITIVE_WRITE_STATUSES:
                return ("definitive", e.detail, e.status)
            return ("ambiguous", f"http_{e.status}", e.status)
        except HTTPError_ as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in self.DEFINITIVE_WRITE_STATUSES:
                return ("definitive", self._handle_error(e), status)
            return ("ambiguous", f"http_{status}", status)
        except (Timeout, ConnectionError_) as e:
            return ("ambiguous", f"transport: {type(e).__name__}", None)
        except ValueError as e:
            # An accepted write whose body will not parse. Applied or not is unknown.
            return ("ambiguous", f"unparseable_response: {e}", None)
        except RequestException_ as e:
            # ChunkedEncodingError, ContentDecodingError, a broken response stream:
            # everything reached the server, so none of these proves non-application.
            return ("ambiguous", f"transport: {type(e).__name__}", None)

    def _status_detail(self, response) -> str:
        """Readable detail for a non-2xx response, built from the status and body."""
        try:
            detail = response.json()
            message = f"{response.status_code}: {detail}"
        except Exception:
            message = f"{response.status_code}: {response.text[:200]}"
        if response.status_code == 403:
            message = (
                "Access denied (403). Common causes: athlete_id doesn't match "
                "the ID shown in Intervals.icu Settings exactly (an `i` added or "
                "dropped), API key is wrong, or the API key has no access to "
                f"this athlete. Raw response: {message}"
            )
        return message

    def _check_write_status(self, response):
        """
        Accept only an explicit 2xx.

        raise_for_status() passes 1xx and 3xx through, so a redirect or an
        informational response would otherwise be read as a successful write and the
        body parsed as the created object. Anything outside 2xx raises here, carrying
        the numeric status so the classifier never inspects formatted text.
        """
        status = response.status_code
        if 200 <= status < 300:
            return
        raise WriteStatusError(status, self._status_detail(response))

    @staticmethod
    def _is_object(payload) -> bool:
        return isinstance(payload, dict)

    @staticmethod
    def _readable_description(source: dict):
        """
        The description as a string, or None when the field is unusable.

        Absent and null both mean "no description" and read as "". Anything that is
        not a string is malformed: prepending a NOTE line to a number would either
        raise here or silently write nonsense.
        """
        if "description" not in source:
            return ""
        value = source.get("description")
        if value is None:
            return ""
        return value if isinstance(value, str) else None

    @staticmethod
    def _message_text(item: dict):
        """
        Message text as a string, or None when unusable.

        An empty or whitespace-only `content` falls back to `text`, because either
        field can carry the note and neither is guaranteed. This is push.py's own
        reading of the payload; sync.py's exporter falls back only when `content` is
        null, and that difference is deliberate rather than an oversight here: this
        value is only ever used as verification evidence, never as exported data.
        """
        for key in ("content", "text"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value
            if value is not None and not isinstance(value, str):
                return None
        return ""

    @staticmethod
    def _is_object_list(payload) -> bool:
        return isinstance(payload, list) and all(isinstance(i, dict) for i in payload)

    @staticmethod
    def _pre_read_failure(error: str) -> dict:
        """A failed pre-write read is a closed gate: definite failure, zero writes."""
        return {
            "success": False,
            "outcome": "not_applied",
            "error": f"pre-write read failed, no write attempted: {error}",
        }

    @staticmethod
    def _unknown(cause: str, detail: str, **extra) -> dict:
        result = {
            "success": False,
            "outcome": "unknown",
            "cause": cause,
            "error": f"write outcome UNKNOWN after {cause}: {detail} "
                     f"No write retry was issued.",
        }
        result.update(extra)
        return result

    def _get(self, endpoint: str, params: dict = None) -> any:
        """GET from Intervals.icu API."""
        requests = _ensure_requests()
        response = self._read_with_retry(
            lambda: self._intervals_request("get", self._url(endpoint), headers=self._headers(),
                                 params=params, timeout=self.READ_TIMEOUT))
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint: str, payload) -> any:
        """POST to Intervals.icu API. One attempt, never retried."""
        requests = _ensure_requests()
        response = self._intervals_request("post", self._url(endpoint), headers=self._headers(),
                                 json=payload, timeout=self.WRITE_TIMEOUT)
        self._check_write_status(response)
        return response.json()

    def _put(self, endpoint: str, payload: dict) -> any:
        """PUT to Intervals.icu API. One attempt, never retried."""
        requests = _ensure_requests()
        response = self._intervals_request("put", self._url(endpoint), headers=self._headers(),
                                json=payload, timeout=self.WRITE_TIMEOUT)
        self._check_write_status(response)
        return response.json()

    def _delete(self, endpoint: str) -> bool:
        """DELETE on Intervals.icu API. One attempt, never retried."""
        requests = _ensure_requests()
        response = self._intervals_request("delete", self._url(endpoint), headers=self._headers(),
                                   timeout=self.WRITE_TIMEOUT)
        self._check_write_status(response)
        return True

    # ── Validation ──────────────────────────────────────────────────

    @staticmethod
    def _workout_label(workout, index: int) -> str:
        """A safe label for an entry that may not be an object at all."""
        if isinstance(workout, dict):
            name = workout.get("name")
            if isinstance(name, str) and name.strip():
                return name
        return f"workout[{index}]"

    def validate_workout(self, workout) -> Tuple[bool, Optional[str]]:
        """Validate a workout dict. Returns (True, None) or (False, error)."""
        if not isinstance(workout, dict):
            # A JSON array may hold anything. Calling .get() on an int or a string
            # would raise out of a validation routine whose whole job is to report
            # problems as data.
            return False, (f"entry must be a JSON object, got "
                           f"{type(workout).__name__}")
        name = workout.get("name")
        if name is not None and not isinstance(name, str):
            return False, f"name must be text, got {type(name).__name__}"
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

        if "time" in workout and not self._valid_time(workout["time"]):
            return False, "time must be HH:MM local (00:00 through 23:59)"

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
            "start_date_local": f"{workout['date']}T{workout.get('time', '00:00')}:00",
            "name": workout["name"],
            "type": workout.get("type", "Ride"),
        }

        description = workout.get("description", "")
        if description:
            event["description"] = description

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
        """
        Compact summary of an Intervals.icu event.

        Display metadata only. It must never raise: a malformed moving_time or
        start_date_local is a cosmetic problem, and turning it into an exception
        would convert a verified write outcome into a crash or, worse, into a false
        claim about remote state. Unusable fields become None.
        """
        if not isinstance(evt, dict):
            return {"id": None, "name": None, "date": None, "type": None,
                    "category": None, "duration_minutes": None, "tss": None}
        moving_time = evt.get("moving_time")
        if isinstance(moving_time, bool) or not isinstance(moving_time, (int, float)):
            duration = None
        elif not moving_time:
            duration = None
        else:
            try:
                # NaN and both infinities are floats and pass isinstance, but round()
                # raises ValueError and OverflowError on them; an int wider than a
                # float can overflow the division. None of that may escape a display
                # helper.
                if isinstance(moving_time, float) and not math.isfinite(moving_time):
                    raise ValueError("non-finite moving_time")
                duration = round(moving_time / 60)
            except (ValueError, OverflowError, ArithmeticError, TypeError):
                duration = None
        start = evt.get("start_date_local")
        date = start[:10] if isinstance(start, str) else None
        local_time = start[11:] if isinstance(start, str) and len(start) > 11 and start[10] == "T" else None
        return {
            "id": evt.get("id"),
            "name": evt.get("name"),
            "date": date,
            "time": local_time,
            "type": evt.get("type"),
            "category": evt.get("category"),
            "duration_minutes": duration,
            "tss": evt.get("icu_training_load"),
        }

    # ── Push (create) ──────────────────────────────────────────────

    def push_workout(self, workout: dict) -> dict:
        """Validate and push a single workout."""
        return self.push_workouts([workout])

    @budgeted_write
    def push_workouts(self, workouts: list) -> dict:
        """
        Validate and push multiple workouts through the bulk upsert endpoint.

        v0.6: the pre-write window read is a safety gate, not an optimisation. It
        establishes that every intended external_id resolves to at most one event
        INSIDE THE FETCHED TARGET DATE WINDOW, which is what makes verification over
        that same window sound. It says nothing about uniqueness elsewhere in the
        athlete's calendar, and the API's upsert matching key is not established by
        this source. If the read fails, nothing is written.
        """
        if not workouts:
            return {"success": False, "outcome": "not_applied",
                    "error": "no workouts provided"}

        errors = []
        for i, w in enumerate(workouts):
            valid, error = self.validate_workout(w)
            if not valid:
                errors.append(f"{self._workout_label(w, i)}: {error}")
        if errors:
            return {"success": False, "outcome": "not_applied",
                    "error": "; ".join(errors)}

        events = [self._build_event(w) for w in workouts]

        ext_ids = [e["external_id"] for e in events if e.get("external_id")]
        duplicates = sorted({x for x in ext_ids if ext_ids.count(x) > 1})
        if duplicates:
            return {
                "success": False, "outcome": "not_applied",
                "error": f"duplicate external_id within the submitted batch: "
                         f"{duplicates}. Verification could not be sound, so nothing "
                         f"was written.",
            }

        dates = sorted(w["date"] for w in workouts)
        window = self._read_event_window(dates[0], dates[-1])
        if not window["success"]:
            return self._pre_read_failure(window["error"])

        upstream_counts = {}
        for evt in window["events"]:
            eid = evt.get("external_id")
            if eid:
                key = str(eid)
                upstream_counts[key] = upstream_counts.get(key, 0) + 1
        conflicting = sorted(x for x in set(ext_ids) if upstream_counts.get(x, 0) > 1)
        if conflicting:
            return {
                "success": False, "outcome": "not_applied",
                "error": f"the target window already holds more than one event for "
                         f"external_id {conflicting}. Verification could not be "
                         f"sound, so nothing was written.",
            }

        state, payload, _status = self._write_once(
            lambda: self._post("events/bulk?upsert=true", events))

        if state == "definitive":
            return {"success": False, "outcome": "not_applied", "error": payload}
        if state == "ambiguous":
            return self._verify_bulk(events, dates, payload)

        # An explicit 2xx is not enough on its own. The body must be a list of
        # objects of the expected length before it can be read as "all of these
        # landed"; anything else may be a partial application or a shape this code
        # cannot interpret, and goes to verification rather than to a claim.
        response = payload
        if not self._is_object_list(response):
            return self._verify_bulk(events, dates, "malformed_response_body")
        if len(response) != len(events):
            return self._verify_bulk(events, dates,
                                     f"response_count_{len(response)}")
        return {"success": True, "outcome": "applied",
                "count": len(response),
                "events": [self._summarize_event(evt) for evt in response]}

    def _read_event_window(self, oldest: str, newest: str) -> dict:
        """Raw event read over a date span, used as snapshot and as verifier."""
        try:
            response = self._get("events", params={"oldest": oldest, "newest": newest})
        except Exception as e:
            return {"success": False, "error": self._handle_error(e)}
        if not self._is_object_list(response):
            # A malformed 200 establishes nothing. Coercing it to [] would look like
            # an empty calendar and let a write proceed against unknown state.
            return {"success": False,
                    "error": "malformed events payload: expected a list of objects"}
        return {"success": True, "events": response}

    @staticmethod
    def _event_matches_intent(remote: dict, intended: dict) -> bool:
        """
        Every intended field must be present upstream with the intended value.
        Strict by design: a mismatch yields unknown, never a claim of success.
        external_id is the locator, not a payload field, so it is compared by the
        caller.
        """
        for key, want in intended.items():
            if key == "external_id":
                continue
            if remote.get(key) != want:
                return False
        return True

    def _verify_bulk(self, events: list, dates: list, cause: str) -> dict:
        """
        Classify a bulk upsert whose outcome is not established.

        applied requires EVERY item to be found by its intended external_id,
        uniquely, with all intended fields equal. Absence of a match does not prove
        non-application: the upsert matching key is not established by the current
        source, so anything short of a unique exact match is unknown. No replay.
        """
        window = self._read_event_window(dates[0], dates[-1])
        if not window["success"]:
            return self._unknown(
                cause,
                f"the verification read failed ({window['error']}), so whether the "
                f"batch was applied could not be established.",
                items=[{"name": e.get("name"), "date": (e.get("start_date_local") or "")[:10],
                        "state": "unknown", "reason": "verification_read_failed"}
                       for e in events])

        by_ext = {}
        for evt in window["events"]:
            eid = evt.get("external_id")
            if eid:
                by_ext.setdefault(str(eid), []).append(evt)

        items = []
        all_applied = True
        for intended in events:
            label = {"name": intended.get("name"),
                     "date": (intended.get("start_date_local") or "")[:10]}
            eid = intended.get("external_id")
            if not eid:
                all_applied = False
                items.append({**label, "state": "unknown", "reason": "no_external_id"})
                continue
            matches = by_ext.get(str(eid), [])
            if len(matches) != 1:
                all_applied = False
                items.append({**label, "state": "unknown",
                              "reason": "no_unique_external_id_match"})
                continue
            if self._event_matches_intent(matches[0], intended):
                items.append({**label, "state": "applied",
                              "id": matches[0].get("id")})
            else:
                all_applied = False
                items.append({**label, "state": "unknown", "reason": "field_mismatch"})

        if all_applied:
            return {
                "success": True, "outcome": "applied", "verified_after": cause,
                "count": len(items),
                "events": [self._summarize_event(by_ext[str(e["external_id"])][0])
                           for e in events],
            }
        return self._unknown(
            cause,
            "at least one item could not be matched to a unique external_id with "
            "every intended field equal. Matching on name, date or type would not "
            "be proof, so those items stay unknown.",
            items=items)

    def preview_push(self, workouts: list) -> dict:
        """Validate workouts and return preview without writing."""
        errors = []
        for i, w in enumerate(workouts):
            valid, error = self.validate_workout(w)
            if not valid:
                errors.append(f"{self._workout_label(w, i)}: {error}")
        if errors:
            return {"success": False, "mode": "preview", "error": "; ".join(errors)}

        events = [self._build_event(w) for w in workouts]
        summary = []
        for w in workouts:
            summary.append({
                "name": w.get("name"),
                "date": w.get("date"),
                "time": w.get("time", "00:00"),
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

    def _event_presence(self, event_id: int) -> dict:
        """
        Establish whether an event exists.

        {"state": "present", "event": {...}} | {"state": "absent"} |
        {"state": "error", "error": str}

        A definitive 404 or 410 is a successful establishment of absence, not a
        failed read.
        """
        _t, _c, HTTPError_, _re = self._exception_types()
        try:
            event = self._get(f"events/{event_id}")
            if not self._is_object(event):
                return {"state": "error",
                        "error": "malformed event payload: expected an object"}
            return {"state": "present", "event": event}
        except HTTPError_ as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (404, 410):
                return {"state": "absent"}
            return {"state": "error", "error": self._handle_error(e)}
        except Exception as e:
            return {"state": "error", "error": self._handle_error(e)}

    @budgeted_write
    def update_event(self, event_id: int, updates: dict) -> dict:
        """Partial update of an event, gated by a pre-write read."""
        pre = self._event_presence(event_id)
        if pre["state"] == "error":
            return self._pre_read_failure(pre["error"])
        if pre["state"] == "absent":
            return {"success": False, "outcome": "not_applied",
                    "error": f"event {event_id} does not exist; nothing was written"}
        return self._apply_event_update(event_id, updates)

    def _apply_event_update(self, event_id: int, updates: dict) -> dict:
        """
        One PUT, then verification if the outcome is not established. Callers that
        have already taken the pre-write read use this directly rather than paying
        for a second GET.
        """
        state, payload, _status = self._write_once(
            lambda: self._put(f"events/{event_id}", updates))
        if state == "definitive":
            return {"success": False, "outcome": "not_applied", "error": payload}
        if state == "ambiguous":
            return self._verify_event_update(event_id, updates, payload)
        summary = self._summarize_event(payload) if isinstance(payload, dict) else None
        return {"success": True, "outcome": "applied", "event": summary}

    def _verify_event_update(self, event_id: int, updates: dict, cause: str) -> dict:
        """Only exact equality on every requested field proves the write landed."""
        post = self._event_presence(event_id)
        if post["state"] == "error":
            return self._unknown(cause, f"the verification read failed "
                                        f"({post['error']}).")
        if post["state"] == "absent":
            return self._unknown(cause, f"event {event_id} is no longer readable, so "
                                        f"the requested change cannot be confirmed.")
        evt = post["event"]
        if all(evt.get(k) == v for k, v in updates.items()):
            return {"success": True, "outcome": "applied", "verified_after": cause,
                    "event": self._summarize_event(evt)}
        return self._unknown(
            cause,
            "the event does not carry every requested value. It may hold the "
            "pre-write state or a concurrent edit; neither proves the write failed.")

    @staticmethod
    def _valid_time(value):
        return isinstance(value, str) and re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value) is not None

    @staticmethod
    def _move_start(event, new_date, new_time):
        if new_time is not None:
            return f"{new_date}T{new_time}:00"
        raw = event.get("start_date_local")
        if raw in (None, "") or (isinstance(raw, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw)):
            return f"{new_date}T00:00:00"
        try:
            if not isinstance(raw, str) or "T" not in raw:
                raise ValueError()
            datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("existing start time is invalid; supply --time HH:MM")
        return new_date + "T" + raw.split("T", 1)[1]

    def preview_move(self, event_id: int, new_date: str, new_time: str = None) -> dict:
        """Preview moving a workout to a new date."""
        if new_time is not None and not self._valid_time(new_time):
            return {"success": False, "mode": "preview", "error": "time must be HH:MM local"}
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
        try:
            start = self._move_start(evt, new_date, new_time)
        except ValueError as error:
            return {"success": False, "mode": "preview", "error": str(error)}

        return {
            "success": True,
            "mode": "preview",
            "event_id": event_id,
            "name": evt.get("name"),
            "from_date": old_date,
            "to_date": new_date,
            "from_time": self._summarize_event(evt).get("time"),
            "to_time": start.split("T", 1)[1],
            "message": "Preview only - add --confirm to move this workout",
        }

    @budgeted_write
    def move_event(self, event_id: int, new_date: str, new_time: str = None) -> dict:
        """Move a workout to a new date."""
        if new_time is not None and not self._valid_time(new_time):
            return {"success": False, "outcome": "not_applied", "error": "time must be HH:MM local"}
        # Validate
        try:
            target_date = datetime.strptime(new_date, "%Y-%m-%d").date()
        except ValueError:
            return {"success": False, "outcome": "not_applied",
                    "error": f"invalid date: {new_date}"}

        today = datetime.now().date()
        if target_date < today:
            return {"success": False, "outcome": "not_applied",
                    "error": f"date {new_date} is in the past"}

        pre = self._event_presence(event_id)
        if pre["state"] == "error":
            return self._pre_read_failure(pre["error"])
        if pre["state"] == "absent":
            return {"success": False, "outcome": "not_applied",
                    "error": f"event {event_id} does not exist; nothing was written"}
        try:
            start = self._move_start(pre["event"], new_date, new_time)
        except ValueError as error:
            return {"success": False, "outcome": "not_applied", "error": str(error)}
        return self._apply_event_update(event_id, {"start_date_local": start})

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

    @budgeted_write
    def delete_event(self, event_id: int) -> dict:
        """
        Delete a single event.

        v0.6 treats delete as desired-state convergence: an event that is already
        absent is the requested end state, so it reports applied/unchanged with zero
        DELETE requests rather than a failure.
        """
        pre = self._event_presence(event_id)
        if pre["state"] == "error":
            return self._pre_read_failure(pre["error"])
        if pre["state"] == "absent":
            return {"success": True, "outcome": "applied", "unchanged": True,
                    "deleted": event_id,
                    "message": "event was already absent; no request issued"}

        state, payload, status = self._write_once(
            lambda: self._delete(f"events/{event_id}"))
        if state == "ok":
            return {"success": True, "outcome": "applied", "deleted": event_id}
        if state == "definitive":
            # Desired-state convergence, decided on the NUMERIC status. A 400 whose
            # body happens to contain the characters "404" is still a refusal.
            if status in (404, 410):
                return {"success": True, "outcome": "applied", "unchanged": True,
                        "deleted": event_id,
                        "message": "event was already absent at write time"}
            return {"success": False, "outcome": "not_applied", "error": payload}

        post = self._event_presence(event_id)
        if post["state"] == "absent":
            return {"success": True, "outcome": "applied", "deleted": event_id,
                    "verified_after": payload}
        if post["state"] == "error":
            return self._unknown(payload, f"the verification read failed "
                                          f"({post['error']}).")
        return self._unknown(
            payload,
            f"event {event_id} is still readable. A delete can still be in flight, "
            f"so this does not prove the request failed.")

    # ── Raw URL helpers (for non-athlete endpoints) ────────────────

    def _get_raw(self, url: str) -> any:
        """GET from an absolute Intervals.icu URL."""
        requests = _ensure_requests()
        response = self._read_with_retry(
            lambda: self._intervals_request("get", url, headers=self._headers(),
                                 timeout=self.READ_TIMEOUT))
        response.raise_for_status()
        return response.json()

    def _post_raw(self, url: str, payload) -> any:
        """POST to an absolute Intervals.icu URL. One attempt, never retried."""
        requests = _ensure_requests()
        response = self._intervals_request("post", url, headers=self._headers(), json=payload,
                                 timeout=self.WRITE_TIMEOUT)
        self._check_write_status(response)
        return response.json()

    def _put_raw(self, url: str, payload: dict) -> any:
        """PUT to an absolute Intervals.icu URL. One attempt, never retried."""
        requests = _ensure_requests()
        response = self._intervals_request("put", url, headers=self._headers(), json=payload,
                                timeout=self.WRITE_TIMEOUT)
        self._check_write_status(response)
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
        except Exception as e:
            return {"success": False, "error": self._handle_error(e)}
        if not self._is_object(response):
            return {"success": False,
                    "error": "malformed sport settings payload: expected an object"}
        return {"success": True, "settings": response}

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

    @budgeted_write
    def set_threshold(self, sport: str, updates: dict) -> dict:
        """Update sport-specific thresholds."""
        sport_type = self._resolve_sport_type(sport)

        invalid = set(updates.keys()) - self.THRESHOLD_FIELDS
        if invalid:
            return {"success": False, "outcome": "not_applied",
                    "error": f"invalid fields: {sorted(invalid)}"}
        if not updates:
            return {"success": False, "outcome": "not_applied",
                    "error": "no threshold fields provided"}

        pre = self.get_sport_settings(sport_type)
        if not pre["success"]:
            return self._pre_read_failure(pre["error"])

        state, payload, _status = self._write_once(
            lambda: self._put(f"sport-settings/{sport_type}", updates))
        if state == "definitive":
            return {"success": False, "outcome": "not_applied", "error": payload}
        if state == "ambiguous":
            return self._verify_threshold(sport_type, updates, payload)

        response = payload if isinstance(payload, dict) else {}
        return {"success": True, "outcome": "applied", "sport": sport_type,
                "updated": {field: response.get(field) for field in updates}}

    def _verify_threshold(self, sport_type: str, updates: dict, cause: str) -> dict:
        """
        Only exact equality confirms. Whether the API normalises or rounds these
        fields is not established by the current source, so a value that is neither
        the pre-write value nor the intended value stays unknown.
        """
        post = self.get_sport_settings(sport_type)
        if not post["success"]:
            return self._unknown(cause, f"the verification read failed "
                                        f"({post['error']}).")
        settings = post["settings"]
        if all(settings.get(field) == value for field, value in updates.items()):
            return {"success": True, "outcome": "applied", "verified_after": cause,
                    "sport": sport_type,
                    "updated": {f: settings.get(f) for f in updates}}
        return self._unknown(
            cause,
            "the stored settings do not exactly equal the requested values. They may "
            "be the pre-write values, a concurrent edit, or server normalisation; "
            "none of those proves the write failed.",
            observed={f: settings.get(f) for f in updates})

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
        except Exception as e:
            return {"success": False, "error": self._handle_error(e)}
        if not self._is_object(response):
            return {"success": False,
                    "error": "malformed activity payload: expected an object"}
        return {"success": True, "activity": response}

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

    @budgeted_write
    def annotate_activity(self, activity_id: str, message: str, chat: bool = False) -> dict:
        """Add a note to a completed activity. Default: description. --chat: messages endpoint."""
        if not message or not message.strip():
            return {"success": False, "outcome": "not_applied",
                    "error": "message is required"}

        if chat:
            return self._annotate_activity_chat(activity_id, message)
        return self._annotate_activity_description(activity_id, message)

    def _get_activity_messages_raw(self, activity_id: str) -> dict:
        """
        Raw message elements, retained whole so a pre-write snapshot can be compared
        by id. get_activity_messages() keeps only text and created, which cannot
        support verification.
        """
        try:
            url = f"{self.BASE_URL}/activity/{activity_id}/messages"
            response = self._get_raw(url)
        except Exception as e:
            return {"success": False, "error": self._handle_error(e)}
        if not self._is_object_list(response):
            return {"success": False,
                    "error": "malformed messages payload: expected a list of objects"}
        return {"success": True, "messages": response}

    @staticmethod
    def _message_ids(messages: list) -> set:
        return {str(m.get("id")) for m in messages
                if isinstance(m, dict) and m.get("id") is not None}

    def _annotate_activity_chat(self, activity_id: str, message: str) -> dict:
        """
        Post a note to a completed activity's messages/chat.

        v0.6: the snapshot read is a gate. After an ambiguous POST the outcome is
        UNKNOWN unconditionally, because the current source does not establish that
        this endpoint returns a stable unique message id. Any ids or matching text
        observed are returned as evidence for the agent and never change the
        classification. No write retry is ever issued: a replay is a visible duplicate message.
        """
        text = message.strip()
        snapshot = self._get_activity_messages_raw(activity_id)
        if not snapshot["success"]:
            return self._pre_read_failure(snapshot["error"])
        before_ids = self._message_ids(snapshot["messages"])

        url = f"{self.BASE_URL}/activity/{activity_id}/messages"
        state, payload, _status = self._write_once(
            lambda: self._post_raw(url, {"content": text}))
        if state == "ok":
            return {"success": True, "outcome": "applied", "target": "activity_chat",
                    "activity_id": activity_id, "message": text}
        if state == "definitive":
            return {"success": False, "outcome": "not_applied", "error": payload}

        evidence = {"stable_message_id_available": False}
        after = self._get_activity_messages_raw(activity_id)
        if after["success"]:
            after_ids = self._message_ids(after["messages"])
            evidence["stable_message_id_available"] = bool(after_ids)
            evidence["new_message_ids"] = sorted(after_ids - before_ids)
            texts = [self._message_text(m) for m in after["messages"]]
            evidence["unreadable_message_content"] = any(t is None for t in texts)
            evidence["matching_text_present"] = any(
                t is not None and t.strip() == text for t in texts)
        else:
            evidence["verification_read_error"] = after["error"]
        return self._unknown(
            payload,
            "activity chat notes cannot be verified: the API is not established to "
            "return a stable unique message id, and identical text or timing "
            "proximity is not proof. Read the activity's messages before re-running.",
            target="activity_chat", activity_id=activity_id, message=text,
            evidence=evidence)

    def _annotate_activity_description(self, activity_id: str, message: str) -> dict:
        """Prepend a NOTE: line to a completed activity's description."""
        text = message.strip()
        current = self.get_activity(activity_id)
        if not current["success"]:
            return self._pre_read_failure(current["error"])

        act = current["activity"]
        existing_desc = self._readable_description(act)
        if existing_desc is None:
            return self._pre_read_failure(
                "malformed activity payload: description is not text")
        note_line = f"NOTE: {text}"

        # Duplicate suppression. Re-running after an unknown outcome is the
        # documented recovery, so it must not double the note.
        if existing_desc.split("\n", 1)[0].strip() == note_line:
            return {"success": True, "outcome": "applied", "unchanged": True,
                    "target": "activity_description", "activity_id": activity_id,
                    "message": text,
                    "note": "this note is already the first line; no request issued"}

        new_desc = f"{note_line}\n\n{existing_desc}" if existing_desc else note_line
        url = f"{self.BASE_URL}/activity/{activity_id}"
        state, payload, _status = self._write_once(
            lambda: self._put_raw(url, {"description": new_desc}))
        if state == "ok":
            return {"success": True, "outcome": "applied",
                    "target": "activity_description", "activity_id": activity_id,
                    "message": text}
        if state == "definitive":
            return {"success": False, "outcome": "not_applied", "error": payload}

        post = self.get_activity(activity_id)
        if not post["success"]:
            return self._unknown(payload, f"the verification read failed "
                                          f"({post['error']}).",
                                 target="activity_description",
                                 activity_id=activity_id)
        observed = self._readable_description(post["activity"])
        if observed is None:
            return self._unknown(payload,
                                 "the verification read returned a description that "
                                 "is not text, so the outcome cannot be established.",
                                 target="activity_description",
                                 activity_id=activity_id)
        if observed == new_desc:
            return {"success": True, "outcome": "applied", "verified_after": payload,
                    "target": "activity_description", "activity_id": activity_id,
                    "message": text}
        return self._unknown(
            payload,
            "the description does not exactly equal the intended text. It may hold "
            "the pre-write value or a concurrent edit; neither proves the write "
            "failed.",
            target="activity_description", activity_id=activity_id)

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

    @budgeted_write
    def annotate_event(self, event_id: int, message: str) -> dict:
        """Add a NOTE: line to a planned workout's description."""
        text = message.strip() if message else ""
        if not text:
            return {"success": False, "outcome": "not_applied",
                    "error": "message is required"}

        # This read is the pre-write gate for the PUT below, so _apply_event_update
        # is called directly rather than update_event, which would read again.
        pre = self._event_presence(event_id)
        if pre["state"] == "error":
            return self._pre_read_failure(pre["error"])
        if pre["state"] == "absent":
            return {"success": False, "outcome": "not_applied",
                    "error": f"event {event_id} does not exist; nothing was written"}

        evt = pre["event"]
        existing_desc = self._readable_description(evt)
        if existing_desc is None:
            return self._pre_read_failure(
                "malformed event payload: description is not text")
        note_line = f"NOTE: {text}"

        # Duplicate suppression: re-running after an unknown outcome must not double
        # the note.
        if existing_desc.split("\n", 1)[0].strip() == note_line:
            return {"success": True, "outcome": "applied", "unchanged": True,
                    "target": "event", "event_id": event_id, "message": text,
                    "note": "this note is already the first line; no request issued"}

        new_desc = f"{note_line}\n\n{existing_desc}" if existing_desc else note_line
        return self._apply_event_update(event_id, {"description": new_desc})


# ── CLI ────────────────────────────────────────────────────────────

def _reject_local(args, error: str):
    """
    Emit a local rejection and exit.

    When --confirm is present this IS a write result: nothing was sent, so it is a
    definite not_applied and must carry the outcome contract, or a caller cannot tell
    it from an unknown outcome. Preview and read-only commands have no --confirm and
    keep their original outcome-free shape.
    """
    if getattr(args, "confirm", False):
        _output({"success": False, "outcome": "not_applied", "error": error})
    _output({"success": False, "error": error})


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


_OUTCOME_EXIT_CODES = {"applied": 0, "not_applied": 1, "unknown": 2}


def _output(result: dict):
    """
    Print result JSON and exit with the appropriate code.

    Write results carry `outcome` and map applied -> 0, not_applied -> 1,
    unknown -> 2, so a caller or workflow can tell "this did not happen" from
    "nobody knows whether this happened". Preview and read-only results carry no
    outcome key and keep the original 0/1 behaviour untouched.
    """
    print(json.dumps(result, indent=2))
    outcome = result.get("outcome")
    if outcome is not None:
        sys.exit(_OUTCOME_EXIT_CODES.get(outcome, 1))
    sys.exit(0 if result.get("success") else 1)


def _build_workouts_from_args(args) -> list:
    """Build workout list from CLI args or --json file."""
    if args.json:
        if args.time is not None:
            _reject_local(args, "--time is for a single workout; JSON uses per-workout time")
        try:
            with open(args.json) as f:
                data = json.load(f)
            return data if isinstance(data, list) else [data]
        except Exception as e:
            _reject_local(args, f"Failed to read {args.json}: {e}")

    if not args.name or not args.date:
        _reject_local(
            args,
            "--name and --date are required (or use --json for file input)")

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
    if args.time is not None:
        workout["time"] = args.time

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
        _output(pusher.preview_move(args.event_id, args.date, args.time))
    else:
        _output(pusher.move_event(args.event_id, args.date, args.time))


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
        # In confirm mode this IS a write result: the write definitely did not
        # happen, so it carries the outcome contract. Preview keeps its old shape.
        _reject_local(args, "provide at least one threshold field (--ftp, "
                            "--indoor-ftp, --lthr, --max-hr, --threshold-pace)")

    if not args.confirm:
        _output(pusher.preview_set_threshold(args.sport, updates))
    else:
        _output(pusher.set_threshold(args.sport, updates))


def _cmd_annotate(args, pusher: IntervalsPush):
    """Handle annotate subcommand."""
    if args.activity_id and args.event_id:
        _reject_local(args, "provide --activity-id OR --event-id, not both")
    if not args.activity_id and not args.event_id:
        _reject_local(args,
                      "provide --activity-id (completed) or --event-id (planned)")

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
    parser.add_argument("--data-dir", help="Data folder shared with sync.py (contains latest.json)")

    subparsers = parser.add_subparsers(dest="command")

    # ── push ──
    push_parser = subparsers.add_parser("push", help="Add workouts to calendar")
    push_parser.add_argument("--name", help="Workout name (required unless --json)")
    push_parser.add_argument("--date", help="Date YYYY-MM-DD (required unless --json)")
    push_parser.add_argument("--time", help="Local start HH:MM for a single workout; JSON uses per-workout time")
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
    move_parser.add_argument("--time", help="Local start HH:MM; omitted preserves the existing time")
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
    top_level_value_flags = {"--athlete-id", "--api-key", "--data-dir"}

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
        _reject_local(
            args,
            "Missing credentials. Provide via --athlete-id/--api-key, "
            ".sync_config.json, or env vars ATHLETE_ID/INTERVALS_KEY")

    pusher = None
    try:
        pusher = IntervalsPush(athlete_id, api_key, data_dir=args.data_dir)
    except ValueError as e:
        _reject_local(args, str(e))

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
