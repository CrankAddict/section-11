"""
Tests for the history.json refresh gate, retention and failure backoff.

Origin: written for the unreleased history-refresh repair on top of sync.py
v3.136. Behaviour is validated against the current sync.py.

Standard library only: unittest and unittest.mock, no third-party test packages,
no real athlete data, no network. All fixtures are synthetic. Importing sync.py
does require `requests`, its normal runtime dependency, so these tests must run
under the interpreter or virtual environment that already runs sync.py.

Run from the repository root:

    python3 -m unittest discover dev/tests

Seams, chosen so the same assertions also run against the pre-repair sync.py and
fail there on behaviour rather than on a missing name:
  * the clock is frozen by replacing sync.py's module-level `datetime` with a
    subclass whose now() returns a fixed instant (naive host-local when called
    without a tz, as the old gate did, aware when called with one);
  * the host timezone is pinned with TZ plus time.tzset(), to UTC by default,
    which is what a GitHub runner uses. That needs time.tzset(), so on a platform
    without it (Windows) the module is skipped with a reason;
  * runs go through main() with --output, so the automatic path is exercised as
    shipped, with collect_training_data, save_to_file and the update check
    patched out and every Intervals.icu read replaced by a scripted fake;
  * a GitHub Actions runner is simulated as a fresh temporary directory seeded
    only with the bytes of the previously committed history.json. A run that is
    "published" commits its history.json; one that is not leaves the committed
    bytes unchanged, which is how state is lost when a whole run fails.

Covered: age boundaries and the removed weekday/midnight window, catch-up after
downtime, unusable and future generated_at, timezone and DST interpretation,
retention of an existing file on failed fetches, atomic writes, refresh_state
backoff, Retry-After, clock regression, malformed state, script-hash
containment, error sanitisation, manual --generate-history, publication
failures, first-run behaviour and the accepted residuals (first run without a
state carrier, and GitHub runs that are not published).

Also covered: the GitHub Actions run budget (B1-B20). Platform context is
hermetic: setUpModule removes GITHUB_ACTIONS, GITHUB_EVENT_NAME,
GITHUB_RUN_NUMBER and GITHUB_RUN_ATTEMPT (and only those) for the duration of
this module and restores them afterwards, so a suite run inside GitHub Actions
behaves as a local one. Budget cases set the exact context they need with
actions(), never inheriting host values. They drive only main() and
should_generate_history(), so against a sync.py without the budget they fail on
attempt counts, not on missing names.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from _harness import (NetworkBlocked, SYNC_PATH, install_verb_guard,
                      load_module_by_path, restore_verb_guard)

sync_mod = load_module_by_path("s11_sync_history", SYNC_PATH)
IntervalsSync = sync_mod.IntervalsSync
requests = sync_mod.requests


# ── network guard and host timezone ──────────────────────────────────────────

# Same verb seam as the other sync.py modules: only the named verbs are replaced
# and requests.exceptions stays reachable. Installed in setUpModule, never at
# import time, for the reason given in _harness.

_ORIGINAL_VERBS = {}
_ORIGINAL_TZ = None

# GitHub Actions context read by the history run budget. Removed for this module
# so host values can never leak into a case; nothing else in os.environ changes.
PLATFORM_KEYS = ("GITHUB_ACTIONS", "GITHUB_EVENT_NAME", "GITHUB_RUN_NUMBER", "GITHUB_RUN_ATTEMPT")
_HOST_PLATFORM = {}


def setUpModule():
    global _ORIGINAL_VERBS, _ORIGINAL_TZ
    if not hasattr(time, "tzset"):
        raise unittest.SkipTest("time.tzset() unavailable: host timezone cannot be pinned")
    for key in PLATFORM_KEYS:
        if key in os.environ:
            _HOST_PLATFORM[key] = os.environ.pop(key)
    _ORIGINAL_TZ = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    _ORIGINAL_VERBS = install_verb_guard(sync_mod.requests)


def tearDownModule():
    restore_verb_guard(sync_mod.requests, _ORIGINAL_VERBS)
    os.environ.update(_HOST_PLATFORM)
    if hasattr(time, "tzset"):
        if _ORIGINAL_TZ is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = _ORIGINAL_TZ
        time.tzset()


@contextlib.contextmanager
def actions(number, event="schedule", attempt=1, github_actions="true"):
    """
    Exactly this GitHub Actions context for the block; a None value leaves that
    variable unset. Everything else in os.environ, TMPDIR included, is kept.
    """
    values = {"GITHUB_ACTIONS": github_actions, "GITHUB_EVENT_NAME": event,
              "GITHUB_RUN_NUMBER": None if number is None else str(number),
              "GITHUB_RUN_ATTEMPT": None if attempt is None else str(attempt)}
    with mock.patch.dict(os.environ):
        for key in PLATFORM_KEYS:
            os.environ.pop(key, None)
        os.environ.update({k: v for k, v in values.items() if v is not None})
        yield


@contextlib.contextmanager
def host_tz(name):
    previous = os.environ.get("TZ")
    os.environ["TZ"] = name
    time.tzset()
    try:
        yield
    finally:
        os.environ["TZ"] = previous if previous is not None else "UTC"
        time.tzset()


# ── frozen clock ─────────────────────────────────────────────────────────────

class FrozenDatetime(datetime):
    """sync.py's `datetime` with now() fixed at `frozen_utc`."""

    frozen_utc = None

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return datetime.fromtimestamp(cls.frozen_utc.timestamp())
        return cls.frozen_utc.astimezone(tz)


@contextlib.contextmanager
def frozen(now_utc):
    FrozenDatetime.frozen_utc = now_utc
    with mock.patch.object(sync_mod, "datetime", FrozenDatetime):
        yield


@contextlib.contextmanager
def chdir(path):
    previous = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def local_naive(dt_utc):
    """The naive host-local stamp generate_history() would have written at dt_utc."""
    return datetime.fromtimestamp(dt_utc.timestamp()).isoformat()


# Fixed instants (host TZ is UTC unless a test pins another).
SUN_0007 = utc(2026, 7, 19, 0, 7)       # inside the old window
SUN_0045 = utc(2026, 7, 19, 0, 45)      # W1 :07 run delayed past 00:30
MON_0010 = utc(2026, 7, 20, 0, 10)
MON_0031 = utc(2026, 7, 20, 0, 31)
TUE_1400 = utc(2026, 7, 21, 14, 0)
WED_1200 = utc(2026, 7, 22, 12, 0)
WED_0007 = utc(2026, 7, 22, 0, 7)


# ── fixtures ─────────────────────────────────────────────────────────────────

CURRENT_HASH = IntervalsSync("athlete_test", "key_test").script_hash


def prior_history(generated_at, script_hash=None, **extra):
    """A synthetic, previously generated history.json body."""
    data = {
        "generated_at": generated_at,
        "source": "Intervals.icu API",
        "sync_version": "3.136",
        "script_hash": CURRENT_HASH if script_hash is None else script_hash,
        "data_range": {"earliest": "2024-01-01", "latest": "2026-06-20", "total_months": 30},
        "ftp_timeline": [{"date": "2025-05-01", "ftp": 250, "type": "indoor"}],
        "data_gaps": [],
        "summaries": {"note": "synthetic retained summary"},
        "daily_90d": [{"date": "2026-06-20", "total_tss": 55.5, "hrv": 61}],
        "weekly_180d": [{"week_start": "2026-06-15", "total_tss": 300.0, "phase_detected": "Build"}],
        "monthly_1y": [{"month": "2026-05", "total_tss": 1200}],
        "monthly_2y": [],
        "monthly_3y": [],
    }
    data.update(extra)
    return data


def write_history(directory, data):
    path = Path(directory) / "history.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return path


def read_history(directory):
    with open(Path(directory) / "history.json") as f:
        return json.load(f)


def http_error(status, retry_after=None, secret="TOKENSECRET"):
    response = requests.models.Response()
    response.status_code = status
    response.url = f"https://intervals.icu/api/v1/athlete/i999?key={secret}"
    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
    return requests.exceptions.HTTPError(
        f"{status} Error for url: {response.url}", response=response)


class Api:
    """
    Scripted stand-in for IntervalsSync._intervals_get. Each endpoint returns its
    value, or raises it when it is an exception. Every call is recorded.
    """

    def __init__(self, activities=None, wellness=None, athlete=None):
        self.outcomes = {
            "activities": [] if activities is None else activities,
            "wellness": [{"id": "2026-07-01", "ctl": 50, "atl": 40, "hrv": 60}] if wellness is None else wellness,
            "": {} if athlete is None else athlete,
        }
        self.calls = []

    def __call__(self, endpoint, params=None):
        self.calls.append(endpoint)
        outcome = self.outcomes.get(endpoint, {})
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def attempts(self):
        """Generation attempts that reached the athlete read (always the last of the three)."""
        return self.calls.count("")

    def started(self):
        """Generation attempts started (the activities read is always first)."""
        return self.calls.count("activities")


MIN_DATA = {"derived_metrics": {}, "alerts": [], "history": {}}


def run_main(directory, now_utc, api, mode="output", extra_args=(), publish=None,
             write_latest=False):
    """
    One sync.py run through main(), offline. mode "output" is the documented
    local/GitHub Actions invocation; "api" is the direct-API mode, with
    publish_to_github replaced by `publish`. write_latest keeps the real
    save_to_file, so latest.json is actually written.
    Returns (collect_mock, publish_mock, stdout text).
    """
    argv = ["sync.py", "--athlete-id", "i000000", "--intervals-key", "k000000"]
    if mode == "output":
        argv += ["--output", "latest.json"]
    else:
        argv += ["--github-token", "t000000", "--github-repo", "owner/repo"]
    argv += list(extra_args)
    publish = publish if publish is not None else mock.MagicMock(return_value="https://example.invalid/latest.json")
    out = io.StringIO()
    with chdir(directory), frozen(now_utc), \
            mock.patch.object(sys, "argv", argv), \
            mock.patch.object(IntervalsSync, "_intervals_get", api), \
            mock.patch.object(IntervalsSync, "collect_training_data", return_value=MIN_DATA) as collect, \
            (contextlib.nullcontext() if write_latest else
             mock.patch.object(IntervalsSync, "save_to_file", return_value="latest.json")), \
            mock.patch.object(IntervalsSync, "publish_to_github", publish), \
            mock.patch.object(IntervalsSync, "check_upstream_updates"), \
            mock.patch.object(sync_mod, "notify_if_updates_available"), \
            mock.patch.object(sync_mod, "_rotate_log_if_needed"), \
            contextlib.redirect_stdout(out):
        sync_mod.main()
    return collect, publish, out.getvalue()


def gate(directory, now_utc):
    s = IntervalsSync("athlete_test", "key_test")
    s.data_dir = Path(directory)
    with frozen(now_utc), contextlib.redirect_stdout(io.StringIO()):
        return s.should_generate_history()


def generate(directory, now_utc, api):
    s = IntervalsSync("athlete_test", "key_test")
    s.data_dir = Path(directory)
    with frozen(now_utc), mock.patch.object(s, "_intervals_get", api), \
            contextlib.redirect_stdout(io.StringIO()):
        return s.generate_history()


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def assert_state(self, data):
        self.assertIn("refresh_state", data,
                      "a failed automatic refresh of an existing file recorded no refresh_state")
        return data["refresh_state"]

    def assert_data_retained(self, before, after):
        self.assertEqual({k: v for k, v in after.items() if k != "refresh_state"},
                         {k: v for k, v in before.items() if k != "refresh_state"},
                         "existing history content was replaced by a failed refresh")
        self.assertEqual([k for k in after if k != "refresh_state"],
                         [k for k in before if k != "refresh_state"],
                         "key order of the retained file changed")


# ── R1: the gate ─────────────────────────────────────────────────────────────

class GateTests(TempDirCase):
    """T1-T7, T10, T11, T20, T21, T25."""

    def overdue(self, now, days=30, **extra):
        write_history(self.dir, prior_history(local_naive(now - timedelta(days=days)), **extra))

    def test_t1_delayed_sunday_run_is_due(self):
        self.overdue(SUN_0045)
        self.assertTrue(gate(self.dir, SUN_0045),
                        "overdue history skipped because the W1 run started after 00:30")

    def test_t2_monday_0031_is_due(self):
        self.overdue(MON_0031)
        self.assertTrue(gate(self.dir, MON_0031), "overdue history skipped at Monday 00:31")

    def test_t3_old_window_run_still_due(self):
        self.overdue(SUN_0007)
        self.assertTrue(gate(self.dir, SUN_0007))

    def test_t4_weekend_downtime_catches_up_on_first_run(self):
        self.overdue(TUE_1400, days=33)
        self.assertTrue(gate(self.dir, TUE_1400),
                        "history overdue after whole-weekend downtime waited for the next weekend")

    def test_t5_just_under_29_days_not_due(self):
        write_history(self.dir, prior_history(
            local_naive(MON_0010 - timedelta(days=28, hours=23, minutes=59, seconds=59))))
        self.assertFalse(gate(self.dir, MON_0010), "strict > 28 whole days boundary moved")

    def test_t6_exactly_29_days_due_midweek(self):
        write_history(self.dir, prior_history(local_naive(WED_1200 - timedelta(days=29))))
        self.assertTrue(gate(self.dir, WED_1200), "a 29-day-old file is not due on a Wednesday")

    def test_t7_fresh_file_not_due(self):
        self.overdue(SUN_0007, days=10)
        self.assertFalse(gate(self.dir, SUN_0007))
        self.overdue(WED_1200, days=10)
        self.assertFalse(gate(self.dir, WED_1200))

    def test_t10_unusable_generated_at_due_any_time(self):
        for value in (None, "", "not-a-date", 12345):
            with self.subTest(generated_at=value):
                data = prior_history("x")
                if value is None:
                    del data["generated_at"]
                else:
                    data["generated_at"] = value
                write_history(self.dir, data)
                self.assertTrue(gate(self.dir, WED_1200),
                                "an unusable generated_at regenerated only inside the old window")

    def test_t11_future_generated_at(self):
        write_history(self.dir, prior_history(local_naive(SUN_0007 + timedelta(days=2))))
        self.assertTrue(gate(self.dir, SUN_0007),
                        "a generated_at two days in the future is never refreshed")
        # Nearby valid case: within the one-day tolerance it is simply fresh.
        write_history(self.dir, prior_history(local_naive(SUN_0007 + timedelta(hours=12))))
        self.assertFalse(gate(self.dir, SUN_0007))

    def test_t20_clock_regression_ignores_far_future_state(self):
        state = {"last_attempt_at": (WED_1200 + timedelta(days=4)).isoformat(),
                 "consecutive_failures": 3,
                 "next_attempt_after": (WED_1200 + timedelta(days=5)).isoformat(),
                 "attempt_script_hash": CURRENT_HASH,
                 "last_error": {"kind": "timeout", "status": None}}
        self.overdue(WED_1200, refresh_state=state)
        self.assertTrue(gate(self.dir, WED_1200),
                        "a next attempt beyond the 24h maximum (clock regression) blocked refresh")
        # Nearby valid case: a genuine pending backoff is honoured.
        state = dict(state, next_attempt_after=(WED_1200 + timedelta(minutes=30)).isoformat())
        self.overdue(WED_1200, refresh_state=state)
        self.assertFalse(gate(self.dir, WED_1200))

    def test_t21_aware_generated_at_converted_not_stripped(self):
        # 29d 00:30 elapsed in UTC, written with a +03:00 offset.
        write_history(self.dir, prior_history("2026-06-20T02:40:00+03:00"))
        self.assertTrue(gate(self.dir, utc(2026, 7, 19, 0, 10)),
                        "an aware generated_at had its offset dropped instead of converted")
        # Nearby valid case: the same instant written with Z.
        write_history(self.dir, prior_history("2026-06-19T23:40:00Z"))
        self.assertTrue(gate(self.dir, utc(2026, 7, 19, 0, 10)))

    def test_t21_naive_stamp_across_dst_uses_real_elapsed_time(self):
        # Europe/Helsinki enters summer time on 2026-03-29. A naive local stamp
        # from before the change is 28d 23:50 old in real time but 29d 00:50 by
        # wall clock; the age is real elapsed time.
        with host_tz("Europe/Helsinki"):
            now = utc(2026, 3, 29, 21, 20)          # Monday 00:20 local
            write_history(self.dir, prior_history("2026-02-28T23:30:00"))
            self.assertFalse(gate(self.dir, now),
                             "wall-clock subtraction across DST made a 28d 23:50 file due")
            write_history(self.dir, prior_history("2026-02-28T22:30:00"))
            self.assertTrue(gate(self.dir, now))

    def test_t25_malformed_refresh_state_is_ignored(self):
        for state in ("text", [], {"attempt_script_hash": CURRENT_HASH},
                      {"attempt_script_hash": CURRENT_HASH, "next_attempt_after": "garbage"},
                      {"attempt_script_hash": CURRENT_HASH, "next_attempt_after": 5},
                      {"attempt_script_hash": CURRENT_HASH,
                       "next_attempt_after": (WED_1200 + timedelta(hours=1)).replace(tzinfo=None).isoformat()}):
            with self.subTest(state=state):
                self.overdue(WED_1200, refresh_state=state)
                self.assertTrue(gate(self.dir, WED_1200), "malformed refresh_state blocked refresh")


# ── R2: retention and atomic writes ──────────────────────────────────────────

class RetentionTests(TempDirCase):
    """T15, T15b, T16, T17, T24a and state preservation.

    Runs at Sunday 00:07, inside the old window, so the pre-repair gate also
    attempts these refreshes and the retention assertions themselves are what a
    regression would trip.
    """

    NOW = SUN_0007

    def setUp(self):
        super().setUp()
        self.before = prior_history(local_naive(self.NOW - timedelta(days=30)))
        write_history(self.dir, self.before)

    def test_t15_activities_failure_keeps_existing_file(self):
        api = Api(activities=requests.exceptions.ConnectionError("down"))
        collect, _, _ = run_main(self.dir, self.NOW, api)
        after = read_history(self.dir)
        self.assert_data_retained(self.before, after)
        state = self.assert_state(after)
        self.assertEqual(state["last_error"], {"kind": "connection", "status": None})
        self.assertTrue(collect.called, "a failed history refresh stopped the main sync")

    def test_t15b_wellness_failure_keeps_existing_file(self):
        api = Api(wellness=requests.exceptions.Timeout("slow"))
        run_main(self.dir, self.NOW, api)
        after = read_history(self.dir)
        self.assert_data_retained(self.before, after)
        self.assertEqual(self.assert_state(after)["last_error"], {"kind": "timeout", "status": None})

    def test_athlete_failure_keeps_existing_file(self):
        api = Api(athlete=http_error(502))
        run_main(self.dir, self.NOW, api)
        after = read_history(self.dir)
        self.assert_data_retained(self.before, after)
        self.assertEqual(self.assert_state(after)["last_error"], {"kind": "http_status", "status": 502})

    def test_t16_successful_empty_upstream_is_written(self):
        api = Api(activities=[], wellness=[])
        history = generate(self.dir, self.NOW, api)
        after = read_history(self.dir)
        self.assertEqual(after["generated_at"], history["generated_at"])
        self.assertEqual(after["generated_at"], local_naive(self.NOW))
        self.assertNotIn("refresh_state", after)
        self.assertNotEqual(after["data_range"], self.before["data_range"])

    def test_t17_failed_write_leaves_previous_file_and_no_temp(self):
        original = (self.dir / "history.json").read_bytes()
        real_dump = json.dump

        def partial_dump(obj, fp, **kwargs):
            fp.write('{"generated_at": "trunc')
            raise OSError("disk full")

        api = Api(activities=[], wellness=[])
        with mock.patch.object(sync_mod.json, "dump", partial_dump):
            with self.assertRaises(OSError):
                generate(self.dir, self.NOW, api)
        self.assertIs(json.dump, real_dump)
        self.assertEqual((self.dir / "history.json").read_bytes(), original,
                         "a failed history write truncated the existing file")
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["history.json"],
                         "a temp file was left behind after a failed write")

    def test_state_write_failure_is_non_critical(self):
        original = (self.dir / "history.json").read_bytes()
        api = Api(athlete=requests.exceptions.ConnectionError("down"))
        with mock.patch.object(sync_mod.os, "replace", side_effect=OSError("read-only")):
            collect, _, _ = run_main(self.dir, self.NOW, api)
        self.assertTrue(collect.called, "a failed refresh_state write stopped the main sync")
        self.assertEqual((self.dir / "history.json").read_bytes(), original)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["history.json"])

    def test_retained_bytes_differ_only_by_refresh_state(self):
        original_text = (self.dir / "history.json").read_text()
        api = Api(athlete=requests.exceptions.ConnectionError("down"))
        run_main(self.dir, self.NOW, api)
        after = read_history(self.dir)
        self.assert_state(after)
        stripped = {k: v for k, v in after.items() if k != "refresh_state"}
        self.assertEqual(json.dumps(stripped, indent=2, default=str), original_text,
                         "pre-existing content was re-serialised differently")
        self.assertEqual(after["generated_at"], self.before["generated_at"])

    def test_t24a_manual_failure_with_prior_file_is_loud_and_keeps_file(self):
        original = (self.dir / "history.json").read_bytes()
        api = Api(activities=requests.exceptions.ConnectionError("down"))
        with self.assertRaises(requests.exceptions.ConnectionError):
            run_main(self.dir, self.NOW, api, extra_args=("--generate-history",))
        self.assertEqual((self.dir / "history.json").read_bytes(), original,
                         "--generate-history replaced good history after a failed fetch")

    def test_manual_success_bypasses_backoff_and_clears_state(self):
        state = {"last_attempt_at": self.NOW.isoformat(), "consecutive_failures": 2,
                 "next_attempt_after": (self.NOW + timedelta(hours=6)).isoformat(),
                 "attempt_script_hash": CURRENT_HASH,
                 "last_error": {"kind": "timeout", "status": None}}
        write_history(self.dir, dict(self.before, refresh_state=state))
        run_main(self.dir, self.NOW + timedelta(minutes=5), Api(), extra_args=("--generate-history",))
        after = read_history(self.dir)
        self.assertNotIn("refresh_state", after)
        self.assertEqual(after["generated_at"], local_naive(self.NOW + timedelta(minutes=5)))


class ManualFirstRunTests(TempDirCase):
    """T24b, T24c: the manual path follows the same first-run rule."""

    def test_t24b_manual_no_prior_activities_failure_writes_degraded_file(self):
        api = Api(activities=requests.exceptions.ConnectionError("down"))
        run_main(self.dir, WED_1200, api, extra_args=("--generate-history",))
        after = read_history(self.dir)
        self.assertNotIn("refresh_state", after)
        self.assertEqual(after["data_range"]["latest"], WED_1200.strftime("%Y-%m-%d"))

    def test_t24c_manual_no_prior_athlete_failure_raises_without_file(self):
        api = Api(athlete=requests.exceptions.ConnectionError("down"))
        with self.assertRaises(requests.exceptions.ConnectionError):
            run_main(self.dir, WED_1200, api, extra_args=("--generate-history",))
        self.assertFalse((self.dir / "history.json").exists())


# ── R3: refresh_state, backoff and containment ───────────────────────────────

class BackoffTests(TempDirCase):
    """T12, T13, T13b, T14, T18, T19, sanitisation."""

    def test_t14_local_minute_timer_three_attempts_in_first_day(self):
        write_history(self.dir, prior_history(local_naive(WED_0007 - timedelta(days=30))))
        api = Api(athlete=requests.exceptions.ConnectionError("down"))
        attempt_minutes = []
        for minute in range(0, 1900):
            before = api.attempts()
            run_main(self.dir, WED_0007 + timedelta(minutes=minute), api)
            if api.attempts() > before:
                attempt_minutes.append(minute)
        self.assertEqual(attempt_minutes, [0, 60, 420, 1860],
                         "automatic attempts did not follow the 1h/6h/24h ladder at a 60 s cadence")
        self.assertEqual(len([m for m in attempt_minutes if m < 1440]), 3)
        self.assertEqual(api.started(), 4, "API load not contained: extra history pulls started")
        self.assertEqual(self.assert_state(read_history(self.dir))["consecutive_failures"], 4)

    def _w1_chain(self, published, runs=96):
        committed = json.dumps(prior_history(local_naive(WED_0007 - timedelta(days=30))),
                               indent=2).encode()
        api = Api(athlete=requests.exceptions.ConnectionError("down"))
        attempt_offsets = []
        for i in range(runs):
            offset = timedelta(minutes=30 * i)
            with tempfile.TemporaryDirectory() as runner:
                (Path(runner) / "history.json").write_bytes(committed)
                before = api.attempts()
                run_main(runner, WED_0007 + offset, api)
                if api.attempts() > before:
                    attempt_offsets.append(offset)
                if published:
                    committed = (Path(runner) / "history.json").read_bytes()
        return attempt_offsets, committed

    def test_t13_w1_fresh_runners_published_follow_ladder(self):
        offsets, committed = self._w1_chain(published=True)
        hours = [o.total_seconds() / 3600 for o in offsets]
        self.assertEqual(hours, [0, 1, 7, 31],
                         "refresh_state carried in the committed file did not back fresh runners off")
        data = json.loads(committed)
        self.assert_data_retained(
            prior_history(local_naive(WED_0007 - timedelta(days=30))), data)

    def test_t13b_w1_unpublished_runs_lose_state_accepted_residual(self):
        # Accepted residual, not a containment claim: when the whole GitHub run
        # fails (combined outage, failed push) the committed file never carries
        # the state, so every fresh runner attempts again.
        offsets, committed = self._w1_chain(published=False, runs=48)
        self.assertEqual(len(offsets), 48)
        self.assertNotIn("refresh_state", json.loads(committed))

    def test_t12_script_change_contained_per_hash(self):
        write_history(self.dir, prior_history(local_naive(WED_1200 - timedelta(days=1)),
                                              script_hash="0ldhash00000"))
        api = Api(athlete=requests.exceptions.ConnectionError("down"))
        run_main(self.dir, WED_1200, api)
        self.assertEqual(api.attempts(), 1, "changed sync.py did not get an immediate attempt")
        self.assertEqual(self.assert_state(read_history(self.dir))["attempt_script_hash"], CURRENT_HASH)
        run_main(self.dir, WED_1200 + timedelta(minutes=30), api)
        self.assertEqual(api.attempts(), 1, "the sync.py-changed trigger retried inside its backoff")
        run_main(self.dir, WED_1200 + timedelta(minutes=61), api)
        self.assertEqual(api.attempts(), 2)
        with mock.patch.object(IntervalsSync, "script_hash",
                               new_callable=mock.PropertyMock, return_value="n3whash00000"):
            run_main(self.dir, WED_1200 + timedelta(minutes=70), api)
            self.assertEqual(api.attempts(), 3, "a newer sync.py was held back by older state")
            state = self.assert_state(read_history(self.dir))
            self.assertEqual(state["consecutive_failures"], 1)
            self.assertEqual(state["attempt_script_hash"], "n3whash00000")

    def test_t18_success_after_failures_clears_state(self):
        write_history(self.dir, prior_history(local_naive(WED_1200 - timedelta(days=30))))
        run_main(self.dir, WED_1200, Api(athlete=requests.exceptions.ConnectionError("down")))
        self.assert_state(read_history(self.dir))
        later = WED_1200 + timedelta(hours=2)
        run_main(self.dir, later, Api())
        after = read_history(self.dir)
        self.assertNotIn("refresh_state", after)
        self.assertEqual(after["generated_at"], local_naive(later))

    def test_t19_retry_after_raises_never_lowers_and_is_capped(self):
        cases = (
            (http_error(429, retry_after=7200), timedelta(hours=2)),
            (http_error(503, retry_after=10 * 86400), timedelta(hours=24)),
            (http_error(503, retry_after=60), timedelta(hours=1)),
            (http_error(500, retry_after=7200), timedelta(hours=1)),
        )
        for error, expected in cases:
            with self.subTest(status=error.response.status_code,
                              retry_after=error.response.headers.get("Retry-After")):
                write_history(self.dir, prior_history(local_naive(WED_1200 - timedelta(days=30))))
                run_main(self.dir, WED_1200, Api(athlete=error))
                state = self.assert_state(read_history(self.dir))
                due = datetime.fromisoformat(state["next_attempt_after"])
                self.assertEqual(due - WED_1200, expected)
                self.assertEqual(due.utcoffset(), timedelta(0), "next_attempt_after is not aware UTC")

    def test_error_kinds_are_sanitised(self):
        cases = (
            (http_error(429, secret="TOKENSECRET"), {"kind": "http_status", "status": 429}),
            (requests.exceptions.Timeout("https://intervals.icu/?key=TOKENSECRET"), {"kind": "timeout", "status": None}),
            (requests.exceptions.ConnectionError("TOKENSECRET"), {"kind": "connection", "status": None}),
            (requests.exceptions.JSONDecodeError("TOKENSECRET", "doc", 0), {"kind": "decode", "status": None}),
            (RuntimeError("athlete TOKENSECRET"), {"kind": "internal", "status": None}),
        )
        for error, expected in cases:
            with self.subTest(error=type(error).__name__):
                write_history(self.dir, prior_history(local_naive(WED_1200 - timedelta(days=30))))
                run_main(self.dir, WED_1200, Api(athlete=error))
                state = self.assert_state(read_history(self.dir))
                self.assertEqual(state["last_error"], expected)
                self.assertEqual(set(state), {"last_attempt_at", "consecutive_failures",
                                              "next_attempt_after", "attempt_script_hash",
                                              "last_error"})
                self.assertNotIn("TOKENSECRET", (self.dir / "history.json").read_text(),
                                 "exception text leaked into history.json")


# ── orchestration, publication and first-run residuals ───────────────────────

class OrchestrationTests(TempDirCase):
    """T8a, T8b, T9, T22, T23."""

    def test_t22_generation_failure_stays_non_critical(self):
        write_history(self.dir, prior_history(local_naive(SUN_0007 - timedelta(days=30))))
        collect, _, out = run_main(self.dir, SUN_0007,
                                   Api(athlete=requests.exceptions.ConnectionError("down")))
        self.assertTrue(collect.called)
        self.assertIn("non-critical", out)

    def test_t23_publication_failures_record_nothing_and_never_replay(self):
        for error in (sync_mod.PublishOutcomeUnknown("unknown"), sync_mod.PublishError("refused")):
            with self.subTest(error=type(error).__name__):
                write_history(self.dir, prior_history(local_naive(SUN_0007 - timedelta(days=30))))
                publish = mock.MagicMock(side_effect=[error, "https://example.invalid/latest.json"])
                collect, publish, out = run_main(self.dir, SUN_0007, Api(), mode="api", publish=publish)
                history_calls = [c for c in publish.call_args_list
                                 if c.kwargs.get("filepath") == "history.json"]
                self.assertEqual(len(history_calls), 1, "history publication was replayed")
                after = read_history(self.dir)
                self.assertNotIn("refresh_state", after,
                                 "a publication failure was recorded as a generation failure")
                self.assertEqual(after["generated_at"], local_naive(SUN_0007))
                self.assertTrue(collect.called)

    def test_t8a_first_run_activities_failure_writes_degraded_file(self):
        # Accepted first-run behaviour, unchanged: no prior file, so a swallowed
        # activities failure still writes a degraded file and no state.
        api = Api(activities=requests.exceptions.ConnectionError("down"))
        for minute in range(5):
            run_main(self.dir, WED_1200 + timedelta(minutes=minute), api)
        self.assertEqual(api.started(), 1)
        after = read_history(self.dir)
        self.assertNotIn("refresh_state", after)
        self.assertTrue(after["daily_90d"], "wellness rows missing from the degraded first file")

    def test_t8b_first_run_propagating_failure_retries_every_run(self):
        # Accepted residual: with no file there is no state carrier, so an
        # athlete-read failure is retried on every run, as before.
        api = Api(athlete=requests.exceptions.ConnectionError("down"))
        for minute in range(5):
            run_main(self.dir, WED_1200 + timedelta(minutes=minute), api)
        self.assertEqual(api.attempts(), 5)
        self.assertFalse((self.dir / "history.json").exists())

    def test_t9_unreadable_file_has_no_state_carrier(self):
        for body in ("{not json", "[1, 2, 3]"):
            with self.subTest(body=body):
                (self.dir / "history.json").write_text(body)
                api = Api(athlete=requests.exceptions.ConnectionError("down"))
                for minute in range(3):
                    run_main(self.dir, WED_1200 + timedelta(minutes=minute), api)
                self.assertEqual(api.attempts(), 3)
                self.assertEqual((self.dir / "history.json").read_text(), body)
                # Nearby case: an activities-only failure writes a degraded file
                # under the unchanged first-run rule.
                run_main(self.dir, WED_1200 + timedelta(minutes=5),
                         Api(activities=requests.exceptions.ConnectionError("down")))
                after = read_history(self.dir)
                self.assertIsInstance(after, dict)
                self.assertNotIn("refresh_state", after)


# ── GitHub Actions run budget (B1-B20) ───────────────────────────────────────

DEFERRED = "automatic refresh deferred"
OVERDUE_AT_WED_0007 = prior_history(local_naive(WED_0007 - timedelta(days=30)))


def scheduled(numbers, event="schedule"):
    return [(n, event, 1) for n in numbers]


def actions_chain(runs, api, publish_when=lambda number: False, history=None):
    """
    Each run is (run number, event, run attempt), executed in the given order on
    a fresh runner 30 minutes apart, seeded with the committed history.json. A
    run whose number satisfies publish_when commits its history.json. Returns the
    runs that started a history generation, and the final committed bytes.
    """
    committed = json.dumps(OVERDUE_AT_WED_0007 if history is None else history,
                           indent=2).encode()
    attempted = []
    for i, (number, event, attempt) in enumerate(runs):
        with tempfile.TemporaryDirectory() as runner:
            (Path(runner) / "history.json").write_bytes(committed)
            before = api.started()
            with actions(number, event, attempt):
                run_main(runner, WED_0007 + timedelta(minutes=30 * i), api)
            if api.started() > before:
                attempted.append((number, event, attempt))
            if publish_when(number):
                committed = (Path(runner) / "history.json").read_bytes()
    return attempted, committed


class ActionsBudgetTests(TempDirCase):
    """B1-B20: the GitHub Actions run budget on top of the gate and backoff."""

    def overdue(self, now=WED_1200, days=30, **extra):
        write_history(self.dir, prior_history(local_naive(now - timedelta(days=days)), **extra))

    def held_gate(self, number, event="schedule", **kwargs):
        with actions(number, event, **kwargs):
            return gate(self.dir, WED_1200)

    def test_b1_eligibility_table(self):
        self.overdue()
        cases = (
            ("not in Actions", dict(number=1001, github_actions=None), True),
            ("GITHUB_ACTIONS not 'true'", dict(number=1001, github_actions="false"), True),
            ("manual dispatch, held number", dict(number=1001, event="workflow_dispatch"), True),
            ("schedule 32", dict(number=32), True),
            ("schedule 33", dict(number=33), False),
            ("schedule 1008", dict(number=1008), True),
            ("push 33", dict(number=33, event="push"), False),
            ("push 48", dict(number=48, event="push"), True),
            ("repository_dispatch 1001", dict(number=1001, event="repository_dispatch"), False),
            ("event missing, 1001", dict(number=1001, event=None), False),
            ("event missing, 1008", dict(number=1008, event=None), True),
        )
        for label, kwargs, expected in cases:
            with self.subTest(label):
                self.assertIs(self.held_gate(**kwargs), expected)
        for raw in (None, "", "0", "-16", "1e3", " 32", "32 ", "32.0", "032", "+32",
                    "٣٢", "0x20", "16\n"):
            with self.subTest(malformed=raw):
                self.assertFalse(self.held_gate(raw), "a malformed run number was not held")

    def test_b2_unpublished_generation_failure_six_eligible_attempts(self):
        api = Api(athlete=requests.exceptions.ConnectionError("down"))
        attempted, committed = actions_chain(scheduled(range(1000, 1096)), api)
        self.assertEqual([n for n, _, _ in attempted], [1008, 1024, 1040, 1056, 1072, 1088])
        self.assertEqual(api.started(), 6, "unpublished failures were not contained by the run budget")
        self.assertNotIn("refresh_state", json.loads(committed))

    def test_b3_unpublished_successful_pulls_six_eligible_attempts(self):
        api = Api()
        attempted, committed = actions_chain(scheduled(range(1000, 1096)), api)
        self.assertEqual([n for n, _, _ in attempted], [1008, 1024, 1040, 1056, 1072, 1088])
        self.assertEqual((api.started(), api.attempts()), (6, 6),
                         "full history pulls repeated on runs that could not publish")
        self.assertEqual(json.loads(committed), OVERDUE_AT_WED_0007)

    def test_b4_published_failures_need_both_backoff_and_budget(self):
        api = Api(athlete=requests.exceptions.ConnectionError("down"))
        attempted, committed = actions_chain(scheduled(range(1000, 1096)), api,
                                             publish_when=lambda n: True)
        # 1008: failure 1 (1h); 1024: failure 2 (6h); 1040: failure 3 (24h, until
        # run 1088); 1056 and 1072 are eligible but still backing off.
        self.assertEqual([n for n, _, _ in attempted], [1008, 1024, 1040, 1088])
        data = json.loads(committed)
        self.assertEqual(self.assert_state(data)["consecutive_failures"], 4)
        self.assert_data_retained(OVERDUE_AT_WED_0007, data)

    def test_b5_script_change_trigger_is_budgeted_and_keeps_per_hash_backoff(self):
        write_history(self.dir, prior_history(local_naive(WED_1200 - timedelta(days=1)),
                                              script_hash="0ldhash00000"))
        original = (self.dir / "history.json").read_bytes()
        api = Api(athlete=requests.exceptions.ConnectionError("down"))
        with actions(1001):
            _, _, out = run_main(self.dir, WED_1200, api)
        self.assertEqual(api.calls, [], "a held run requested history")
        self.assertEqual((self.dir / "history.json").read_bytes(), original)
        self.assertIn("stale (sync.py changed): " + DEFERRED, out)
        with actions(1008):
            run_main(self.dir, WED_1200 + timedelta(minutes=30), api)
        self.assertEqual(api.attempts(), 1)
        self.assertEqual(self.assert_state(read_history(self.dir))["attempt_script_hash"], CURRENT_HASH)
        with actions(1024):
            _, _, out = run_main(self.dir, WED_1200 + timedelta(minutes=60), api)
        self.assertEqual(api.attempts(), 1, "an eligible run ignored the per-hash backoff")
        self.assertNotIn(DEFERRED, out, "backoff must be reported before the budget")
        with actions(1025, event="workflow_dispatch"):
            run_main(self.dir, WED_1200 + timedelta(minutes=91), api)
        self.assertEqual(api.attempts(), 2)

    def test_b6_first_run_paths_are_not_budgeted(self):
        for body in (None, "{not json", "[1, 2, 3]"):
            with self.subTest(body=body):
                path = self.dir / "history.json"
                if path.exists():
                    path.unlink()
                if body is not None:
                    path.write_text(body)
                api = Api(athlete=requests.exceptions.ConnectionError("down"))
                for i, number in enumerate((1001, 1002, 1003)):
                    with actions(number):
                        run_main(self.dir, WED_1200 + timedelta(minutes=30 * i), api)
                self.assertEqual(api.attempts(), 3, "the first-run path was budgeted")
                if body is None:
                    self.assertFalse(path.exists())
                else:
                    self.assertEqual(path.read_text(), body)
        # Nearby case: an activities-only failure still writes a degraded first file.
        (self.dir / "history.json").unlink()
        with actions(1005):
            run_main(self.dir, WED_1200 + timedelta(hours=3),
                     Api(activities=requests.exceptions.ConnectionError("down")))
        self.assertNotIn("refresh_state", read_history(self.dir))

    def test_b7_dispatch_skips_only_the_budget(self):
        self.overdue()
        api = Api(athlete=requests.exceptions.ConnectionError("down"))
        with actions(1001, event="workflow_dispatch"):
            run_main(self.dir, WED_1200, api)
        self.assertEqual(api.attempts(), 1, "Sync Now on a held number did not refresh a due file")
        with actions(1002, event="workflow_dispatch"):
            run_main(self.dir, WED_1200 + timedelta(minutes=30), api)
        self.assertEqual(api.attempts(), 1, "Sync Now bypassed refresh_state backoff")
        self.overdue(days=10)
        with actions(1003, event="workflow_dispatch"):
            run_main(self.dir, WED_1200 + timedelta(hours=2), api)
        self.assertEqual(api.attempts(), 1, "Sync Now refreshed a file that was not due")

    def test_b8_held_run_completes_main_sync_and_keeps_history_bytes(self):
        self.overdue()
        original = (self.dir / "history.json").read_bytes()
        api = Api()
        with actions(1001):
            collect, _, out = run_main(self.dir, WED_1200, api, write_latest=True)
        self.assertTrue(collect.called, "a held run skipped the main sync")
        with open(self.dir / "latest.json") as f:
            self.assertEqual(json.load(f), MIN_DATA)
        self.assertEqual((self.dir / "history.json").read_bytes(), original)
        self.assertEqual(api.calls, [], "a held run issued a history request")
        self.assertEqual(out.count(DEFERRED), 1)

    def test_b9_rerun_keeps_its_number(self):
        api = Api(athlete=requests.exceptions.ConnectionError("down"))
        attempted, _ = actions_chain([(1008, "schedule", 1), (1008, "schedule", 2),
                                      (1009, "schedule", 1), (1009, "schedule", 2)], api)
        self.assertEqual(attempted, [(1008, "schedule", 1), (1008, "schedule", 2)])
        # With the failure published, an eligible re-run is still held by backoff.
        self.overdue()
        api = Api(athlete=requests.exceptions.ConnectionError("down"))
        with actions(1024, attempt=1):
            run_main(self.dir, WED_1200, api)
        with actions(1024, attempt=2):
            run_main(self.dir, WED_1200 + timedelta(minutes=10), api)
        self.assertEqual(api.attempts(), 1)

    def test_b10_not_due_eligible_run_does_nothing(self):
        self.overdue(days=10)
        api = Api()
        with actions(1008):
            _, _, out = run_main(self.dir, WED_1200, api)
        self.assertEqual(api.calls, [])
        self.assertNotIn(DEFERRED, out)

    def test_b11_trigger_and_state_variants_still_held(self):
        future_state = {"last_attempt_at": (WED_1200 + timedelta(days=4)).isoformat(),
                        "consecutive_failures": 3,
                        "next_attempt_after": (WED_1200 + timedelta(days=5)).isoformat(),
                        "attempt_script_hash": CURRENT_HASH,
                        "last_error": {"kind": "timeout", "status": None}}
        variants = {
            "malformed refresh_state": prior_history(local_naive(WED_1200 - timedelta(days=30)),
                                                     refresh_state="text"),
            "far-future refresh_state": prior_history(local_naive(WED_1200 - timedelta(days=30)),
                                                      refresh_state=future_state),
            "unusable generated_at": prior_history("not-a-date"),
            "future generated_at": prior_history(local_naive(WED_1200 + timedelta(days=2))),
        }
        for label, data in variants.items():
            with self.subTest(label):
                write_history(self.dir, data)
                self.assertFalse(self.held_gate(1001), "the budget did not hold this trigger")
                self.assertTrue(self.held_gate(1008), "an eligible run did not refresh this trigger")

    def test_b12_recovery_publishes_at_first_eligible_run(self):
        # Controlled chain: every run executes, generation succeeds, no backoff,
        # scheduled runs only. Pushes fail until run 1048.
        api = Api()
        attempted, committed = actions_chain(scheduled(range(1000, 1072)), api,
                                             publish_when=lambda n: n >= 1048)
        self.assertEqual([n for n, _, _ in attempted], [1008, 1024, 1040, 1056])
        data = json.loads(committed)
        self.assertEqual(data["generated_at"], local_naive(WED_0007 + timedelta(minutes=30 * 56)))
        self.assertNotIn("refresh_state", data)

    def test_b13_local_timer_ignores_stray_run_variables(self):
        write_history(self.dir, prior_history(local_naive(WED_0007 - timedelta(days=30))))
        api = Api(athlete=requests.exceptions.ConnectionError("down"))
        attempt_minutes = []
        with actions(1001, github_actions=None):
            for minute in range(0, 1900):
                before = api.attempts()
                run_main(self.dir, WED_0007 + timedelta(minutes=minute), api)
                if api.attempts() > before:
                    attempt_minutes.append(minute)
        self.assertEqual(attempt_minutes, [0, 60, 420, 1860])

    def test_b15_platform_context_is_hermetic(self):
        for key in PLATFORM_KEYS:
            self.assertNotIn(key, os.environ, f"{key} leaked from the host into the tests")
        with actions(1008):
            self.assertEqual(os.environ["GITHUB_RUN_NUMBER"], "1008")
        self.assertNotIn("GITHUB_RUN_NUMBER", os.environ)
        if "TMPDIR" in os.environ:
            self.assertTrue(Path(tempfile.gettempdir()).is_dir())
        with self.assertRaises(NetworkBlocked):
            sync_mod.requests.get("https://example.invalid/")

    def test_b16_dispatches_share_the_counter(self):
        api = Api()
        runs = scheduled([1008]) + scheduled(range(1009, 1024), "workflow_dispatch") + scheduled([1024])
        attempted, _ = actions_chain(runs, api)
        automatic = [n for n, e, _ in attempted if e != "workflow_dispatch"]
        manual = [n for n, e, _ in attempted if e == "workflow_dispatch"]
        self.assertEqual(automatic, [1008, 1024], "consecutive scheduled runs were not both eligible")
        self.assertEqual(len(manual), 15, "dispatch attempts are outside the budget")
        self.assertEqual(len(automatic), 1024 // 16 - 1007 // 16)
        # Three dispatches between two eligible scheduled runs leave 12 scheduled
        # runs between them instead of 15.
        api = Api(athlete=requests.exceptions.ConnectionError("down"))
        runs = (scheduled(range(1008, 1013)) + scheduled(range(1013, 1016), "workflow_dispatch")
                + scheduled(range(1016, 1025)))
        attempted, _ = actions_chain(runs, api)
        automatic = [n for n, e, _ in attempted if e != "workflow_dispatch"]
        self.assertEqual(automatic, [1008, 1024])
        self.assertEqual(len([n for n, e, _ in runs if e == "schedule" and 1008 < n < 1024]), 12)
        # A gapless run of dispatches is entirely outside the budget.
        api = Api()
        attempted, _ = actions_chain(scheduled(range(1100, 1132), "workflow_dispatch"), api)
        self.assertEqual(len(attempted), 32)

    def test_b17_unexecuted_eligible_runs_postpone_refresh(self):
        api = Api(athlete=requests.exceptions.ConnectionError("down"))
        numbers = [n for n in range(1000, 1041) if n not in (1008, 1024)]
        attempted, _ = actions_chain(scheduled(numbers), api)
        self.assertEqual([n for n, _, _ in attempted], [1040],
                         "a run that is not a multiple of 16 stood in for a lost eligible run")

    def test_b18_out_of_order_numbers_and_reruns(self):
        api = Api(athlete=requests.exceptions.ConnectionError("down"))
        runs = [(1017, "schedule", 1), (1008, "schedule", 1), (1040, "schedule", 1),
                (1008, "schedule", 2), (1024, "schedule", 1), (1003, "schedule", 1)]
        attempted, _ = actions_chain(runs, api)
        self.assertEqual(attempted, [(1008, "schedule", 1), (1040, "schedule", 1),
                                     (1008, "schedule", 2), (1024, "schedule", 1)])
        self.assertEqual(sorted({n for n, _, a in attempted if a == 1}), [1008, 1024, 1040])
        self.assertEqual(len([r for r in attempted if r[2] > 1]), 1)

    def test_b19_custom_automatic_events_are_budgeted(self):
        for event in ("push", "repository_dispatch", None):
            with self.subTest(event=event):
                self.overdue()
                api = Api()
                with actions(1001, event=event):
                    run_main(self.dir, WED_1200, api)
                self.assertEqual(api.calls, [], f"{event} run on a held number pulled history")
                with actions(1008, event=event):
                    run_main(self.dir, WED_1200 + timedelta(minutes=30), api)
                self.assertEqual(api.started(), 1)

    def test_b20_deferral_line(self):
        self.overdue()
        with actions(1001):
            _, _, out = run_main(self.dir, WED_1200, Api())
        lines = [line for line in out.splitlines() if DEFERRED in line]
        self.assertEqual(len(lines), 1)
        line = lines[0]
        for part in ("run 1001 is not a multiple of 16", "multiples of 16",
                     "Sync Now skips only this limit", "retry backoff", "only a due file"):
            self.assertIn(part, line)
        with actions("x9TOKENSECRET"):
            _, _, out = run_main(self.dir, WED_1200, Api())
        self.assertIn("missing or not a positive integer", out)
        self.assertNotIn("TOKENSECRET", out, "a raw malformed run number was echoed")
        # Backoff is checked first: a held run that is also backing off makes no
        # request and prints no budget line.
        state = {"last_attempt_at": WED_1200.isoformat(), "consecutive_failures": 1,
                 "next_attempt_after": (WED_1200 + timedelta(minutes=30)).isoformat(),
                 "attempt_script_hash": CURRENT_HASH,
                 "last_error": {"kind": "timeout", "status": None}}
        self.overdue(refresh_state=state)
        api = Api()
        with actions(1001):
            _, _, out = run_main(self.dir, WED_1200 + timedelta(minutes=5), api)
        self.assertEqual(api.calls, [])
        self.assertNotIn(DEFERRED, out, "the budget line replaced the backoff decision")


if __name__ == "__main__":
    unittest.main()
