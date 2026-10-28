"""
Tests for the shared /streams response per activity per sync run.

Origin: written against sync.py v3.157 / Section 11 v11.92. That pairing is
provenance only.

Standard library only, synthetic fixtures, no network: the shared verb guard
blocks real requests and each test patches requests.get explicitly.

Run from the repository root:

    python3 -m unittest discover dev/tests
"""

import tempfile
import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from _harness import (SYNC_PATH, install_verb_guard, load_module_by_path,
                      restore_verb_guard)

sync_mod = load_module_by_path("s11_sync", SYNC_PATH)
IntervalsSync = sync_mod.IntervalsSync

_ORIGINAL_VERBS = {}


def setUpModule():
    global _ORIGINAL_VERBS
    _ORIGINAL_VERBS = install_verb_guard(sync_mod.requests)


def tearDownModule():
    restore_verb_guard(sync_mod.requests, _ORIGINAL_VERBS)


class FakeResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


STREAMS = [
    {"type": "time", "data": [0, 1, 2]},
    {"type": "watts", "data": [100, 200, 300]},
    {"type": "heartrate", "data": [120, 121, 122]},
    {"type": "cadence", "data": [80, 81, 82]},
    {"type": "dfa_a1", "data": [1.0, 0.9, 0.8]},
]


class StreamReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sync = IntervalsSync("athlete_test", "key_test")
        self.sync.data_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def fetch(self, aid, types):
        return self.sync._fetch_activity_streams(aid, types)

    def test_two_consumers_share_one_request(self):
        with mock.patch.object(sync_mod.requests, "get",
                               return_value=FakeResponse(200, STREAMS)) as get:
            dfa = self.fetch("a1", ["dfa_a1", "artifacts", "heartrate", "watts", "time"])
            structure = self.fetch("a1", ["time", "watts", "heartrate", "cadence"])
        self.assertEqual(get.call_count, 1)
        self.assertEqual(dfa, ("ok", {"dfa_a1": [1.0, 0.9, 0.8], "heartrate": [120, 121, 122],
                                      "watts": [100, 200, 300], "time": [0, 1, 2]}))
        self.assertEqual(structure, ("ok", {"time": [0, 1, 2], "watts": [100, 200, 300],
                                            "heartrate": [120, 121, 122], "cadence": [80, 81, 82]}))

    def test_consumers_receive_private_copies(self):
        with mock.patch.object(sync_mod.requests, "get", return_value=FakeResponse(200, STREAMS)):
            _, first = self.fetch("a1", ["watts"])
            first["watts"][0] = -1
            _, second = self.fetch("a1", ["watts"])
        self.assertEqual(second["watts"], [100, 200, 300])

    def test_no_data_for_one_consumer_does_not_hide_others(self):
        with mock.patch.object(sync_mod.requests, "get",
                               return_value=FakeResponse(200, [{"type": "watts", "data": [1]}])) as get:
            self.assertEqual(self.fetch("a1", ["dfa_a1"]), ("no_data", {}))
            self.assertEqual(self.fetch("a1", ["watts"]), ("ok", {"watts": [1]}))
        self.assertEqual(get.call_count, 1)

    def test_rate_limit_is_reused_with_retry_after(self):
        with mock.patch.object(sync_mod.requests, "get",
                               return_value=FakeResponse(429, headers={"Retry-After": "120"})) as get:
            self.assertEqual(self.fetch("a1", ["dfa_a1"]), ("transient", "http_429"))
            self.assertEqual(self.sync._last_retry_after_secs, 120)
            self.sync._last_retry_after_secs = None
            self.assertEqual(self.fetch("a1", ["watts"]), ("transient", "http_429"))
            self.assertEqual(self.sync._last_retry_after_secs, 120)
        self.assertEqual(get.call_count, 1)

    def test_retry_after_does_not_leak_to_other_activity(self):
        responses = [FakeResponse(429, headers={"Retry-After": "120"}), FakeResponse(200, STREAMS)]
        with mock.patch.object(sync_mod.requests, "get", side_effect=responses) as get:
            self.fetch("a1", ["watts"])
            self.assertEqual(self.fetch("a2", ["watts"]), ("deferred", "request_budget"))
            self.assertIsNone(self.sync._last_retry_after_secs)
        self.assertEqual(get.call_count, 1)

    def test_terminal_results_are_shared(self):
        for code in (404, 410):
            with mock.patch.object(sync_mod.requests, "get", return_value=FakeResponse(code)) as get:
                aid = "gone-%d" % code
                for types in (["watts"], ["time"], ["cadence"]):
                    self.assertEqual(self.fetch(aid, types), ("terminal_error", "http_%d" % code))
            self.assertEqual(get.call_count, 1)

    def test_other_transient_failure_allows_one_more_request(self):
        failures = [
            ("timeout", lambda: sync_mod.requests.exceptions.Timeout(), ("transient", "timeout")),
            ("server", lambda: FakeResponse(503), ("transient", "http_503")),
            ("parse", lambda: FakeResponse(200, ValueError("bad json")), ("transient", "parse_error")),
            ("shape", lambda: FakeResponse(200, {"not": "a list"}), ("transient", "unexpected_shape")),
        ]
        for name, make, expected in failures:
            with self.subTest(name=name):
                def fail(*args, **kwargs):
                    value = make()
                    if isinstance(value, Exception):
                        raise value
                    return value
                with mock.patch.object(sync_mod.requests, "get", side_effect=fail) as get:
                    for types in (["watts"], ["time"], ["cadence"]):
                        self.assertEqual(self.fetch(name, types), expected)
                self.assertEqual(get.call_count, 2)

    def test_retry_success_is_shared_with_later_consumers(self):
        with mock.patch.object(sync_mod.requests, "get",
                               side_effect=[FakeResponse(503), FakeResponse(200, STREAMS)]) as get:
            self.assertEqual(self.fetch("blip", ["dfa_a1"]), ("transient", "http_503"))
            self.assertEqual(self.fetch("blip", ["watts"]), ("ok", {"watts": [100, 200, 300]}))
            self.assertEqual(self.fetch("blip", ["time"]), ("ok", {"time": [0, 1, 2]}))
        self.assertEqual(get.call_count, 2)

    def test_retry_after_rate_limit_in_second_attempt_is_shared(self):
        with mock.patch.object(sync_mod.requests, "get",
                               side_effect=[FakeResponse(503),
                                            FakeResponse(429, headers={"Retry-After": "600"})]) as get:
            self.fetch("busy", ["watts"])
            self.assertEqual(self.fetch("busy", ["time"]), ("transient", "http_429"))
            self.assertEqual(self.sync._last_retry_after_secs, 600)
            self.sync._last_retry_after_secs = None
            self.assertEqual(self.fetch("busy", ["cadence"]), ("transient", "http_429"))
            self.assertEqual(self.sync._last_retry_after_secs, 600)
        self.assertEqual(get.call_count, 2)

    def test_new_sync_run_starts_with_empty_reuse(self):
        with mock.patch.object(sync_mod.requests, "get", return_value=FakeResponse(200, STREAMS)):
            self.fetch("a1", ["watts"])
        self.assertIn("a1", self.sync._stream_responses)

        class Stop(BaseException):
            pass

        with mock.patch.object(self.sync, "_intervals_get", side_effect=Stop()):
            with self.assertRaises(Stop):
                self.sync.collect_training_data()
        self.assertEqual(self.sync._stream_responses, {})


# -- both real consumers ----------------------------------------------------

NOW = datetime(2026, 10, 23, 12)


def clock(at):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return at.astimezone(tz) if tz else at.replace(tzinfo=None)
    return Clock


def ride():
    act = {"id": 101, "paired_event_id": 42, "type": "Ride",
           "start_date": "2026-10-23T08:00:00Z", "start_date_local": "2026-10-23T10:00:00",
           "elapsed_time": 300, "moving_time": 300, "icu_intervals": [], "name": "Synthetic"}
    event = {"id": 42, "category": "WORKOUT", "workout_doc": {"duration": 300, "steps": [
        {"duration": 100, "power": {"units": "w", "value": p}} for p in (100, 200, 300)]}}
    data = {"time": list(range(301)), "watts": [100] * 100 + [200] * 100 + [300] * 100 + [0],
            "heartrate": [120] * 301, "cadence": [90] * 301, "dfa_a1": [1.0] * 301, "artifacts": [0] * 301}
    return act, event, [{"type": k, "data": v} for k, v in data.items()]


class BothConsumersTests(unittest.TestCase):
    """_generate_intervals then _prepare_session_structures, as in collect_training_data."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sync = IntervalsSync("athlete_test", "key_test")
        self.sync.data_dir = Path(self.tmp.name)
        self.sync._cached_script_hash = "stream-reuse-test"

    def tearDown(self):
        self.tmp.cleanup()

    def new_run(self):
        prior = self.sync.request_budget
        prior.sleep(10800)
        with mock.patch.dict(os.environ, {"SECTION11_STATE_DIR": str(prior.root.parent.parent)}):
            self.sync._request_budget = sync_mod.RequestBudget(
                prior.data_dir, "sync", sync_mod.RequestBudgetRefused, self.sync._budget_identity,
                clock=prior.clock, sleep=prior.sleep, jitter=lambda: 0)
        self.assertEqual(self.sync.request_budget.root, prior.root)
        self.sync._prior_budget_scratch = prior
        class Stop(BaseException):
            pass
        with mock.patch.object(self.sync, "_intervals_get", side_effect=Stop()):
            with self.assertRaises(Stop):
                self.sync.collect_training_data()
        self.assertEqual(self.sync._stream_responses, {})

    def run_consumers(self, stream_responses, at=NOW):
        act, event, _ = ride()
        sent = []
        queue = list(stream_responses)

        def get(url, **kwargs):
            if url.endswith("/streams"):
                sent.append(url)
                return queue.pop(0)
            return FakeResponse(200, {"icu_intervals": []})
        with mock.patch.object(sync_mod, "datetime", clock(at)), \
                mock.patch.object(sync_mod.requests, "get", side_effect=get):
            self.sync._generate_intervals([act], {"101"}, [event])
            block = self.sync._prepare_session_structures(
                [act], [event], {}, at.astimezone(timezone.utc))["101"]
        return self.sync._intervals_data["fetch_state"]["101"]["streams"], block, len(sent)

    def test_success_uses_one_stream_request(self):
        state, block, sent = self.run_consumers([FakeResponse(200, ride()[2])])
        self.assertEqual(sent, 1)
        self.assertEqual(state["reason"], "ok")
        self.assertEqual(block["status"], "followed")

    def test_rate_limit_is_shared_with_both_schedules_and_cleared_next_run(self):
        state, block, sent = self.run_consumers([FakeResponse(429, headers={"Retry-After": "7200"})])
        self.assertEqual(sent, 1)
        self.assertEqual((state["status"], state["reason"]), ("pending", "transient"))
        self.assertEqual(state["next_retry_at"], (NOW + timedelta(seconds=7200)).isoformat())
        self.assertIn("streams_transient", block["issues"])
        self.assertEqual(block["cache"]["status"], "unavailable")
        self.assertEqual(block["cache"]["next_refresh_at"],
                         (NOW.astimezone(timezone.utc) + timedelta(seconds=7200)).isoformat())
        self.new_run()
        later = NOW + timedelta(hours=3)
        state, block, sent = self.run_consumers([FakeResponse(200, ride()[2])], at=later)
        self.assertEqual(sent, 1)
        self.assertEqual(state["reason"], "ok")
        self.assertEqual(block["status"], "followed")

    def test_server_blip_lets_second_consumer_recover(self):
        state, block, sent = self.run_consumers([FakeResponse(503), FakeResponse(200, ride()[2])])
        self.assertEqual(sent, 2)
        self.assertEqual((state["status"], state["reason"]), ("pending", "transient"))
        self.assertEqual(block["status"], "followed")


if __name__ == "__main__":
    unittest.main()
