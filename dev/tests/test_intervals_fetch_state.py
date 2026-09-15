"""
Tests for intervals.json per-endpoint fetch state.

Origin: written against sync.py v3.121 / Section 11 v11.53. That pairing is
provenance only. Behaviour is validated against the current sync.py, and the
current version is the target.

Standard library only: unittest and unittest.mock, no third-party test packages,
no real athlete data, no network. All fixtures are synthetic. Importing sync.py
does require `requests`, its normal runtime dependency, so these tests must run
under the interpreter or virtual environment that already runs sync.py.

Run from the repository root:

    python3 -m unittest discover dev/tests

Use the same interpreter or virtual environment that runs sync.py. There is no
`python` executable on every platform, and the interpreter that has `requests`
is the one that matters.

Several tests bind private helpers directly (_parse_retry_after, _schedule_retry,
_advance_endpoint_state, _build_pairing_map, _format_interval_segments and
_generate_intervals). That is deliberate. They are regression guards on behaviour
with no public entry point, so this suite is not implementation independent.

Covered: independent endpoint transitions, the retry ladder and its deadlines,
Retry-After handling, expiry to tombstone, sibling-only merging, state persistence
across restarts, and the write gates.
"""

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from _harness import (NetworkBlocked, REPO_ROOT, SYNC_PATH, install_verb_guard,
                      load_module_by_path, restore_verb_guard)

sync_mod = load_module_by_path("s11_sync", SYNC_PATH)
IntervalsSync = sync_mod.IntervalsSync


# ── network guard ─────────────────────────────────────────────────────

# Nothing here may reach the network. sync.py catches requests.exceptions.
# RequestException at both fetchers, so an Exception-derived guard, or a socket
# level block that requests wraps into ConnectionError, is swallowed into a
# ("transient", ...) result and the test passes without exercising anything.
# NetworkBlocked derives from BaseException so it propagates instead.
#
# Only the verb attributes are replaced: sync.py's except clauses reference
# requests.exceptions, which must stay reachable. The originals are saved here
# and installed in setUpModule, then restored in tearDownModule, so this module
# cannot contaminate another one in the same interpreter, including after a
# failing run and including during discovery's import phase.

# The verb seam and its lifecycle now live in _harness.py, shared with the other
# two modules. What stays here is the choice of seam: only the named verbs on
# sync.py's real requests module are replaced, because sync.py's fetchers
# reference requests.exceptions inside their except clauses and it must stay
# reachable. Installation is still deferred to setUpModule for the reason given
# in _harness: discovery imports every test module before running any of them.

_ORIGINAL_VERBS = {}


def setUpModule():
    """Activate the guard, but only once this module's tests are about to run."""
    global _ORIGINAL_VERBS
    _ORIGINAL_VERBS = install_verb_guard(sync_mod.requests)


def tearDownModule():
    """Put the real requests verbs back, whatever the outcome of the run."""
    restore_verb_guard(sync_mod.requests, _ORIGINAL_VERBS)


# ── helpers ──────────────────────────────────────────────────────────────────

def make_sync(tmpdir):
    """An IntervalsSync with a scratch data dir and no credentials in play."""
    s = IntervalsSync("athlete_test", "key_test")
    s.data_dir = Path(tmpdir)
    return s


def activity(act_id="a1", start=None, act_type="Ride", name="Test Ride", **extra):
    start = start or datetime.now()
    act = {
        "id": act_id,
        "start_date_local": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "type": act_type,
        "name": name,
        "interval_summary": None,
    }
    act.update(extra)
    return act


def raw_interval(**over):
    iv = {
        "type": "WORK", "group_id": "300s@250w", "elapsed_time": 300,
        "moving_time": 300, "start_time": 0, "end_time": 300,
        "average_watts": 250, "max_watts": 280, "average_heartrate": 150,
        "max_heartrate": 160, "min_heartrate": 130, "average_cadence": 90,
        "zone": 3, "zone_min_watts": 230, "zone_max_watts": 260,
        "wbal_start": 22000, "wbal_end": 20500, "training_load": 8.0,
    }
    iv.update(over)
    return iv


class FakeResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def write_cache(tmpdir, sync, activities=None, fetch_state=None, script_hash=None):
    data = {
        "generated_at": datetime.now().isoformat(),
        "schema_version": 1,
        "version": sync.VERSION,
        "script_hash": script_hash if script_hash is not None else sync.script_hash,
        "scan_hours": sync.INTERVAL_SCAN_HOURS,
        "retention_days": sync.INTERVAL_RETENTION_DAYS,
        "activities": activities or [],
        "fetch_state": fetch_state or {},
    }
    (Path(tmpdir) / sync.INTERVALS_FILE).write_text(json.dumps(data))
    return data


# ── Retry-After parsing ──────────────────────────────────────────────────────

class TestParseRetryAfter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sync = make_sync(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_delta_seconds(self):
        self.assertEqual(self.sync._parse_retry_after("120"), 120)
        self.assertEqual(self.sync._parse_retry_after(" 45 "), 45)
        self.assertEqual(self.sync._parse_retry_after(0), 0)

    def test_http_date(self):
        future = datetime.now() + timedelta(seconds=300)
        header = future.strftime("%a, %d %b %Y %H:%M:%S GMT")
        parsed = self.sync._parse_retry_after(header)
        self.assertIsNotNone(parsed)
        self.assertGreaterEqual(parsed, 0)

    def test_http_date_in_past_clamps_to_zero(self):
        past = datetime.now() - timedelta(days=1)
        header = past.strftime("%a, %d %b %Y %H:%M:%S GMT")
        self.assertEqual(self.sync._parse_retry_after(header), 0)

    def test_absent_and_garbage(self):
        for value in (None, "", "   ", "not-a-date", "-5"):
            self.assertIsNone(self.sync._parse_retry_after(value), value)


class TestRetryAfterDoesNotLeak(unittest.TestCase):
    """A 429 value must never influence the next request."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sync = make_sync(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_intervals_then_streams(self):
        with mock.patch.object(sync_mod.requests, "get",
                               return_value=FakeResponse(429, headers={"Retry-After": "900"})):
            self.sync._fetch_activity_intervals("a1")
        self.assertEqual(self.sync._last_retry_after_secs, 900)

        with mock.patch.object(sync_mod.requests, "get",
                               return_value=FakeResponse(500)):
            self.sync._fetch_activity_streams("a1", ["dfa_a1"])
        self.assertIsNone(self.sync._last_retry_after_secs,
                          "429 Retry-After leaked into a later request")

    def test_reset_on_success(self):
        with mock.patch.object(sync_mod.requests, "get",
                               return_value=FakeResponse(429, headers={"Retry-After": "60"})):
            self.sync._fetch_activity_intervals("a1")
        self.assertEqual(self.sync._last_retry_after_secs, 60)
        with mock.patch.object(sync_mod.requests, "get",
                               return_value=FakeResponse(200, {"icu_intervals": [raw_interval()]})):
            status, _ = self.sync._fetch_activity_intervals("a1")
        self.assertEqual(status, "ok")
        self.assertIsNone(self.sync._last_retry_after_secs)


# ── retry ladder and deadlines ───────────────────────────────────────────────

class TestScheduleRetry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sync = make_sync(self.tmp.name)
        self.now = datetime(2026, 8, 1, 12, 0, 0)
        self.start = self.now - timedelta(minutes=10)

    def tearDown(self):
        self.tmp.cleanup()

    def _delay(self, attempts, endpoint="intervals", paired=False, retry_after=None,
               now=None, start=None):
        nxt = self.sync._schedule_retry(endpoint, attempts, paired,
                                        start or self.start, now or self.now, retry_after)
        if nxt is None:
            return None
        return (datetime.fromisoformat(nxt) - (now or self.now)).total_seconds()

    def test_ladder_boundaries(self):
        self.assertEqual(self._delay(1), 300)
        self.assertEqual(self._delay(6), 300)
        self.assertEqual(self._delay(7), 1800)     # 6 -> 7 boundary
        self.assertEqual(self._delay(12), 1800)
        self.assertEqual(self._delay(13), 21600)   # 12 -> 13 boundary

    def test_retry_after_raises_but_never_lowers_delay(self):
        self.assertEqual(self._delay(1, retry_after=900), 900)
        self.assertEqual(self._delay(1, retry_after=10), 300)

    def test_unpaired_expires_at_72h(self):
        start = self.now - timedelta(hours=71, minutes=59)
        self.assertIsNone(self._delay(1, paired=False, start=start),
                          "next retry would land past the 72h deadline")
        old = self.now - timedelta(hours=80)
        self.assertIsNone(self._delay(1, paired=False, start=old))

    def test_paired_intervals_extend_to_retention(self):
        start = self.now - timedelta(hours=80)
        delay = self._delay(20, endpoint="intervals", paired=True, start=start)
        self.assertEqual(delay, 86400, "paired intervals should fall back to daily")

    def test_paired_expires_at_retention_limit(self):
        start = self.now - timedelta(days=14)
        self.assertIsNone(self._delay(20, endpoint="intervals", paired=True, start=start))

    def test_streams_never_get_the_extended_tier(self):
        start = self.now - timedelta(hours=80)
        self.assertIsNone(self._delay(20, endpoint="streams", paired=True, start=start),
                          "pairing must not extend the streams window")

    def test_backfill_of_old_activity_does_not_open_fresh_window(self):
        """Deadline derives from activity start, not from first_seen/now."""
        start = self.now - timedelta(days=5)
        self.assertIsNone(self._delay(1, paired=False, start=start))


class TestAdvanceEndpointState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sync = make_sync(self.tmp.name)
        self.now = datetime(2026, 8, 1, 12, 0, 0)
        self.start = self.now - timedelta(minutes=5)

    def tearDown(self):
        self.tmp.cleanup()

    def test_ok_clears_next_retry(self):
        prev = {"attempts": 3, "first_seen": "seen", "status": "pending",
                "next_retry_at": "x"}
        st = self.sync._advance_endpoint_state(prev, "intervals", "ok", "ok",
                                               self.now, self.start, False)
        self.assertEqual(st["status"], "ok")
        self.assertEqual(st["attempts"], 4)
        self.assertEqual(st["first_seen"], "seen")
        self.assertNotIn("next_retry_at", st)

    def test_pending_increments_and_schedules(self):
        st = self.sync._advance_endpoint_state(None, "intervals", "pending", "no_data",
                                               self.now, self.start, False)
        self.assertEqual(st["status"], "pending")
        self.assertEqual(st["reason"], "no_data")
        self.assertEqual(st["attempts"], 1)
        self.assertIn("next_retry_at", st)

    def test_expiry_becomes_tombstone(self):
        old_start = self.now - timedelta(days=6)
        st = self.sync._advance_endpoint_state(None, "intervals", "pending", "no_data",
                                               self.now, old_start, False)
        self.assertEqual(st["status"], "tombstone")
        self.assertEqual(st["reason"], "retry_expired")
        self.assertNotIn("next_retry_at", st)

    def test_terminal_is_immediate_tombstone(self):
        st = self.sync._advance_endpoint_state(None, "streams", "tombstone",
                                               "terminal_error", self.now, self.start, False)
        self.assertEqual(st["status"], "tombstone")
        self.assertEqual(st["reason"], "terminal_error")


# ── pairing map ──────────────────────────────────────────────────────────────

class TestPairingMap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sync = make_sync(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_event_to_activity_direction(self):
        events = [{"id": 9, "paired_activity_id": "a1", "workout_doc": {"steps": [{"x": 1}]}}]
        self.assertEqual(self.sync._build_pairing_map(events, []), {"a1"})

    def test_activity_to_event_direction(self):
        events = [{"id": 9, "workout_doc": {"steps": [{"x": 1}]}}]
        acts = [activity(act_id="a1", paired_event_id=9)]
        self.assertEqual(self.sync._build_pairing_map(events, acts), {"a1"})

    def test_empty_workout_doc_is_not_paired(self):
        events = [{"id": 9, "paired_activity_id": "a1", "workout_doc": {"steps": []}},
                  {"id": 10, "paired_activity_id": "a2"}]
        acts = [activity(act_id="a2", paired_event_id=10)]
        self.assertEqual(self.sync._build_pairing_map(events, acts), set())

    def test_no_date_or_sport_fallback(self):
        """An unpaired same-day event must never produce a match."""
        today = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        events = [{"id": 9, "start_date_local": today, "workout_doc": {"steps": [{"x": 1}]}}]
        acts = [activity(act_id="a1")]
        self.assertEqual(self.sync._build_pairing_map(events, acts), set())


# ── segment formatting / zone_basis ──────────────────────────────────────────

class TestFormatSegments(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sync = make_sync(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_power_basis_and_none_stripping(self):
        segs, basis = self.sync._format_interval_segments([raw_interval()], activity())
        self.assertEqual(basis, "power")
        self.assertNotIn("decoupling", segs[0])
        self.assertNotIn("avg_dfa_a1", segs[0])
        self.assertEqual(segs[0]["w_bal_start"], 22000)

    def test_hr_basis_when_no_watt_bounds(self):
        iv = raw_interval(zone_min_watts=None, zone_max_watts=None,
                          average_watts=None, max_watts=None, wbal_start=None, wbal_end=None)
        act = activity(icu_hr_zone_times=[0, 100, 200])
        _, basis = self.sync._format_interval_segments([iv], act)
        self.assertEqual(basis, "hr")

    def test_pace_basis_from_gap(self):
        iv = raw_interval(zone_min_watts=None, zone_max_watts=None)
        act = activity(gap_zone_times=[0, 100])
        _, basis = self.sync._format_interval_segments([iv], act)
        self.assertEqual(basis, "pace")

    def test_ambiguous_and_absent_are_omitted(self):
        iv = raw_interval(zone_min_watts=None, zone_max_watts=None)
        both = activity(icu_hr_zone_times=[0, 1], pace_zone_times=[0, 1])
        self.assertIsNone(self.sync._format_interval_segments([iv], both)[1])
        self.assertIsNone(self.sync._format_interval_segments([iv], activity())[1])

    def test_no_zone_means_no_basis(self):
        iv = raw_interval(zone=None)
        act = activity(icu_hr_zone_times=[0, 1])
        self.assertIsNone(self.sync._format_interval_segments([iv], act)[1])


# ── end-to-end _generate_intervals behaviour ─────────────────────────────────

class GenerateIntervalsCase(unittest.TestCase):
    """Drives _generate_intervals with the two fetchers stubbed."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sync = make_sync(self.tmp.name)
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def run_generate(self, acts, intervals_result, streams_result, events=None,
                     present=None):
        def fake_intervals(act_id):
            self.calls.append(("intervals", str(act_id)))
            self.sync._last_retry_after_secs = None
            return intervals_result

        def fake_streams(act_id, types):
            self.calls.append(("streams", str(act_id)))
            self.sync._last_retry_after_secs = None
            return streams_result

        with mock.patch.object(self.sync, "_fetch_activity_intervals", fake_intervals), \
             mock.patch.object(self.sync, "_fetch_activity_streams", fake_streams), \
             mock.patch.object(self.sync, "_compute_dfa_block",
                               lambda payload: {"avg": 1.0, "quality": {"sufficient": True}}):
            self.sync._generate_intervals(acts, present_activity_ids=present, events=events)
        return self.sync._intervals_data


class TestPartialSuccess(GenerateIntervalsCase):
    def test_intervals_ok_streams_transient(self):
        data = self.run_generate(
            [activity()],
            ("ok", [raw_interval()]),
            ("transient", "http_500"),
        )
        entry = data["activities"][0]
        self.assertEqual(len(entry["intervals"]), 1, "interval payload must survive")
        self.assertNotIn("dfa", entry)
        st = data["fetch_state"]["a1"]
        self.assertEqual(st["intervals"]["status"], "ok")
        self.assertEqual(st["streams"]["status"], "pending")
        self.assertEqual(st["streams"]["reason"], "transient")

    def test_intervals_no_data_streams_ok(self):
        data = self.run_generate(
            [activity()],
            ("no_data", []),
            ("ok", {"dfa_a1": [1.0, 1.1], "heartrate": [120, 121]}),
        )
        entry = data["activities"][0]
        self.assertIn("dfa", entry, "DFA payload must survive")
        self.assertEqual(entry["intervals"], [])
        st = data["fetch_state"]["a1"]
        self.assertEqual(st["intervals"]["status"], "pending")
        self.assertEqual(st["intervals"]["reason"], "no_data")
        self.assertEqual(st["streams"]["status"], "ok")


class TestStreamsSuccessSemantics(GenerateIntervalsCase):
    def test_ordinary_streams_without_dfa_is_pending(self):
        data = self.run_generate(
            [activity()],
            ("ok", [raw_interval()]),
            ("ok", {"heartrate": [120, 121], "watts": [200, 210]}),
        )
        st = data["fetch_state"]["a1"]["streams"]
        self.assertEqual(st["status"], "pending",
                         "HTTP 200 without dfa_a1 must not count as success")
        self.assertEqual(st["reason"], "no_data")
        self.assertNotIn("dfa", data["activities"][0])

    def test_compute_error_is_distinct_from_no_data(self):
        def boom(payload):
            raise ValueError("bad stream")

        def fake_intervals(act_id):
            self.sync._last_retry_after_secs = None
            return ("ok", [raw_interval()])

        def fake_streams(act_id, types):
            self.sync._last_retry_after_secs = None
            return ("ok", {"dfa_a1": [1.0]})

        with mock.patch.object(self.sync, "_fetch_activity_intervals", fake_intervals), \
             mock.patch.object(self.sync, "_fetch_activity_streams", fake_streams), \
             mock.patch.object(self.sync, "_compute_dfa_block", boom):
            self.sync._generate_intervals([activity()], present_activity_ids=None)
        st = self.sync._intervals_data["fetch_state"]["a1"]["streams"]
        self.assertEqual(st["status"], "pending")
        self.assertEqual(st["reason"], "compute_error")


class TestTransportFailures(GenerateIntervalsCase):
    def test_timeout_is_pending(self):
        data = self.run_generate([activity()], ("transient", "timeout"),
                                 ("transient", "timeout"))
        st = data["fetch_state"]["a1"]
        self.assertEqual(st["intervals"]["status"], "pending")
        self.assertEqual(st["intervals"]["reason"], "transient")
        self.assertEqual(data["activities"], [])

    def test_server_error_is_pending(self):
        data = self.run_generate([activity()], ("transient", "http_503"),
                                 ("transient", "http_503"))
        self.assertEqual(data["fetch_state"]["a1"]["intervals"]["status"], "pending")

    def test_terminal_is_tombstone(self):
        data = self.run_generate([activity()], ("terminal_error", "http_404"),
                                 ("terminal_error", "http_404"))
        st = data["fetch_state"]["a1"]
        self.assertEqual(st["intervals"]["status"], "tombstone")
        self.assertEqual(st["intervals"]["reason"], "terminal_error")


class TestDueEndpointIsolation(GenerateIntervalsCase):
    def test_only_the_due_endpoint_is_fetched(self):
        """A pending endpoint that is due must not drag its sibling along."""
        act = activity()
        past = (datetime.now() - timedelta(minutes=5)).isoformat()
        future = (datetime.now() + timedelta(hours=6)).isoformat()
        write_cache(
            self.tmp.name, self.sync,
            activities=[{"activity_id": "a1", "date": act["start_date_local"][:10],
                         "intervals": [], "dfa": {"avg": 1.0}}],
            fetch_state={"a1": {
                "date": act["start_date_local"][:10],
                "intervals": {"status": "pending", "reason": "no_data", "attempts": 2,
                              "next_retry_at": past},
                "streams": {"status": "pending", "reason": "no_data", "attempts": 1,
                            "next_retry_at": future},
            }},
        )
        data = self.run_generate([act], ("ok", [raw_interval()]), ("ok", {"dfa_a1": [1.0]}))
        self.assertEqual(self.calls, [("intervals", "a1")],
                         "only the due endpoint should be fetched")
        st = data["fetch_state"]["a1"]
        self.assertEqual(st["intervals"]["status"], "ok")
        self.assertEqual(st["streams"]["attempts"], 1, "sibling state must be untouched")
        self.assertEqual(st["streams"]["next_retry_at"], future)

    def test_not_due_means_no_fetch_at_all(self):
        act = activity()
        future = (datetime.now() + timedelta(hours=6)).isoformat()
        write_cache(
            self.tmp.name, self.sync,
            activities=[{"activity_id": "a1", "date": act["start_date_local"][:10],
                         "intervals": [raw_interval()]}],
            fetch_state={"a1": {
                "date": act["start_date_local"][:10],
                "intervals": {"status": "ok", "reason": "ok", "attempts": 1},
                "streams": {"status": "pending", "reason": "no_data", "attempts": 1,
                            "next_retry_at": future},
            }},
        )
        self.run_generate([act], ("ok", [raw_interval()]), ("ok", {"dfa_a1": [1.0]}))
        self.assertEqual(self.calls, [])


class TestSiblingOnlyMerge(GenerateIntervalsCase):
    def test_retry_replaces_only_its_own_payload(self):
        act = activity()
        past = (datetime.now() - timedelta(minutes=5)).isoformat()
        existing_dfa = {"avg": 0.87, "quality": {"sufficient": True}}
        write_cache(
            self.tmp.name, self.sync,
            activities=[{"activity_id": "a1", "date": act["start_date_local"][:10],
                         "name": "cached", "intervals": [], "dfa": existing_dfa,
                         "zone_basis": "hr"}],
            fetch_state={"a1": {
                "date": act["start_date_local"][:10],
                "intervals": {"status": "pending", "reason": "no_data", "attempts": 1,
                              "next_retry_at": past},
                "streams": {"status": "ok", "reason": "ok", "attempts": 1},
            }},
        )
        data = self.run_generate([act], ("ok", [raw_interval()]), ("ok", {"dfa_a1": [1.0]}))
        entries = [e for e in data["activities"] if str(e["activity_id"]) == "a1"]
        self.assertEqual(len(entries), 1, "must not append a duplicate activity_id")
        entry = entries[0]
        self.assertEqual(entry["dfa"], existing_dfa, "sibling DFA must be preserved")
        self.assertEqual(len(entry["intervals"]), 1)
        self.assertEqual(entry["zone_basis"], "power", "basis must be recomputed")

    def test_stale_zone_basis_removed_when_no_longer_resolvable(self):
        act = activity()
        past = (datetime.now() - timedelta(minutes=5)).isoformat()
        write_cache(
            self.tmp.name, self.sync,
            activities=[{"activity_id": "a1", "date": act["start_date_local"][:10],
                         "intervals": [{"type": "WORK"}], "zone_basis": "power"}],
            fetch_state={"a1": {
                "date": act["start_date_local"][:10],
                "intervals": {"status": "pending", "reason": "no_data", "attempts": 1,
                              "next_retry_at": past},
            }},
        )
        unresolvable = raw_interval(zone=None, zone_min_watts=None, zone_max_watts=None)
        data = self.run_generate([act], ("ok", [unresolvable]), ("ok", {"dfa_a1": [1.0]}))
        entry = [e for e in data["activities"] if str(e["activity_id"]) == "a1"][0]
        self.assertNotIn("zone_basis", entry)


class TestPersistenceAndPruning(GenerateIntervalsCase):
    def test_state_survives_restart(self):
        data = self.run_generate([activity()], ("no_data", []), ("transient", "timeout"))
        path = Path(self.tmp.name) / self.sync.INTERVALS_FILE
        path.write_text(json.dumps(data, default=str))

        reloaded = make_sync(self.tmp.name)
        on_disk = json.loads(path.read_text())
        self.assertEqual(on_disk["fetch_state"]["a1"]["intervals"]["reason"], "no_data")
        self.assertEqual(on_disk["fetch_state"]["a1"]["streams"]["reason"], "transient")
        self.assertEqual(on_disk["script_hash"], reloaded.script_hash)

    def test_script_hash_change_clears_state(self):
        act = activity()
        write_cache(self.tmp.name, self.sync,
                    activities=[{"activity_id": "a1", "date": act["start_date_local"][:10],
                                 "intervals": [raw_interval()]}],
                    fetch_state={"a1": {"date": act["start_date_local"][:10],
                                        "intervals": {"status": "ok", "attempts": 1}}},
                    script_hash="deadbeefcafe")
        data = self.run_generate([act], ("ok", [raw_interval()]), ("ok", {"dfa_a1": [1.0]}))
        self.assertEqual(self.calls, [("intervals", "a1"), ("streams", "a1")],
                         "a hash change must force a full refetch")
        self.assertEqual(data["fetch_state"]["a1"]["intervals"]["attempts"], 1)

    def test_tombstoned_activity_is_not_requeued(self):
        act = activity()
        write_cache(
            self.tmp.name, self.sync,
            fetch_state={"a1": {
                "date": act["start_date_local"][:10],
                "intervals": {"status": "tombstone", "reason": "retry_expired", "attempts": 9},
                "streams": {"status": "tombstone", "reason": "retry_expired", "attempts": 9},
            }},
        )
        self.run_generate([act], ("ok", [raw_interval()]), ("ok", {"dfa_a1": [1.0]}))
        self.assertEqual(self.calls, [])

    def test_state_pruned_by_present_activity_ids(self):
        act = activity()
        write_cache(
            self.tmp.name, self.sync,
            fetch_state={"gone": {"date": act["start_date_local"][:10],
                                  "intervals": {"status": "ok", "attempts": 1}}},
        )
        data = self.run_generate([act], ("ok", [raw_interval()]), ("ok", {"dfa_a1": [1.0]}),
                                 present=set())
        self.assertNotIn("gone", data["fetch_state"])

    def test_state_keys_normalized_to_strings(self):
        act = activity(act_id=12345)
        data = self.run_generate([act], ("ok", [raw_interval()]), ("ok", {"dfa_a1": [1.0]}))
        self.assertIn("12345", data["fetch_state"])

    def test_retry_ignores_the_scan_window(self):
        """An activity older than the 72h scan window is still retried when due."""
        old = datetime.now() - timedelta(days=5)
        act = activity(start=old)
        past = (datetime.now() - timedelta(minutes=5)).isoformat()
        write_cache(
            self.tmp.name, self.sync,
            activities=[{"activity_id": "a1", "date": old.strftime("%Y-%m-%d"),
                         "intervals": [{"type": "WORK"}]}],
            fetch_state={"a1": {
                "date": old.strftime("%Y-%m-%d"),
                "paired_planned": True,
                "intervals": {"status": "pending", "reason": "no_data", "attempts": 3,
                              "next_retry_at": past},
            }},
        )
        events = [{"id": 7, "paired_activity_id": "a1", "workout_doc": {"steps": [{"x": 1}]},
                   "start_date_local": old.strftime("%Y-%m-%dT%H:%M:%S")}]
        self.run_generate([act], ("ok", [raw_interval()]), ("ok", {"dfa_a1": [1.0]}),
                          events=events)
        self.assertIn(("intervals", "a1"), self.calls,
                      "late analysis must be recoverable outside the scan window")


class TestWriteGate(GenerateIntervalsCase):
    def test_pending_only_state_still_produces_a_file_object(self):
        data = self.run_generate([activity()], ("no_data", []),
                                 ("ok", {"heartrate": [1, 2]}))
        self.assertEqual(data["activities"], [])
        self.assertTrue(data["fetch_state"], "pending-only state must be present")
        self.assertIsNotNone(data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
