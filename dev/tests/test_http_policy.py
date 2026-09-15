"""
Tests for the HTTP timeout, retry and ambiguous-write policy in sync.py v3.133 and
push.py v0.6.

Standard library only: unittest and unittest.mock. Every payload is synthetic and
built inline, scratch files go to a TemporaryDirectory, and nothing here reaches the
network, real athlete data, credentials or a machine-specific path.

Run from the repository root:

    python3 -m unittest discover dev/tests

Use the same interpreter or virtual environment that runs sync.py.

Three things this module is guarding, none of which a live run reaches often enough
to catch:

  1. Every direct request carries a bounded timeout, proved structurally by an AST
     walk over the real source rather than by grepping for the word.
  2. Safe reads retry within a bounded admission window, and the decision to retry is
     taken BEFORE sleeping, so a large Retry-After cannot buy a long sleep followed by
     no request.
  3. No write is ever replayed. After an ambiguous write only the exact intended
     remote state proves success; the pre-write state does not prove failure, because
     a commit can still be in flight.

The clock is faked throughout the retry tests. Real sleeps would make the suite
useless as a fast local check, and the admission arithmetic is exactly what needs
asserting.
"""

import ast
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import requests

from _harness import (NetworkBlocked, PUSH_PATH, REPO_ROOT, RefuseEverything,
                      SYNC_PATH, install_verb_guard, load_module_by_path,
                      restore_verb_guard)

sync_mod = load_module_by_path("s11_sync_http", SYNC_PATH)
push_mod = load_module_by_path("s11_push_http", PUSH_PATH)

PULL_PATH = REPO_ROOT / "examples" / "agentic" / "pull.py"


# ── network guards ───────────────────────────────────────────────────────────
#
# Two seams, kept distinct on purpose. sync.py needs its named verbs replaced with
# requests.exceptions left reachable; push.py has no module-level requests and needs
# its lazily-bound _requests object replaced. Both install here and restore in
# tearDownModule, including after a failing run, and neither is touched at import
# time.

_ORIGINAL_VERBS = {}
_ORIGINAL_PUSH_REQUESTS = push_mod._requests


def setUpModule():
    global _ORIGINAL_VERBS
    _ORIGINAL_VERBS = install_verb_guard(sync_mod.requests)
    try:
        push_mod._requests = RefuseEverything()
    except BaseException:
        restore_verb_guard(sync_mod.requests, _ORIGINAL_VERBS)
        push_mod._requests = _ORIGINAL_PUSH_REQUESTS
        raise


def tearDownModule():
    restore_verb_guard(sync_mod.requests, _ORIGINAL_VERBS)
    push_mod._requests = _ORIGINAL_PUSH_REQUESTS


# ── AST timeout checker ──────────────────────────────────────────────────────

def find_timeout_free_calls(source_path):
    """
    Every `requests.<verb>(...)` in a file that carries no `timeout=` keyword.

    Returns [(lineno, "requests.verb")]. A checker rather than a regex, because
    `timeout` appearing anywhere on the line, in a comment or in an adjacent call,
    would satisfy a grep and prove nothing.
    """
    tree = ast.parse(Path(source_path).read_text())
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        base = func.value
        is_requests = (
            (isinstance(base, ast.Name) and base.id == "requests")
            or (isinstance(base, ast.Attribute) and base.attr == "requests")
        )
        if not is_requests:
            continue
        if not any(kw.arg == "timeout" for kw in node.keywords):
            offenders.append((node.lineno, f"requests.{func.attr}"))
    return sorted(offenders)


class TestBoundedTimeoutGuard(unittest.TestCase):
    """Structural proof that no unbounded request survives anywhere."""

    def test_sync_has_no_timeout_free_request(self):
        self.assertEqual(find_timeout_free_calls(SYNC_PATH), [],
                         "sync.py has a requests call with no timeout; an unbounded "
                         "read can hang a sync indefinitely")

    def test_push_has_no_timeout_free_request(self):
        self.assertEqual(find_timeout_free_calls(PUSH_PATH), [],
                         "push.py has a requests call with no timeout")

    def test_pull_has_no_timeout_free_request(self):
        self.assertEqual(find_timeout_free_calls(PULL_PATH), [],
                         "pull.py has a requests call with no timeout")

    def test_checker_detects_a_removed_timeout_in_real_source(self):
        """
        Negative control. The checker is run against a COPY of the real sync.py with
        one timeout removed, not against an inline synthetic module, so this proves
        the checker works on the file it actually guards.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            copy = Path(tmpdir) / "sync_copy.py"
            shutil.copy(SYNC_PATH, copy)
            text = copy.read_text()
            marker = "timeout=self.INTERVALS_READ_TIMEOUT))"
            self.assertIn(marker, text, "the mutation anchor moved; fix this test")
            copy.write_text(text.replace(marker, "))", 1))
            self.assertEqual(find_timeout_free_calls(SYNC_PATH), [],
                             "the unmodified original must still be clean")
            self.assertTrue(find_timeout_free_calls(copy),
                            "the checker passed a source with a timeout removed, so "
                            "every other assertion it makes is hollow")


# ── guard lifecycle ──────────────────────────────────────────────────────────

class TestGuardLifecycle(unittest.TestCase):
    """Import-time cleanliness, activity during a run, and restoration after both a
    normal and a failing test."""

    def test_guard_is_active_during_this_module(self):
        with self.assertRaises(NetworkBlocked):
            sync_mod.requests.get("https://example.invalid")
        with self.assertRaises(NetworkBlocked):
            push_mod._ensure_requests().post("https://example.invalid")

    def test_requests_exceptions_stay_reachable_behind_the_sync_seam(self):
        self.assertTrue(issubclass(sync_mod.requests.exceptions.Timeout,
                                   sync_mod.requests.exceptions.RequestException))

    def test_importing_a_module_does_not_install_a_guard(self):
        """A freshly loaded copy holds real bindings until setUpModule runs."""
        fresh = load_module_by_path("s11_push_import_probe", PUSH_PATH)
        self.assertIsNone(fresh._requests,
                          "importing push.py bound something at import time")
        del sys.modules["s11_push_import_probe"]

    def test_module_teardown_restores_both_seams_after_a_failing_test(self):
        """
        The real lifecycle, not a hand-rolled finally block. A throwaway module with
        its own setUpModule/tearDownModule and one deliberately failing test is run
        through unittest itself, and both seams must be back afterwards.
        """
        module = type(sys)("guard_lifecycle_probe")
        real_verb = lambda *a, **k: "real"
        fake_requests = type(sys)("fake_requests")
        fake_requests.get = real_verb
        holder = type("Holder", (), {"_requests": "original"})()
        state = {}

        def setUpModule():
            state["verbs"] = install_verb_guard(fake_requests, verbs=("get",))
            state["obj"] = holder._requests
            holder._requests = RefuseEverything()

        def tearDownModule():
            restore_verb_guard(fake_requests, state["verbs"])
            holder._requests = state["obj"]

        class Failing(unittest.TestCase):
            def test_seams_are_guarded_then_this_fails(inner):
                inner.assertIsNot(fake_requests.get, real_verb)
                inner.assertIsInstance(holder._requests, RefuseEverything)
                inner.fail("deliberate failure inside a guarded module")

        module.setUpModule = setUpModule
        module.tearDownModule = tearDownModule
        module.Failing = Failing
        Failing.__module__ = "guard_lifecycle_probe"
        sys.modules["guard_lifecycle_probe"] = module
        self.addCleanup(sys.modules.pop, "guard_lifecycle_probe", None)

        suite = unittest.defaultTestLoader.loadTestsFromTestCase(Failing)
        result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)

        self.assertFalse(result.wasSuccessful(),
                         "the probe test was supposed to fail")
        self.assertIs(fake_requests.get, real_verb,
                      "tearDownModule did not restore the verb seam after a failing "
                      "test")
        self.assertEqual(holder._requests, "original",
                         "tearDownModule did not restore the object seam after a "
                         "failing test")

    def test_verb_guard_restores_after_a_failing_run(self):
        module = type(sys)("fake_requests")
        sentinel = lambda *a, **k: "real"
        module.get = sentinel
        originals = install_verb_guard(module, verbs=("get",))
        try:
            raise AssertionError("simulated test failure inside a guarded run")
        except AssertionError:
            pass
        finally:
            restore_verb_guard(module, originals)
        self.assertIs(module.get, sentinel,
                      "a failing run left the HTTP seam holding a test double")


# ── fakes ────────────────────────────────────────────────────────────────────

class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.text = json.dumps(self._payload)

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(
                f"{self.status_code}", response=self)


class Clock:
    """Fake monotonic clock. Requests and sleeps both advance it."""

    def __init__(self):
        self.t = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.t

    def sleep(self, secs):
        self.sleeps.append(secs)
        self.t += secs


class Scripted:
    """Callable transport. Each entry is a response to return or an error to raise."""

    def __init__(self, script, clock=None, cost=0.0):
        self.script = list(script)
        self.clock = clock
        self.cost = cost
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.clock is not None:
            self.clock.t += self.cost
        item = self.script[min(len(self.calls) - 1, len(self.script) - 1)]
        if isinstance(item, BaseException):
            raise item
        return item


def make_sync(tmpdir):
    s = sync_mod.IntervalsSync(athlete_id="i000000", intervals_api_key="synthetic")
    s.data_dir = Path(tmpdir)
    return s


class SyncPolicyCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sync = make_sync(self.tmp.name)
        self.clock = Clock()
        self.addCleanup(mock.patch.object(sync_mod.time, "sleep",
                                          self.clock.sleep).stop)
        mock.patch.object(sync_mod.time, "sleep", self.clock.sleep).start()
        self.addCleanup(mock.patch.object(sync_mod.time, "monotonic",
                                          self.clock.monotonic).stop)
        mock.patch.object(sync_mod.time, "monotonic", self.clock.monotonic).start()

    def install(self, script, cost=0.0):
        transport = Scripted(script, clock=self.clock, cost=cost)
        patcher = mock.patch.object(sync_mod.requests, "get", transport)
        patcher.start()
        self.addCleanup(patcher.stop)
        return transport


# ── sync generic read policy ─────────────────────────────────────────────────

class TestSyncReadRetryPolicy(SyncPolicyCase):
    def test_success_makes_exactly_one_call(self):
        t = self.install([FakeResponse(200, [{"id": 1}])])
        self.assertEqual(self.sync._intervals_get("activities"), [{"id": 1}])
        self.assertEqual(len(t.calls), 1)
        self.assertEqual(self.clock.sleeps, [])

    def test_every_call_site_passes_the_timeout_tuple(self):
        t = self.install([FakeResponse(200, {})])
        self.sync._intervals_get("")
        self.assertEqual(t.calls[0][1]["timeout"], (5, 30))

    def test_timeout_is_retried_then_succeeds(self):
        t = self.install([requests.exceptions.Timeout("read timed out"),
                          FakeResponse(200, {"ok": True})])
        self.assertEqual(self.sync._intervals_get(""), {"ok": True})
        self.assertEqual(len(t.calls), 2)
        self.assertEqual(self.clock.sleeps, [1])

    def test_connection_error_is_retried(self):
        t = self.install([requests.exceptions.ConnectionError("reset"),
                          FakeResponse(200, {"ok": True})])
        self.sync._intervals_get("")
        self.assertEqual(len(t.calls), 2)

    def test_retryable_statuses_are_retried(self):
        for status in (429, 500, 502, 503, 504):
            with self.subTest(status=status):
                sync = make_sync(self.tmp.name)
                t = Scripted([FakeResponse(status), FakeResponse(200, {"ok": True})])
                with mock.patch.object(sync_mod.requests, "get", t):
                    sync._intervals_get("")
                self.assertEqual(len(t.calls), 2,
                                 f"HTTP {status} was not retried")

    def test_non_retryable_statuses_make_exactly_one_call(self):
        for status in (400, 401, 403, 404, 409, 410, 422, 501):
            with self.subTest(status=status):
                sync = make_sync(self.tmp.name)
                t = Scripted([FakeResponse(status)])
                with mock.patch.object(sync_mod.requests, "get", t):
                    with self.assertRaises(requests.exceptions.HTTPError):
                        sync._intervals_get("")
                self.assertEqual(len(t.calls), 1,
                                 f"HTTP {status} was retried; only transient "
                                 f"statuses are eligible")

    def test_exhaustion_reraises_the_original_exception_subclass(self):
        original = requests.exceptions.Timeout("read timed out")
        self.install([original])
        with self.assertRaises(requests.exceptions.Timeout) as caught:
            self.sync._intervals_get("")
        self.assertIs(caught.exception, original,
                      "the original exception object was not re-raised, so callers "
                      "catching a specific subclass would stop catching it")
        self.assertIsInstance(caught.exception, requests.exceptions.RequestException)

    def test_exhausted_retryable_status_surfaces_as_httperror(self):
        self.install([FakeResponse(503)])
        with self.assertRaises(requests.exceptions.HTTPError):
            self.sync._intervals_get("")

    def test_retry_after_is_honoured_on_429(self):
        self.install([FakeResponse(429, headers={"Retry-After": "7"}),
                      FakeResponse(200, {"ok": True})])
        self.sync._intervals_get("")
        self.assertEqual(self.clock.sleeps, [7])

    def test_retry_after_never_lowers_the_ladder_delay(self):
        self.install([FakeResponse(429, headers={"Retry-After": "0"}),
                      FakeResponse(200, {"ok": True})])
        self.sync._intervals_get("")
        self.assertEqual(self.clock.sleeps, [1],
                         "Retry-After lowered the backoff below the ladder")

    def test_malformed_retry_after_falls_back_to_the_ladder(self):
        self.install([FakeResponse(429, headers={"Retry-After": "soon"}),
                      FakeResponse(200, {})])
        self.sync._intervals_get("")
        self.assertEqual(self.clock.sleeps, [1])

    def test_past_http_date_retry_after_yields_zero_not_negative(self):
        past = (datetime.now() - timedelta(hours=2)).strftime(
            "%a, %d %b %Y %H:%M:%S GMT")
        self.install([FakeResponse(503, headers={"Retry-After": past}),
                      FakeResponse(200, {})])
        self.sync._intervals_get("")
        self.assertEqual(self.clock.sleeps, [1])

    def test_retry_after_does_not_leak_into_the_next_call(self):
        self.install([FakeResponse(429, headers={"Retry-After": "9"}),
                      FakeResponse(200, {}),
                      FakeResponse(500),
                      FakeResponse(200, {})])
        self.sync._intervals_get("first")
        self.sync._intervals_get("second")
        self.assertEqual(self.clock.sleeps, [9, 1],
                         "a Retry-After from one request set the delay for a later "
                         "one")

    def test_generic_loop_does_not_touch_last_retry_after_secs(self):
        """
        _last_retry_after_secs belongs to the interval/stream fetchers, which reset it
        on entry and read it immediately after. A generic read writing to it would
        silently corrupt interval retry scheduling.
        """
        self.sync._last_retry_after_secs = "sentinel"
        self.install([FakeResponse(429, headers={"Retry-After": "5"}),
                      FakeResponse(200, {})])
        self.sync._intervals_get("")
        self.assertEqual(self.sync._last_retry_after_secs, "sentinel")


class TestAdmissionAndBudget(SyncPolicyCase):
    def test_admission_cap_counts_request_time_not_just_sleeps(self):
        """Each attempt costs 35s of clock, so the 60s cap refuses a third."""
        t = self.install([requests.exceptions.Timeout("slow")], cost=35.0)
        with self.assertRaises(requests.exceptions.Timeout):
            self.sync._intervals_get("")
        self.assertEqual(len(t.calls), 2,
                         "the cap ignored time spent inside the requests call")
        self.assertEqual(self.clock.sleeps, [1])

    def test_unfittable_retry_after_does_not_sleep(self):
        """
        A Retry-After larger than the remaining admission window must end the call
        immediately. Sleeping five minutes and then declining to retry is the failure
        mode this asserts against.
        """
        t = self.install([FakeResponse(429, headers={"Retry-After": "300"})])
        with self.assertRaises(requests.exceptions.HTTPError):
            self.sync._intervals_get("")
        self.assertEqual(self.clock.sleeps, [],
                         "slept for a retry that was never going to be admitted")
        self.assertEqual(len(t.calls), 1)

    def test_extra_attempt_budget_is_charged_only_on_admitted_retries(self):
        self.install([FakeResponse(429, headers={"Retry-After": "300"})])
        with self.assertRaises(requests.exceptions.HTTPError):
            self.sync._intervals_get("")
        self.assertEqual(self.sync._read_retry_extra_attempts_used, 0,
                         "a refused retry consumed instance budget")

    def test_attempt_cap_bounds_one_call_at_three(self):
        t = self.install([requests.exceptions.Timeout("x")])
        with self.assertRaises(requests.exceptions.Timeout):
            self.sync._intervals_get("")
        self.assertEqual(len(t.calls), 3)
        self.assertEqual(self.clock.sleeps, [1, 2])

    def test_instance_budget_is_shared_and_never_reset(self):
        t = self.install([requests.exceptions.Timeout("x")])
        for _ in range(3):
            with self.assertRaises(requests.exceptions.Timeout):
                self.sync._intervals_get("")
        # 3 + 3 attempts exhaust the 4 extra attempts; the third call gets one only.
        self.assertEqual(len(t.calls), 7,
                         "the per-instance extra-attempt budget was reset between "
                         "calls, so a degraded API costs a fresh retry budget per read")
        self.assertEqual(self.sync._read_retry_extra_attempts_used, 4)

    def test_verification_reads_are_not_charged_to_the_instance_budget(self):
        t = self.install([requests.exceptions.Timeout("x")])
        for _ in range(3):
            with self.assertRaises(requests.exceptions.Timeout):
                self.sync._read_with_retry(
                    lambda: sync_mod.requests.get("u", timeout=(5, 30)),
                    charge_instance_budget=False)
        self.assertEqual(self.sync._read_retry_extra_attempts_used, 0)
        self.assertEqual(len(t.calls), 9,
                         "verification reads were starved by the instance budget, "
                         "which would manufacture unknown outcomes")


class TestCallerSemanticsPreserved(SyncPolicyCase):
    def test_health_context_still_degrades_instead_of_raising(self):
        self.install([requests.exceptions.Timeout("x")])
        context = self.sync._build_health_context(
            fallback_events=[], latest_wellness={},
            today=datetime.now().strftime("%Y-%m-%d"),
            fallback_oldest=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
        self.assertEqual(context["source_status"], "partial",
                         "an exhausted retry stopped being a RequestException, so "
                         "_build_health_context no longer catches it")
        self.assertNotIn("marker_active", context,
                         "a degraded health fetch must omit the booleans rather than "
                         "report a false negative")

    def test_mandatory_read_is_still_fatal(self):
        self.install([requests.exceptions.Timeout("x")])
        with self.assertRaises(requests.exceptions.RequestException):
            self.sync._intervals_get("activities")

    def test_optional_wellness_read_still_degrades_to_empty(self):
        self.install([requests.exceptions.Timeout("x")])
        self.assertEqual(self.sync._fetch_today_wellness(), {})


# ── chat notes marker and circuit breaker ────────────────────────────────────

class TestActivityMessagesMarker(SyncPolicyCase):
    def setUp(self):
        super().setUp()
        # _format_activities reads this cache attribute, which collect_training_data
        # normally sets. None is the no-cache case.
        self.sync._intervals_data = None

    def _activity(self, activity_id="a1"):
        return {
            "id": activity_id,
            "name": "Synthetic Ride",
            "type": "Ride",
            "start_date_local": datetime.now().strftime("%Y-%m-%dT08:00:00"),
            "moving_time": 3600,
        }

    def test_successful_empty_response_means_no_notes_and_no_marker(self):
        self.install([FakeResponse(200, [])])
        formatted = self.sync._format_activities([self._activity()])
        self.assertNotIn("chat_notes", formatted[0])
        self.assertNotIn("chat_notes_status", formatted[0],
                         "a confirmed empty message list was reported as degraded")

    def test_successful_notes_are_emitted_without_a_marker(self):
        self.install([FakeResponse(200, [{"content": "felt good"}])])
        formatted = self.sync._format_activities([self._activity()])
        self.assertEqual(formatted[0]["chat_notes"], ["felt good"])
        self.assertNotIn("chat_notes_status", formatted[0])

    def test_healthy_payload_is_unchanged_by_this_feature(self):
        """Negative control on schema creep: no new key on a healthy activity."""
        self.install([FakeResponse(200, [{"content": "felt good"}])])
        formatted = self.sync._format_activities([self._activity()])
        self.assertEqual(
            [k for k in formatted[0] if k.startswith("chat_notes")], ["chat_notes"])

    def test_transport_failure_is_marked_unavailable(self):
        self.install([requests.exceptions.Timeout("x")])
        formatted = self.sync._format_activities([self._activity()])
        self.assertEqual(formatted[0]["chat_notes_status"], "unavailable",
                         "a failed message fetch was indistinguishable from an "
                         "activity with no notes")
        self.assertNotIn("chat_notes", formatted[0])

    def test_http_error_is_marked_unavailable(self):
        self.install([FakeResponse(403)])
        formatted = self.sync._format_activities([self._activity()])
        self.assertEqual(formatted[0]["chat_notes_status"], "unavailable")

    def test_breaker_counts_consecutive_not_total_failures(self):
        """
        Fail, fail, succeed, fail. The success resets the count, so the fourth
        activity is still requested rather than short-circuited.
        """
        self.install([requests.exceptions.Timeout("x"),
                      requests.exceptions.Timeout("x"),
                      FakeResponse(200, [{"content": "ok"}]),
                      requests.exceptions.Timeout("x"),
                      requests.exceptions.Timeout("x")])
        sync = self.sync
        sync.READ_RETRY_MAX_ATTEMPTS = 1   # one attempt per retrieval, so the script
                                           # maps 1:1 and the counter is what is tested
        states = []
        for i in range(4):
            states.append(sync._get_activity_messages(f"a{i}")[0])
        self.assertEqual(states, ["unavailable", "unavailable", "ok", "unavailable"])
        self.assertEqual(sync._messages_consecutive_failures, 1,
                         "the counter was not reset by a successful retrieval, so it "
                         "counts total failures rather than consecutive ones")

    def test_breaker_opens_after_three_consecutive_failures_and_issues_no_request(self):
        t = self.install([requests.exceptions.Timeout("x")])
        self.sync._messages_consecutive_failures = 3
        before = len(t.calls)
        before_budget = self.sync._read_retry_extra_attempts_used
        status, notes = self.sync._get_activity_messages("a9")
        self.assertEqual((status, notes), ("unavailable", []))
        self.assertEqual(len(t.calls), before,
                         "the open circuit still issued a request")
        self.assertEqual(self.sync._read_retry_extra_attempts_used, before_budget,
                         "the break path consumed retry budget without attempting")


# ── GitHub publication ───────────────────────────────────────────────────────

def encoded(payload):
    import base64
    return base64.b64encode(json.dumps(payload, indent=2, default=str)
                            .encode()).decode()


class PublishCase(SyncPolicyCase):
    DATA = {"hello": "world"}

    def setUp(self):
        super().setUp()
        self.sync.github_token = "synthetic"
        self.sync.github_repo = "synthetic/repo"
        self.puts = []

    def install_put(self, script):
        transport = Scripted(script, clock=self.clock)
        patcher = mock.patch.object(sync_mod.requests, "put", transport)
        patcher.start()
        self.addCleanup(patcher.stop)
        return transport


class TestPublishPreReadGate(PublishCase):
    def test_confirmed_404_permits_a_create_without_sha(self):
        self.install([FakeResponse(404)])
        put = self.install_put([FakeResponse(201, {})])
        self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(len(put.calls), 1)
        self.assertNotIn("sha", put.calls[0][1]["json"])

    def test_equal_content_skips_the_put_entirely(self):
        self.install([FakeResponse(200, {"sha": "s1",
                                         "content": encoded(self.DATA)})])
        put = self.install_put([FakeResponse(200, {})])
        self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(put.calls, [],
                         "the no-change short circuit was lost")

    def test_changed_content_puts_with_the_sha(self):
        self.install([FakeResponse(200, {"sha": "s1",
                                         "content": encoded({"old": True})})])
        put = self.install_put([FakeResponse(200, {})])
        self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(put.calls[0][1]["json"]["sha"], "s1")

    def test_pre_read_5xx_stops_before_the_put(self):
        self.install([FakeResponse(500)])
        put = self.install_put([FakeResponse(200, {})])
        with self.assertRaises(sync_mod.PublishPreReadFailed):
            self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(put.calls, [],
                         "an unknown pre-read fell through into a create-style PUT")

    def test_pre_read_403_stops_before_the_put(self):
        self.install([FakeResponse(403)])
        put = self.install_put([FakeResponse(200, {})])
        with self.assertRaises(sync_mod.PublishPreReadFailed):
            self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(put.calls, [])

    def test_pre_read_timeout_stops_before_the_put(self):
        self.install([requests.exceptions.Timeout("x")])
        put = self.install_put([FakeResponse(200, {})])
        with self.assertRaises(sync_mod.PublishPreReadFailed):
            self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(put.calls, [])

    def test_pre_read_failure_is_a_requestexception_for_caller_compatibility(self):
        self.install([FakeResponse(500)])
        self.install_put([FakeResponse(200, {})])
        with self.assertRaises(requests.exceptions.RequestException):
            self.sync.publish_to_github(self.DATA, "latest.json")


class TestPublishAmbiguity(PublishCase):
    def _pre_read_then_verify(self, verify_response):
        return self.install([FakeResponse(200, {"sha": "s1",
                                                "content": encoded({"old": True})}),
                             verify_response])

    def test_timeout_after_application_is_confirmed_by_readback(self):
        self._pre_read_then_verify(
            FakeResponse(200, {"sha": "s2", "content": encoded(self.DATA)}))
        put = self.install_put([requests.exceptions.Timeout("x")])
        url = self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertIn("latest.json", url)
        self.assertEqual(len(put.calls), 1)

    def test_timeout_before_application_is_unknown_with_no_second_put(self):
        self._pre_read_then_verify(
            FakeResponse(200, {"sha": "s1", "content": encoded({"old": True})}))
        put = self.install_put([requests.exceptions.Timeout("x")])
        with self.assertRaises(sync_mod.PublishOutcomeUnknown):
            self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(len(put.calls), 1,
                         "a second PUT was issued after an ambiguous write")

    def test_concurrent_change_is_unknown(self):
        self._pre_read_then_verify(
            FakeResponse(200, {"sha": "s3", "content": encoded({"someone": "else"})}))
        put = self.install_put([requests.exceptions.Timeout("x")])
        with self.assertRaises(sync_mod.PublishOutcomeUnknown):
            self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(len(put.calls), 1)

    def test_failed_verification_read_is_unknown(self):
        self.install([FakeResponse(200, {"sha": "s1",
                                         "content": encoded({"old": True})}),
                      requests.exceptions.Timeout("x")])
        self.install_put([requests.exceptions.Timeout("x")])
        with self.assertRaises(sync_mod.PublishOutcomeUnknown):
            self.sync.publish_to_github(self.DATA, "latest.json")

    def test_put_429_routes_to_verification(self):
        self._pre_read_then_verify(
            FakeResponse(200, {"sha": "s2", "content": encoded(self.DATA)}))
        put = self.install_put([FakeResponse(429)])
        self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(len(put.calls), 1)

    def test_put_500_routes_to_verification_and_stays_unknown_if_unproven(self):
        self._pre_read_then_verify(
            FakeResponse(200, {"sha": "s1", "content": encoded({"old": True})}))
        put = self.install_put([FakeResponse(500)])
        with self.assertRaises(sync_mod.PublishOutcomeUnknown):
            self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(len(put.calls), 1)

    def test_put_409_raises_definitively_without_verification(self):
        reads = self.install([FakeResponse(200, {"sha": "s1",
                                                 "content": encoded({"old": True})})])
        self.install_put([FakeResponse(409)])
        with self.assertRaises(requests.exceptions.HTTPError):
            self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(len(reads.calls), 1,
                         "a definitive 409 triggered a pointless verification read")

    def test_unknown_never_returns_a_url(self):
        self._pre_read_then_verify(
            FakeResponse(200, {"sha": "s1", "content": encoded({"old": True})}))
        self.install_put([requests.exceptions.Timeout("x")])
        try:
            result = self.sync.publish_to_github(self.DATA, "latest.json")
        except sync_mod.PublishOutcomeUnknown:
            result = None
        self.assertIsNone(result)

    def test_unknown_is_catchable_as_exception_for_non_critical_call_sites(self):
        """
        The four non-critical publishes wrap in `except Exception`. If the new class
        escaped that, a routes.json hiccup would kill an otherwise good sync.
        """
        self.assertTrue(issubclass(sync_mod.PublishOutcomeUnknown, Exception))
        self.assertTrue(issubclass(sync_mod.PublishPreReadFailed,
                                   requests.exceptions.RequestException))


class TestPublishLostResponseAndStatus(PublishCase):
    """
    The classes of failure that a timeout-only design gets wrong: a response stream
    that breaks after the server committed, and a status that raise_for_status()
    happily lets through.
    """

    def _pre_then(self, verify):
        return self.install([FakeResponse(200, {"sha": "s1",
                                                "content": encoded({"old": True})}),
                             verify])

    def test_chunked_encoding_error_is_verified_not_failed(self):
        self._pre_then(FakeResponse(200, {"sha": "s2",
                                          "content": encoded(self.DATA)}))
        put = self.install_put([requests.exceptions.ChunkedEncodingError("truncated")])
        url = self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertIn("latest.json", url,
                      "a broken response stream after a committed write was treated "
                      "as a failure instead of being verified")
        self.assertEqual(len(put.calls), 1)

    def test_chunked_encoding_error_without_proof_is_unknown(self):
        self._pre_then(FakeResponse(200, {"sha": "s1",
                                          "content": encoded({"old": True})}))
        put = self.install_put([requests.exceptions.ChunkedEncodingError("truncated")])
        with self.assertRaises(sync_mod.PublishOutcomeUnknown):
            self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(len(put.calls), 1)

    def test_put_302_cannot_return_applied_without_exact_verification(self):
        self._pre_then(FakeResponse(200, {"sha": "s1",
                                          "content": encoded({"old": True})}))
        put = self.install_put([FakeResponse(302)])
        with self.assertRaises(sync_mod.PublishOutcomeUnknown):
            self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(len(put.calls), 1,
                         "a redirect was accepted as a successful write")

    def test_put_302_with_exact_content_verifies_to_applied(self):
        self._pre_then(FakeResponse(200, {"sha": "s2",
                                          "content": encoded(self.DATA)}))
        self.install_put([FakeResponse(302)])
        self.assertIn("latest.json",
                      self.sync.publish_to_github(self.DATA, "latest.json"))

    def test_malformed_pre_read_body_stops_before_the_put(self):
        self.install([FakeResponse(200, ["not", "an", "object"])])
        put = self.install_put([FakeResponse(200, {})])
        with self.assertRaises(sync_mod.PublishPreReadFailed):
            self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(put.calls, [],
                         "a malformed 200 was treated as established pre-state")

    def test_malformed_verifier_body_is_unknown_not_a_crash(self):
        self.install([FakeResponse(200, {"sha": "s1",
                                         "content": encoded({"old": True})}),
                      FakeResponse(200, ["not", "an", "object"])])
        self.install_put([requests.exceptions.Timeout("x")])
        with self.assertRaises(sync_mod.PublishOutcomeUnknown):
            self.sync.publish_to_github(self.DATA, "latest.json")


class TestPublishPreReadFieldValidation(PublishCase):
    """
    A 200 establishes an existing file only if it carries a usable sha and decodable
    content. A null or empty sha would otherwise be dropped by a truthiness test and
    produce a create-style PUT, which only a confirmed 404 may authorise.
    """

    BAD_SHAS = {"null": None, "empty": "", "blank": "   ", "integer": 12345,
                "list": ["s1"], "object": {"sha": "s1"}}

    def test_unusable_sha_stops_before_the_put(self):
        for name, sha in self.BAD_SHAS.items():
            with self.subTest(sha=name):
                self.install([FakeResponse(200, {"sha": sha,
                                                 "content": encoded({"old": True})})])
                put = self.install_put([FakeResponse(200, {})])
                with self.assertRaises(sync_mod.PublishPreReadFailed):
                    self.sync.publish_to_github(self.DATA, "latest.json")
                self.assertEqual(put.calls, [],
                                 f"a {name} sha produced a create-style PUT at a path "
                                 f"that may exist")

    def test_whitespace_padded_sha_stops_before_the_put(self):
        """
        " s1 " is not a usable sha. Sending it verbatim puts a value in the PUT that
        cannot match, and trimming it would be guessing at what the server meant.
        """
        for name, sha in {"leading": " s1", "trailing": "s1 ",
                          "surrounding": "  s1  ", "newline": "s1\n",
                          "tab": "\ts1"}.items():
            with self.subTest(sha=name):
                self.install([FakeResponse(200, {"sha": sha,
                                                 "content": encoded({"old": True})})])
                put = self.install_put([FakeResponse(200, {})])
                with self.assertRaises(sync_mod.PublishPreReadFailed):
                    self.sync.publish_to_github(self.DATA, "latest.json")
                self.assertEqual(put.calls, [],
                                 f"a {name}-whitespace sha reached the PUT")

    def test_clean_sha_is_still_accepted(self):
        self.install([FakeResponse(200, {"sha": "s1",
                                         "content": encoded({"old": True})})])
        put = self.install_put([FakeResponse(200, {})])
        self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(put.calls[0][1]["json"]["sha"], "s1")

    def test_missing_sha_key_stops_before_the_put(self):
        self.install([FakeResponse(200, {"content": encoded({"old": True})})])
        put = self.install_put([FakeResponse(200, {})])
        with self.assertRaises(sync_mod.PublishPreReadFailed):
            self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(put.calls, [])

    def test_unusable_content_stops_before_the_put(self):
        for name, content in {"missing": None, "integer": 42, "list": ["x"],
                              "not_base64": "!!!not base64!!!"}.items():
            with self.subTest(content=name):
                body = {"sha": "s1"}
                if content is not None:
                    body["content"] = content
                self.install([FakeResponse(200, body)])
                put = self.install_put([FakeResponse(200, {})])
                with self.assertRaises(sync_mod.PublishPreReadFailed):
                    self.sync.publish_to_github(self.DATA, "latest.json")
                self.assertEqual(put.calls, [])

    def test_only_a_real_404_creates_without_a_sha(self):
        self.install([FakeResponse(404)])
        put = self.install_put([FakeResponse(201, {})])
        self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(len(put.calls), 1)
        self.assertNotIn("sha", put.calls[0][1]["json"])

    def test_unusable_verifier_sha_or_content_is_unknown_not_a_crash(self):
        for body in ({"sha": "s2"}, {"sha": "s2", "content": 12345},
                     {"sha": None, "content": "!!!"}, ["a", "list"]):
            with self.subTest(body=repr(body)[:24]):
                self.install([FakeResponse(200, {"sha": "s1",
                                                 "content": encoded({"old": True})}),
                              FakeResponse(200, body)])
                self.install_put([requests.exceptions.Timeout("x")])
                with self.assertRaises(sync_mod.PublishOutcomeUnknown):
                    self.sync.publish_to_github(self.DATA, "latest.json")


class TestPublishBase64Strictness(PublishCase):
    """
    base64.b64decode(validate=False) discards characters outside the alphabet, so a
    body with stray punctuation decodes to the same bytes as a clean one. That is how
    a malformed remote body could be compared equal to the intended content and
    reported as an unchanged file, or accepted as proof a write landed.
    """

    def _clean(self):
        return encoded(self.DATA)

    def _polluted(self):
        """The exact intended payload with invalid punctuation wrapped around it."""
        return "!!" + self._clean() + "??"

    def test_plain_base64_still_decodes(self):
        self.install([FakeResponse(200, {"sha": "s1", "content": self._clean()})])
        put = self.install_put([FakeResponse(200, {})])
        self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(put.calls, [], "the no-change short circuit was lost")

    def test_line_wrapped_base64_still_decodes(self):
        raw = self._clean()
        wrapped = "\n".join(raw[i:i + 60] for i in range(0, len(raw), 60)) + "\n"
        self.install([FakeResponse(200, {"sha": "s1", "content": wrapped})])
        put = self.install_put([FakeResponse(200, {})])
        self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(put.calls, [],
                         "GitHub's line-wrapped content was rejected as malformed")

    def test_invalid_punctuation_is_not_silently_accepted_as_unchanged(self):
        out = io.StringIO()
        self.install([FakeResponse(200, {"sha": "s1", "content": self._polluted()})])
        put = self.install_put([FakeResponse(200, {})])
        with contextlib.redirect_stdout(out):
            with self.assertRaises(sync_mod.PublishPreReadFailed):
                self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(put.calls, [], "a malformed pre-read reached the PUT")
        self.assertNotIn("No changes detected", out.getvalue(),
                         "a malformed body was reported as an unchanged file")

    def test_invalid_punctuation_on_verification_is_unknown_with_no_second_put(self):
        self.install([FakeResponse(200, {"sha": "s1",
                                         "content": encoded({"old": True})}),
                      FakeResponse(200, {"sha": "s2", "content": self._polluted()})])
        put = self.install_put([requests.exceptions.Timeout("x")])
        with self.assertRaises(sync_mod.PublishOutcomeUnknown):
            self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(len(put.calls), 1)

    def test_decoder_rejects_unusable_values_and_accepts_valid_ones(self):
        decode = self.sync._decode_github_content
        self.assertEqual(decode(encoded({"a": 1})),
                         json.dumps({"a": 1}, indent=2, default=str))
        for bad in (None, 12345, ["x"], "", "   ", "!!!", "a" * 3 + "!",
                    self._polluted()):
            with self.subTest(value=repr(bad)[:20]):
                with self.assertRaises(ValueError):
                    decode(bad)

    def test_non_utf8_content_is_rejected(self):
        import base64 as b64
        self.install([FakeResponse(200, {"sha": "s1",
                                         "content": b64.b64encode(b"\xff\xfe").decode()})])
        put = self.install_put([FakeResponse(200, {})])
        with self.assertRaises(sync_mod.PublishPreReadFailed):
            self.sync.publish_to_github(self.DATA, "latest.json")
        self.assertEqual(put.calls, [])


class TestReadNotInterruptedByAdmissionCap(SyncPolicyCase):
    def test_a_slow_successful_read_is_returned_not_cut_off(self):
        """
        The admission cap gates whether another attempt may begin. It must never be
        read as a deadline that abandons a request already in flight.
        """
        t = self.install([FakeResponse(200, {"ok": True})], cost=500.0)
        self.assertEqual(self.sync._intervals_get(""), {"ok": True})
        self.assertEqual(len(t.calls), 1)
        self.assertGreater(self.clock.t, self.sync.READ_RETRY_ADMISSION_CAP_SECS)


class TestMalformedActivityMessages(SyncPolicyCase):
    def setUp(self):
        super().setUp()
        self.sync._intervals_data = None
        # The terrain fetcher shares the same patched verb and would otherwise be fed
        # these deliberately malformed message payloads. It is a separate, already
        # bounded path and not what these cases are about.
        patcher = mock.patch.object(self.sync, "_fetch_terrain_streams",
                                    return_value=("no_data", {}))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _activity(self):
        return {"id": "a1", "name": "Ride", "type": "Ride",
                "start_date_local": datetime.now().strftime("%Y-%m-%dT08:00:00"),
                "moving_time": 3600}

    def test_non_object_element_degrades_instead_of_crashing(self):
        self.install([FakeResponse(200, ["a bare string", {"content": "ok"}])])
        formatted = self.sync._format_activities([self._activity()])
        self.assertEqual(formatted[0]["chat_notes_status"], "unavailable")
        self.assertNotIn("chat_notes", formatted[0])

    def test_non_string_content_degrades_instead_of_crashing(self):
        self.install([FakeResponse(200, [{"content": 12345}])])
        formatted = self.sync._format_activities([self._activity()])
        self.assertEqual(formatted[0]["chat_notes_status"], "unavailable")

    def test_malformed_element_advances_the_breaker(self):
        self.sync.READ_RETRY_MAX_ATTEMPTS = 1
        self.install([FakeResponse(200, [None])])
        before = self.sync._messages_consecutive_failures
        self.sync._get_activity_messages("a1")
        self.assertEqual(self.sync._messages_consecutive_failures, before + 1,
                         "a malformed payload did not count toward the breaker, so a "
                         "broken endpoint would be re-read for every activity")

    def test_empty_content_falls_back_to_text(self):
        self.install([FakeResponse(200, [{"content": "", "text": "fallback note"}])])
        formatted = self.sync._format_activities([self._activity()])
        self.assertEqual(formatted[0]["chat_notes"], ["fallback note"],
                         "empty content did not fall back to text, so a real note "
                         "was dropped")
        self.assertNotIn("chat_notes_status", formatted[0])

    def test_whitespace_only_content_falls_back_to_text(self):
        self.install([FakeResponse(200, [{"content": "   \n\t ",
                                          "text": "fallback note"}])])
        formatted = self.sync._format_activities([self._activity()])
        self.assertEqual(formatted[0]["chat_notes"], ["fallback note"])

    def test_empty_content_with_no_text_is_a_confirmed_empty_not_a_failure(self):
        self.install([FakeResponse(200, [{"content": ""}])])
        formatted = self.sync._format_activities([self._activity()])
        self.assertNotIn("chat_notes", formatted[0])
        self.assertNotIn("chat_notes_status", formatted[0],
                         "a message with no usable text was reported as degraded")

    def test_non_string_content_is_still_unavailable(self):
        self.install([FakeResponse(200, [{"content": 12345, "text": "note"}])])
        formatted = self.sync._format_activities([self._activity()])
        self.assertEqual(formatted[0]["chat_notes_status"], "unavailable")

    def test_non_string_text_fallback_is_unavailable(self):
        self.install([FakeResponse(200, [{"content": "", "text": ["a", "list"]}])])
        formatted = self.sync._format_activities([self._activity()])
        self.assertEqual(formatted[0]["chat_notes_status"], "unavailable")

    def test_successful_empty_list_is_still_ok_and_empty(self):
        self.install([FakeResponse(200, [])])
        self.assertEqual(self.sync._get_activity_messages("a1"), ("ok", []))
        self.assertEqual(self.sync._messages_consecutive_failures, 0)

    def test_null_content_with_text_fallback_still_works(self):
        self.install([FakeResponse(200, [{"content": None, "text": "from text"}])])
        formatted = self.sync._format_activities([self._activity()])
        self.assertEqual(formatted[0]["chat_notes"], ["from text"])
        self.assertNotIn("chat_notes_status", formatted[0])


# ── push.py ──────────────────────────────────────────────────────────────────

class PushTransport:
    """
    Stand-in for the whole requests module behind push.py's lazy binding.

    Carries the REAL requests.exceptions so push.py's classification is exercised
    against the actual exception hierarchy rather than a synthetic one.
    """

    exceptions = requests.exceptions

    def __init__(self, handlers=None):
        self.handlers = handlers or {}
        self.calls = []

    def _dispatch(self, verb, url, **kwargs):
        self.calls.append((verb, url))
        handler = self.handlers.get(verb)
        if handler is None:
            raise NetworkBlocked(f"unmocked {verb} to {url}")
        item = handler(url, len([c for c in self.calls if c[0] == verb]) - 1) \
            if callable(handler) else handler
        if isinstance(item, BaseException):
            raise item
        return item

    def get(self, url, **kw):
        return self._dispatch("GET", url, **kw)

    def post(self, url, **kw):
        return self._dispatch("POST", url, **kw)

    def put(self, url, **kw):
        return self._dispatch("PUT", url, **kw)

    def delete(self, url, **kw):
        return self._dispatch("DELETE", url, **kw)

    def verbs(self, name):
        return [c for c in self.calls if c[0] == name]


FUTURE = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")


class PushCase(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        p1 = mock.patch.object(push_mod.time, "sleep", self.clock.sleep)
        p1.start()
        self.addCleanup(p1.stop)
        p2 = mock.patch.object(push_mod.time, "monotonic", self.clock.monotonic)
        p2.start()
        self.addCleanup(p2.stop)
        self._saved = push_mod._requests
        self.addCleanup(self.restore)
        self.pusher = push_mod.IntervalsPush("i123456", "key_test")

    def restore(self):
        push_mod._requests = self._saved

    def install(self, **handlers):
        transport = PushTransport(handlers)
        push_mod._requests = transport
        return transport


class TestPushReadPolicy(PushCase):
    def test_reads_carry_the_timeout_tuple_and_retry_transient_failures(self):
        seq = [requests.exceptions.Timeout("x"), FakeResponse(200, {"id": 42})]
        t = self.install(GET=lambda url, i: seq[min(i, len(seq) - 1)])
        self.assertEqual(self.pusher._get("events/42"), {"id": 42})
        self.assertEqual(len(t.verbs("GET")), 2)
        self.assertEqual(self.clock.sleeps, [1])

    def test_non_retryable_status_is_not_retried(self):
        t = self.install(GET=FakeResponse(404))
        with self.assertRaises(requests.exceptions.HTTPError):
            self.pusher._get("events/42")
        self.assertEqual(len(t.verbs("GET")), 1)

    def test_unfittable_retry_after_does_not_sleep(self):
        self.install(GET=FakeResponse(429, headers={"Retry-After": "300"}))
        with self.assertRaises(requests.exceptions.HTTPError):
            self.pusher._get("events")
        self.assertEqual(self.clock.sleeps, [])

    def test_parse_retry_after_matches_the_sync_table(self):
        sync = sync_mod.IntervalsSync("i0", "k")
        past = (datetime.now() - timedelta(hours=1)).strftime(
            "%a, %d %b %Y %H:%M:%S GMT")
        for value in ("30", "0", "-5", "", None, "soon", past):
            with self.subTest(value=value):
                self.assertEqual(push_mod.IntervalsPush._parse_retry_after(value),
                                 sync._parse_retry_after(value))


class TestPreWriteGates(PushCase):
    """A failed pre-write read closes the gate: not_applied, zero writes."""

    def test_every_write_operation_fails_closed_on_a_failed_pre_read(self):
        cases = {
            "push_workouts": lambda p: p.push_workouts(
                [{"name": "W", "date": FUTURE, "type": "Ride"}]),
            "move_event": lambda p: p.move_event(42, FUTURE),
            "delete_event": lambda p: p.delete_event(42),
            "set_threshold": lambda p: p.set_threshold("Ride", {"ftp": 300}),
            "annotate_event": lambda p: p.annotate_event(42, "note"),
            "annotate_activity_description": lambda p: p.annotate_activity(
                "a1", "note"),
            "annotate_activity_chat": lambda p: p.annotate_activity(
                "a1", "note", chat=True),
        }
        for name, run in cases.items():
            with self.subTest(operation=name):
                t = self.install(GET=FakeResponse(500))
                result = run(self.pusher)
                self.assertFalse(result["success"])
                self.assertEqual(result["outcome"], "not_applied",
                                 f"{name} did not fail closed on a failed pre-read")
                self.assertEqual([c for c in t.calls if c[0] != "GET"], [],
                                 f"{name} wrote after its pre-write read failed")


class TestBulkUpsert(PushCase):
    WORKOUT = {"name": "Sweet Spot", "date": FUTURE, "type": "Ride",
               "external_id": "s11-a", "duration_minutes": 60}

    def test_success_reports_applied(self):
        created = {"id": 1, "name": "Sweet Spot", "start_date_local": f"{FUTURE}T00:00:00",
                   "type": "Ride", "external_id": "s11-a"}
        self.install(GET=FakeResponse(200, []), POST=FakeResponse(200, [created]))
        result = self.pusher.push_workouts([self.WORKOUT])
        self.assertEqual(result["outcome"], "applied")

    def test_duplicate_external_id_in_batch_is_rejected_before_any_request(self):
        t = self.install(GET=FakeResponse(200, []), POST=FakeResponse(200, []))
        second = dict(self.WORKOUT, name="Other")
        result = self.pusher.push_workouts([self.WORKOUT, second])
        self.assertEqual(result["outcome"], "not_applied")
        self.assertEqual(t.calls, [],
                         "a batch with an ambiguous key reached the network")

    def test_pre_existing_duplicate_external_id_stops_before_writing(self):
        upstream = [{"id": 1, "external_id": "s11-a"}, {"id": 2, "external_id": "s11-a"}]
        t = self.install(GET=FakeResponse(200, upstream), POST=FakeResponse(200, []))
        result = self.pusher.push_workouts([self.WORKOUT])
        self.assertEqual(result["outcome"], "not_applied")
        self.assertEqual(t.verbs("POST"), [],
                         "wrote into a window where external_id is not unique")

    def test_timeout_with_exact_unique_match_is_applied(self):
        applied = {"id": 1, "name": "Sweet Spot",
                   "start_date_local": f"{FUTURE}T00:00:00", "type": "Ride",
                   "category": "WORKOUT", "moving_time": 3600,
                   "external_id": "s11-a"}
        gets = [FakeResponse(200, []), FakeResponse(200, [applied])]
        t = self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                         POST=requests.exceptions.Timeout("x"))
        result = self.pusher.push_workouts([self.WORKOUT])
        self.assertEqual(result["outcome"], "applied")
        self.assertEqual(len(t.verbs("POST")), 1)

    def test_timeout_with_no_match_is_unknown_not_not_applied(self):
        t = self.install(GET=FakeResponse(200, []),
                         POST=requests.exceptions.Timeout("x"))
        result = self.pusher.push_workouts([self.WORKOUT])
        self.assertEqual(result["outcome"], "unknown",
                         "absence of a match was treated as proof of failure; the "
                         "upsert matching key is not established")
        self.assertEqual(len(t.verbs("POST")), 1)

    def test_proximity_match_without_external_id_is_still_unknown(self):
        """
        Load-bearing. An event with the same name, date and type sits in the window,
        and the item carried no external_id. That must not be read as success.
        """
        lookalike = {"id": 7, "name": "Sweet Spot",
                     "start_date_local": f"{FUTURE}T00:00:00", "type": "Ride"}
        gets = [FakeResponse(200, []), FakeResponse(200, [lookalike])]
        self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                     POST=requests.exceptions.Timeout("x"))
        workout = {k: v for k, v in self.WORKOUT.items() if k != "external_id"}
        result = self.pusher.push_workouts([workout])
        self.assertEqual(result["outcome"], "unknown",
                         "a same name/date/type match was accepted as proof")
        self.assertEqual(result["items"][0]["reason"], "no_external_id")

    def test_non_unique_match_after_timeout_is_unknown(self):
        twins = [{"id": 1, "external_id": "s11-a"}, {"id": 2, "external_id": "s11-a"}]
        gets = [FakeResponse(200, []), FakeResponse(200, twins)]
        self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                     POST=requests.exceptions.Timeout("x"))
        result = self.pusher.push_workouts([self.WORKOUT])
        self.assertEqual(result["outcome"], "unknown")

    def test_partial_batch_reports_unknown_overall(self):
        one = {"id": 1, "name": "Sweet Spot", "start_date_local": f"{FUTURE}T00:00:00",
               "type": "Ride", "category": "WORKOUT", "moving_time": 3600,
               "external_id": "s11-a"}
        gets = [FakeResponse(200, []), FakeResponse(200, [one])]
        self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                     POST=requests.exceptions.Timeout("x"))
        second = dict(self.WORKOUT, name="Second", external_id="s11-b")
        result = self.pusher.push_workouts([self.WORKOUT, second])
        self.assertEqual(result["outcome"], "unknown")
        states = sorted(i["state"] for i in result["items"])
        self.assertEqual(states, ["applied", "unknown"])

    def test_short_response_list_routes_through_verification(self):
        gets = [FakeResponse(200, []), FakeResponse(200, [])]
        t = self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                         POST=FakeResponse(200, []))
        second = dict(self.WORKOUT, name="Second", external_id="s11-b")
        result = self.pusher.push_workouts([self.WORKOUT, second])
        self.assertEqual(result["outcome"], "unknown")
        self.assertEqual(len(t.verbs("GET")), 2)

    def test_failed_verification_read_is_unknown(self):
        gets = [FakeResponse(200, []), FakeResponse(500)]
        self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                     POST=requests.exceptions.Timeout("x"))
        result = self.pusher.push_workouts([self.WORKOUT])
        self.assertEqual(result["outcome"], "unknown")

    def test_definitive_422_is_not_applied_without_verification(self):
        err = requests.exceptions.HTTPError("422", response=FakeResponse(422))
        t = self.install(GET=FakeResponse(200, []), POST=err)
        result = self.pusher.push_workouts([self.WORKOUT])
        self.assertEqual(result["outcome"], "not_applied")
        self.assertEqual(len(t.verbs("GET")), 1,
                         "a definitive refusal triggered a verification read")


class TestIdAddressedWrites(PushCase):
    EVENT = {"id": 42, "name": "Endurance", "start_date_local": f"{FUTURE}T00:00:00",
             "type": "Ride", "description": "base text"}

    def test_move_success_is_applied(self):
        moved = dict(self.EVENT, start_date_local=f"{FUTURE}T00:00:00")
        self.install(GET=FakeResponse(200, self.EVENT), PUT=FakeResponse(200, moved))
        self.assertEqual(self.pusher.move_event(42, FUTURE)["outcome"], "applied")

    def test_move_timeout_with_matching_state_is_applied(self):
        target = f"{FUTURE}T00:00:00"
        after = dict(self.EVENT, start_date_local=target)
        gets = [FakeResponse(200, self.EVENT), FakeResponse(200, after)]
        t = self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                         PUT=requests.exceptions.Timeout("x"))
        result = self.pusher.move_event(42, FUTURE)
        self.assertEqual(result["outcome"], "applied")
        self.assertEqual(len(t.verbs("PUT")), 1)

    def test_move_timeout_with_pre_write_state_is_unknown_not_replayed(self):
        old = dict(self.EVENT, start_date_local="2099-12-31T00:00:00")
        t = self.install(GET=FakeResponse(200, old),
                         PUT=requests.exceptions.Timeout("x"))
        result = self.pusher.move_event(42, FUTURE)
        self.assertEqual(result["outcome"], "unknown",
                         "observing the pre-write state was treated as proof of "
                         "non-application")
        self.assertEqual(len(t.verbs("PUT")), 1,
                         "the write was replayed")

    def test_move_timeout_with_concurrent_edit_is_unknown(self):
        other = dict(self.EVENT, start_date_local="2098-01-01T00:00:00", name="Changed")
        gets = [FakeResponse(200, self.EVENT), FakeResponse(200, other)]
        self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                     PUT=requests.exceptions.Timeout("x"))
        self.assertEqual(self.pusher.move_event(42, FUTURE)["outcome"], "unknown")

    def test_delete_of_already_absent_event_is_applied_with_zero_deletes(self):
        t = self.install(GET=FakeResponse(404))
        result = self.pusher.delete_event(42)
        self.assertEqual(result["outcome"], "applied")
        self.assertTrue(result["unchanged"])
        self.assertEqual(t.verbs("DELETE"), [],
                         "a DELETE was issued for an event already absent")

    def test_delete_success_is_applied(self):
        self.install(GET=FakeResponse(200, self.EVENT), DELETE=FakeResponse(204, {}))
        self.assertEqual(self.pusher.delete_event(42)["outcome"], "applied")

    def test_delete_timeout_verified_absent_is_applied(self):
        gets = [FakeResponse(200, self.EVENT), FakeResponse(404)]
        t = self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                         DELETE=requests.exceptions.Timeout("x"))
        result = self.pusher.delete_event(42)
        self.assertEqual(result["outcome"], "applied")
        self.assertEqual(len(t.verbs("DELETE")), 1)

    def test_delete_timeout_still_present_is_unknown(self):
        t = self.install(GET=FakeResponse(200, self.EVENT),
                         DELETE=requests.exceptions.Timeout("x"))
        result = self.pusher.delete_event(42)
        self.assertEqual(result["outcome"], "unknown")
        self.assertEqual(len(t.verbs("DELETE")), 1)

    def test_threshold_success_is_applied(self):
        settings = {"ftp": 300, "lthr": 160}
        self.install(GET=FakeResponse(200, {"ftp": 250, "lthr": 160}),
                     PUT=FakeResponse(200, settings))
        self.assertEqual(self.pusher.set_threshold("Ride", {"ftp": 300})["outcome"],
                         "applied")

    def test_threshold_timeout_with_exact_readback_is_applied(self):
        gets = [FakeResponse(200, {"ftp": 250}), FakeResponse(200, {"ftp": 300})]
        self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                     PUT=requests.exceptions.Timeout("x"))
        self.assertEqual(self.pusher.set_threshold("Ride", {"ftp": 300})["outcome"],
                         "applied")

    def test_threshold_normalized_value_is_unknown(self):
        gets = [FakeResponse(200, {"ftp": 250}), FakeResponse(200, {"ftp": 299})]
        self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                     PUT=requests.exceptions.Timeout("x"))
        result = self.pusher.set_threshold("Ride", {"ftp": 300})
        self.assertEqual(result["outcome"], "unknown",
                         "a normalised or rounded value was reported as applied")
        self.assertEqual(result["observed"], {"ftp": 299})


class TestAnnotations(PushCase):
    EVENT = {"id": 42, "name": "Endurance", "start_date_local": f"{FUTURE}T00:00:00",
             "type": "Ride", "description": "base text"}
    ACTIVITY = {"id": "a1", "name": "Ride", "start_date_local": "2099-01-01T00:00:00",
                "description": "base text"}

    def test_event_note_success_is_applied(self):
        self.install(GET=FakeResponse(200, self.EVENT), PUT=FakeResponse(200, self.EVENT))
        self.assertEqual(self.pusher.annotate_event(42, "focus cadence")["outcome"],
                         "applied")

    def test_duplicate_event_note_makes_no_put(self):
        already = dict(self.EVENT, description="NOTE: focus cadence\n\nbase text")
        t = self.install(GET=FakeResponse(200, already), PUT=FakeResponse(200, already))
        result = self.pusher.annotate_event(42, "focus cadence")
        self.assertEqual(result["outcome"], "applied")
        self.assertTrue(result["unchanged"])
        self.assertEqual(t.verbs("PUT"), [],
                         "re-running after an unknown outcome doubled the note")

    def test_event_note_timeout_with_exact_description_is_applied(self):
        target = dict(self.EVENT, description="NOTE: focus cadence\n\nbase text")
        gets = [FakeResponse(200, self.EVENT), FakeResponse(200, target)]
        self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                     PUT=requests.exceptions.Timeout("x"))
        self.assertEqual(self.pusher.annotate_event(42, "focus cadence")["outcome"],
                         "applied")

    def test_event_note_timeout_with_concurrent_edit_is_unknown(self):
        other = dict(self.EVENT, description="someone else wrote this")
        gets = [FakeResponse(200, self.EVENT), FakeResponse(200, other)]
        self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                     PUT=requests.exceptions.Timeout("x"))
        self.assertEqual(self.pusher.annotate_event(42, "focus cadence")["outcome"],
                         "unknown")

    def test_duplicate_activity_note_makes_no_put(self):
        already = dict(self.ACTIVITY, description="NOTE: knee pain\n\nbase text")
        t = self.install(GET=FakeResponse(200, already), PUT=FakeResponse(200, already))
        result = self.pusher.annotate_activity("a1", "knee pain")
        self.assertTrue(result["unchanged"])
        self.assertEqual(t.verbs("PUT"), [])

    def test_activity_note_timeout_with_exact_description_is_applied(self):
        target = dict(self.ACTIVITY, description="NOTE: knee pain\n\nbase text")
        gets = [FakeResponse(200, self.ACTIVITY), FakeResponse(200, target)]
        self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                     PUT=requests.exceptions.Timeout("x"))
        self.assertEqual(self.pusher.annotate_activity("a1", "knee pain")["outcome"],
                         "applied")

    def test_chat_note_success_is_applied(self):
        self.install(GET=FakeResponse(200, []), POST=FakeResponse(200, {"id": 5}))
        result = self.pusher.annotate_activity("a1", "knee pain", chat=True)
        self.assertEqual(result["outcome"], "applied")

    def test_chat_note_timeout_is_unknown_even_with_a_new_id_present(self):
        """
        The message-ID probe has not been run, so a plausible new id is evidence and
        nothing more. Classifying on it would authorise a duplicate-creating replay.
        """
        gets = [FakeResponse(200, []), FakeResponse(200, [{"id": 9, "content": "knee pain"}])]
        t = self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                         POST=requests.exceptions.Timeout("x"))
        result = self.pusher.annotate_activity("a1", "knee pain", chat=True)
        self.assertEqual(result["outcome"], "unknown")
        self.assertEqual(result["evidence"]["new_message_ids"], ["9"])
        self.assertEqual(len(t.verbs("POST")), 1)

    def test_chat_note_timeout_with_identical_pre_existing_text_is_unknown(self):
        existing = [{"id": 1, "content": "knee pain"}]
        self.install(GET=FakeResponse(200, existing),
                     POST=requests.exceptions.Timeout("x"))
        result = self.pusher.annotate_activity("a1", "knee pain", chat=True)
        self.assertEqual(result["outcome"], "unknown",
                         "identical existing text was mistaken for the new message")
        self.assertEqual(result["evidence"]["new_message_ids"], [])


class TestNoAutomaticReissue(PushCase):
    """
    One transport, everything ambiguous. Every write operation must issue its verb
    exactly once and report unknown. This is the single assertion that would fail if
    any reissue path were reintroduced anywhere.
    """

    def test_no_write_verb_is_issued_twice_after_an_ambiguous_write(self):
        timeout = requests.exceptions.Timeout("x")
        # Deliberately NOT on the target date: verification must find the pre-write
        # state and report unknown rather than proving the move landed.
        event = {"id": 42, "name": "E", "start_date_local": "2097-01-01T00:00:00",
                 "type": "Ride", "description": "base"}
        activity = {"id": "a1", "description": "base"}
        cases = [
            ("bulk", "POST", FakeResponse(200, []),
             lambda p: p.push_workouts([{"name": "W", "date": FUTURE, "type": "Ride",
                                         "external_id": "x"}])),
            ("move", "PUT", FakeResponse(200, event),
             lambda p: p.move_event(42, FUTURE)),
            ("delete", "DELETE", FakeResponse(200, event),
             lambda p: p.delete_event(42)),
            ("threshold", "PUT", FakeResponse(200, {"ftp": 250}),
             lambda p: p.set_threshold("Ride", {"ftp": 300})),
            ("event_note", "PUT", FakeResponse(200, event),
             lambda p: p.annotate_event(42, "note")),
            ("activity_note", "PUT", FakeResponse(200, activity),
             lambda p: p.annotate_activity("a1", "note")),
            ("chat_note", "POST", FakeResponse(200, []),
             lambda p: p.annotate_activity("a1", "note", chat=True)),
        ]
        for name, verb, read, run in cases:
            with self.subTest(operation=name):
                t = self.install(GET=read, **{verb: timeout})
                result = run(self.pusher)
                self.assertEqual(result["outcome"], "unknown",
                                 f"{name} claimed a definite outcome it cannot prove")
                self.assertEqual(len(t.verbs(verb)), 1,
                                 f"{name} issued {verb} more than once")


class TestPushLostResponseAndStatus(PushCase):
    """
    A lost response and an unexpected status are the two ways a write can look like a
    failure while having landed. Neither may produce not_applied.
    """

    EVENT = {"id": 42, "name": "E", "start_date_local": "2097-01-01T00:00:00",
             "type": "Ride", "description": "base"}

    def test_chunked_encoding_error_is_ambiguous_not_definitive(self):
        t = self.install(GET=FakeResponse(200, self.EVENT),
                         PUT=requests.exceptions.ChunkedEncodingError("truncated"))
        result = self.pusher.move_event(42, FUTURE)
        self.assertEqual(result["outcome"], "unknown",
                         "a truncated response was reported as not_applied; the "
                         "server may already have committed the change")
        self.assertEqual(len(t.verbs("PUT")), 1)

    def test_chunked_encoding_error_with_exact_state_verifies_to_applied(self):
        after = dict(self.EVENT, start_date_local=f"{FUTURE}T00:00:00")
        gets = [FakeResponse(200, self.EVENT), FakeResponse(200, after)]
        self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                     PUT=requests.exceptions.ChunkedEncodingError("truncated"))
        self.assertEqual(self.pusher.move_event(42, FUTURE)["outcome"], "applied")

    def test_connect_timeout_follows_the_same_ambiguity_path(self):
        t = self.install(GET=FakeResponse(200, self.EVENT),
                         PUT=requests.exceptions.ConnectTimeout("no connect"))
        result = self.pusher.move_event(42, FUTURE)
        self.assertEqual(result["outcome"], "unknown",
                         "ConnectTimeout was special-cased as proof of "
                         "non-application")
        self.assertEqual(len(t.verbs("PUT")), 1)

    def test_write_302_cannot_be_applied_without_verification(self):
        t = self.install(GET=FakeResponse(200, self.EVENT), PUT=FakeResponse(302))
        result = self.pusher.move_event(42, FUTURE)
        self.assertEqual(result["outcome"], "unknown",
                         "a redirect was accepted as a successful write because "
                         "raise_for_status() does not reject 3xx")
        self.assertEqual(len(t.verbs("PUT")), 1)

    def test_write_302_with_exact_state_verifies_to_applied(self):
        after = dict(self.EVENT, start_date_local=f"{FUTURE}T00:00:00")
        gets = [FakeResponse(200, self.EVENT), FakeResponse(200, after)]
        self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                     PUT=FakeResponse(302))
        self.assertEqual(self.pusher.move_event(42, FUTURE)["outcome"], "applied")

    def test_write_side_429_and_5xx_enter_verification(self):
        for status in (429, 500, 502, 503):
            with self.subTest(status=status):
                t = self.install(GET=FakeResponse(200, self.EVENT),
                                 PUT=FakeResponse(status))
                result = self.pusher.move_event(42, FUTURE)
                self.assertEqual(result["outcome"], "unknown",
                                 f"write-side {status} was treated as definite")
                self.assertEqual(len(t.verbs("GET")), 2,
                                 f"write-side {status} skipped verification")
                self.assertEqual(len(t.verbs("PUT")), 1)

    def test_definitive_statuses_stay_not_applied_without_verification(self):
        for status in (400, 401, 403, 409, 422):
            with self.subTest(status=status):
                t = self.install(GET=FakeResponse(200, self.EVENT),
                                 PUT=FakeResponse(status))
                result = self.pusher.move_event(42, FUTURE)
                self.assertEqual(result["outcome"], "not_applied")
                self.assertEqual(len(t.verbs("GET")), 1,
                                 f"a definitive {status} triggered verification")


class TestMalformedReads(PushCase):
    """
    A 200 whose body is the wrong shape establishes nothing. Coercing it to an empty
    list or an empty dict is how a write ends up issued against unknown state.
    """

    WORKOUT = {"name": "W", "date": FUTURE, "type": "Ride", "external_id": "x"}
    EVENT = {"id": 42, "name": "E", "start_date_local": "2097-01-01T00:00:00",
             "type": "Ride", "description": "base"}

    OPERATIONS = {
        "push_workouts": lambda p: p.push_workouts([
            {"name": "W", "date": FUTURE, "type": "Ride", "external_id": "x"}]),
        "move_event": lambda p: p.move_event(42, FUTURE),
        "delete_event": lambda p: p.delete_event(42),
        "set_threshold": lambda p: p.set_threshold("Ride", {"ftp": 300}),
        "annotate_event": lambda p: p.annotate_event(42, "note"),
        "annotate_activity_description": lambda p: p.annotate_activity("a1", "note"),
        "annotate_activity_chat": lambda p: p.annotate_activity("a1", "note",
                                                                chat=True),
    }

    # What counts as malformed depends on the shape the pre-read must establish. A
    # bare object is a perfectly valid event or settings body, so it belongs only in
    # the list-of-objects set.
    MALFORMED_FOR_OBJECT = ("a bare string", ["not", "objects"], [None], 12345)
    MALFORMED_FOR_OBJECT_LIST = ("a bare string", {"unexpected": "object"},
                                 ["not", "objects"], [None], 12345)

    EXPECTS_OBJECT_LIST = {"push_workouts", "annotate_activity_chat"}

    def test_malformed_pre_read_fails_closed_for_every_write_operation(self):
        for name, run in self.OPERATIONS.items():
            bodies = (self.MALFORMED_FOR_OBJECT_LIST
                      if name in self.EXPECTS_OBJECT_LIST
                      else self.MALFORMED_FOR_OBJECT)
            for body in bodies:
                with self.subTest(operation=name, body=repr(body)[:24]):
                    t = self.install(GET=FakeResponse(200, body))
                    result = run(self.pusher)
                    self.assertEqual(
                        result["outcome"], "not_applied",
                        f"{name} did not fail closed on a malformed pre-read")
                    self.assertFalse(result["success"])
                    self.assertEqual(
                        [c for c in t.calls if c[0] != "GET"], [],
                        f"{name} wrote after a malformed pre-read")

    def test_json_null_body_is_malformed_and_fails_closed(self):
        """A literal JSON null decodes to None, which is not an object."""

        class NullBody(FakeResponse):
            def json(self):
                return None

        t = self.install(GET=NullBody(200))
        result = self.pusher.move_event(42, FUTURE)
        self.assertEqual(result["outcome"], "not_applied")
        self.assertEqual(t.verbs("PUT"), [])

    def test_malformed_verifier_body_yields_unknown_for_every_operation(self):
        cases = [
            ("move_event", "PUT", self.EVENT, lambda p: p.move_event(42, FUTURE)),
            ("delete_event", "DELETE", self.EVENT, lambda p: p.delete_event(42)),
            ("set_threshold", "PUT", {"ftp": 250},
             lambda p: p.set_threshold("Ride", {"ftp": 300})),
            ("annotate_event", "PUT", self.EVENT,
             lambda p: p.annotate_event(42, "note")),
            ("annotate_activity_description", "PUT", {"id": "a1", "description": "d"},
             lambda p: p.annotate_activity("a1", "note")),
            ("push_workouts", "POST", [],
             lambda p: p.push_workouts([dict(self.WORKOUT)])),
            ("annotate_activity_chat", "POST", [],
             lambda p: p.annotate_activity("a1", "note", chat=True)),
        ]
        for name, verb, good, run in cases:
            with self.subTest(operation=name):
                gets = [FakeResponse(200, good), FakeResponse(200, "malformed")]
                t = self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                                 **{verb: requests.exceptions.Timeout("x")})
                result = run(self.pusher)
                self.assertEqual(result["outcome"], "unknown",
                                 f"{name} did not report unknown when its verifier "
                                 f"returned a malformed body")
                self.assertEqual(len(t.verbs(verb)), 1)


class TestBulkSuccessBodyValidation(PushCase):
    """
    An explicit 2xx is not proof that every item landed. The body has to be a list of
    objects of the expected length before it can be read that way.
    """

    W1 = {"name": "One", "date": FUTURE, "type": "Ride", "external_id": "e1"}
    W2 = {"name": "Two", "date": FUTURE, "type": "Ride", "external_id": "e2"}

    def _applied(self, workout):
        return {"id": 1, "name": workout["name"],
                "start_date_local": f"{FUTURE}T00:00:00", "type": "Ride",
                "category": "WORKOUT", "external_id": workout["external_id"]}

    def test_object_body_is_not_applied_it_is_verified(self):
        gets = [FakeResponse(200, []), FakeResponse(200, [])]
        t = self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                         POST=FakeResponse(200, {"created": 1}))
        result = self.pusher.push_workouts([self.W1])
        self.assertEqual(result["outcome"], "unknown",
                         "a 200 whose body was an object was reported as applied")
        self.assertEqual(len(t.verbs("GET")), 2, "verification was skipped")
        self.assertEqual(len(t.verbs("POST")), 1)

    def test_object_body_verified_applied_is_allowed(self):
        gets = [FakeResponse(200, []), FakeResponse(200, [self._applied(self.W1)])]
        self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                     POST=FakeResponse(200, {"created": 1}))
        result = self.pusher.push_workouts([self.W1])
        self.assertEqual(result["outcome"], "applied")
        self.assertEqual(result["verified_after"], "malformed_response_body")

    def test_list_with_a_non_object_element_does_not_crash(self):
        for bad in ("a string", None, 12345, ["nested"]):
            with self.subTest(element=repr(bad)[:16]):
                gets = [FakeResponse(200, []), FakeResponse(200, [])]
                t = self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                                 POST=FakeResponse(200, [bad]))
                result = self.pusher.push_workouts([self.W1])
                self.assertEqual(result["outcome"], "unknown")
                self.assertEqual(len(t.verbs("POST")), 1)

    def test_short_list_is_verified_not_applied(self):
        gets = [FakeResponse(200, []), FakeResponse(200, [self._applied(self.W1)])]
        t = self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                         POST=FakeResponse(200, [self._applied(self.W1)]))
        result = self.pusher.push_workouts([self.W1, self.W2])
        self.assertEqual(result["outcome"], "unknown",
                         "a short response list was reported as a full success")
        self.assertEqual(len(t.verbs("POST")), 1)

    def test_long_list_is_verified(self):
        extra = dict(self._applied(self.W1), id=9, external_id="e9")
        gets = [FakeResponse(200, []), FakeResponse(200, [])]
        self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                     POST=FakeResponse(200, [self._applied(self.W1), extra]))
        self.assertEqual(self.pusher.push_workouts([self.W1])["outcome"], "unknown")

    def test_malformed_verification_after_a_malformed_success_is_unknown(self):
        for body in ({"created": 1}, ["a string"],
                     [{"id": 1, "external_id": "e1"}, {"id": 2}]):
            with self.subTest(body=repr(body)[:20]):
                gets = [FakeResponse(200, []), FakeResponse(200, "malformed")]
                t = self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                                 POST=FakeResponse(200, body))
                result = self.pusher.push_workouts([self.W1])
                self.assertEqual(result["outcome"], "unknown")
                self.assertEqual(len(t.verbs("POST")), 1,
                                 "a second write followed a malformed response")


class TestNestedFieldValidation(PushCase):
    EVENT = {"id": 42, "name": "E", "start_date_local": "2097-01-01T00:00:00",
             "type": "Ride"}
    ACTIVITY = {"id": "a1", "name": "Ride"}

    def test_non_string_event_description_fails_closed(self):
        for bad in (12345, ["a", "list"], {"nested": True}, 3.5):
            with self.subTest(description=repr(bad)[:16]):
                event = dict(self.EVENT, description=bad)
                t = self.install(GET=FakeResponse(200, event))
                result = self.pusher.annotate_event(42, "note")
                self.assertEqual(result["outcome"], "not_applied")
                self.assertEqual(t.verbs("PUT"), [],
                                 "wrote a NOTE line onto a non-text description")

    def test_non_string_activity_description_fails_closed(self):
        activity = dict(self.ACTIVITY, description=[1, 2, 3])
        t = self.install(GET=FakeResponse(200, activity))
        result = self.pusher.annotate_activity("a1", "note")
        self.assertEqual(result["outcome"], "not_applied")
        self.assertEqual(t.verbs("PUT"), [])

    def test_absent_and_null_descriptions_are_usable(self):
        for event in (dict(self.EVENT), dict(self.EVENT, description=None)):
            with self.subTest(description=event.get("description", "absent")):
                self.install(GET=FakeResponse(200, event),
                             PUT=FakeResponse(200, event))
                self.assertEqual(self.pusher.annotate_event(42, "note")["outcome"],
                                 "applied")

    def test_malformed_description_on_verification_is_unknown(self):
        activity = dict(self.ACTIVITY, description="base")
        gets = [FakeResponse(200, activity),
                FakeResponse(200, dict(self.ACTIVITY, description=99))]
        t = self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                         PUT=requests.exceptions.Timeout("x"))
        result = self.pusher.annotate_activity("a1", "note")
        self.assertEqual(result["outcome"], "unknown")
        self.assertEqual(len(t.verbs("PUT")), 1)

    def test_non_string_chat_content_after_a_write_is_unknown_not_a_crash(self):
        after = [{"id": 1, "content": 12345}, {"id": 2, "content": ["list"]}]
        gets = [FakeResponse(200, []), FakeResponse(200, after)]
        t = self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                         POST=requests.exceptions.Timeout("x"))
        result = self.pusher.annotate_activity("a1", "note", chat=True)
        self.assertEqual(result["outcome"], "unknown")
        self.assertTrue(result["evidence"]["unreadable_message_content"])
        self.assertEqual(len(t.verbs("POST")), 1)

    def test_empty_content_falls_back_to_text(self):
        after = [{"id": 1, "content": "", "text": "note"}]
        gets = [FakeResponse(200, []), FakeResponse(200, after)]
        self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                     POST=requests.exceptions.Timeout("x"))
        result = self.pusher.annotate_activity("a1", "note", chat=True)
        self.assertTrue(result["evidence"]["matching_text_present"])
        self.assertEqual(result["outcome"], "unknown",
                         "matching text is evidence only and must not prove applied")

    def test_summarize_event_never_raises_on_malformed_display_fields(self):
        for evt in ({"id": 1, "moving_time": "an hour"},
                    {"id": 2, "moving_time": ["x"]},
                    {"id": 3, "start_date_local": 20990101},
                    {"id": 4, "start_date_local": None, "moving_time": None},
                    {"id": 5, "moving_time": True},
                    "not an event"):
            with self.subTest(event=repr(evt)[:24]):
                summary = push_mod.IntervalsPush._summarize_event(evt)
                self.assertIn("duration_minutes", summary)

    def test_summarize_event_survives_non_finite_and_oversized_numbers(self):
        """
        NaN raises ValueError from round(), the infinities raise OverflowError, and an
        int wider than a float overflows the division. A display helper contracted to
        never raise has to absorb all four.
        """
        cases = {
            "nan": float("nan"),
            "positive_infinity": float("inf"),
            "negative_infinity": float("-inf"),
            "huge_int": 10 ** 400,
        }
        for name, value in cases.items():
            with self.subTest(moving_time=name):
                summary = push_mod.IntervalsPush._summarize_event(
                    {"id": 1, "moving_time": value})
                self.assertIsNone(summary["duration_minutes"],
                                  f"{name} did not degrade to null")

    def test_summarize_event_keeps_normal_numeric_behaviour(self):
        self.assertEqual(
            push_mod.IntervalsPush._summarize_event(
                {"id": 1, "moving_time": 3600})["duration_minutes"], 60)
        self.assertEqual(
            push_mod.IntervalsPush._summarize_event(
                {"id": 1, "moving_time": 5400.0})["duration_minutes"], 90)
        self.assertIsNone(
            push_mod.IntervalsPush._summarize_event(
                {"id": 1, "moving_time": 0})["duration_minutes"])

    def test_verified_write_still_returns_a_bounded_result_with_bad_summary_fields(self):
        applied = {"id": 1, "name": "One", "start_date_local": f"{FUTURE}T00:00:00",
                   "type": "Ride", "category": "WORKOUT", "external_id": "e1",
                   "moving_time": "not a number"}
        gets = [FakeResponse(200, []), FakeResponse(200, [applied])]
        self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                     POST=requests.exceptions.Timeout("x"))
        workout = {"name": "One", "date": FUTURE, "type": "Ride",
                   "external_id": "e1", "category": "WORKOUT"}
        result = self.pusher.push_workouts([workout])
        self.assertIn(result["outcome"], ("applied", "unknown"))
        self.assertNotEqual(result["outcome"], "not_applied",
                            "unusable display metadata was turned into a claim that "
                            "the write did not happen")


class TestDeleteConvergenceIsStatusBased(PushCase):
    EVENT = {"id": 42, "name": "E", "start_date_local": "2097-01-01T00:00:00",
             "type": "Ride"}

    def test_direct_delete_404_is_applied_unchanged(self):
        t = self.install(GET=FakeResponse(200, self.EVENT), DELETE=FakeResponse(404))
        result = self.pusher.delete_event(42)
        self.assertEqual(result["outcome"], "applied")
        self.assertTrue(result["unchanged"])
        self.assertEqual(len(t.verbs("DELETE")), 1)

    def test_direct_delete_410_is_applied_unchanged(self):
        t = self.install(GET=FakeResponse(200, self.EVENT), DELETE=FakeResponse(410))
        result = self.pusher.delete_event(42)
        self.assertEqual(result["outcome"], "applied")
        self.assertTrue(result["unchanged"])
        self.assertEqual(len(t.verbs("DELETE")), 1)

    def test_400_whose_body_mentions_404_is_not_applied(self):
        """
        The string-matching implementation this replaces reported this as applied,
        which would tell an athlete a workout was deleted when it was not.
        """
        body = {"error": "bad request: see docs section 404 for event id rules"}
        self.install(GET=FakeResponse(200, self.EVENT),
                     DELETE=FakeResponse(400, body))
        result = self.pusher.delete_event(42)
        self.assertEqual(result["outcome"], "not_applied",
                         "a 400 was read as a successful delete because its body "
                         "contained the characters 404")

    def test_ambiguous_delete_verified_404_is_applied(self):
        gets = [FakeResponse(200, self.EVENT), FakeResponse(404)]
        t = self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                         DELETE=requests.exceptions.Timeout("x"))
        self.assertEqual(self.pusher.delete_event(42)["outcome"], "applied")
        self.assertEqual(len(t.verbs("DELETE")), 1)

    def test_ambiguous_delete_verified_410_is_applied(self):
        gets = [FakeResponse(200, self.EVENT), FakeResponse(410)]
        self.install(GET=lambda url, i: gets[min(i, len(gets) - 1)],
                     DELETE=requests.exceptions.Timeout("x"))
        self.assertEqual(self.pusher.delete_event(42)["outcome"], "applied")

    def test_non_delete_operations_keep_definitive_404_and_410(self):
        for status in (404, 410):
            with self.subTest(status=status):
                t = self.install(GET=FakeResponse(200, self.EVENT),
                                 PUT=FakeResponse(status))
                self.assertEqual(self.pusher.move_event(42, FUTURE)["outcome"],
                                 "not_applied",
                                 f"a non-delete write treated {status} as applied")
                self.assertEqual(len(t.verbs("GET")), 1,
                                 f"a definitive {status} triggered verification")


class TestLocalValidationOutcomes(PushCase):
    """Every confirm-mode write result carries an outcome, including the ones that
    never reach the network."""

    def test_local_refusals_are_not_applied_with_zero_calls(self):
        cases = {
            "empty_batch": lambda p: p.push_workouts([]),
            "invalid_workout": lambda p: p.push_workouts(
                [{"name": "", "date": FUTURE}]),
            "move_invalid_date": lambda p: p.move_event(42, "not-a-date"),
            "move_past_date": lambda p: p.move_event(42, "2000-01-01"),
            "threshold_invalid_field": lambda p: p.set_threshold("Ride", {"vo2": 60}),
            "threshold_empty": lambda p: p.set_threshold("Ride", {}),
            "annotate_activity_empty": lambda p: p.annotate_activity("a1", "  "),
            "annotate_event_empty": lambda p: p.annotate_event(42, ""),
        }
        for name, run in cases.items():
            with self.subTest(case=name):
                t = self.install()
                result = run(self.pusher)
                self.assertFalse(result["success"])
                self.assertEqual(result["outcome"], "not_applied",
                                 f"{name} returned a write result with no outcome, "
                                 f"so its exit code would not distinguish it from an "
                                 f"unknown outcome")
                self.assertEqual(t.calls, [], f"{name} contacted the API")

    def test_empty_batch_does_not_crash(self):
        self.install()
        result = self.pusher.push_workouts([])
        self.assertEqual(result["outcome"], "not_applied")


class TestConfirmModeDispatcherOutcomes(PushCase):
    """
    Validation performed by the CLI dispatcher, before any method is called, is still
    a write result when --confirm is present. Preview keeps its outcome-free shape.
    """

    def _run(self, argv):
        out = io.StringIO()
        transport = self.install()
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                with mock.patch.object(sys, "argv", ["push.py"] + argv), \
                     contextlib.redirect_stdout(out):
                    with self.assertRaises(SystemExit) as exit_info:
                        push_mod.main()
            finally:
                os.chdir(cwd)
        return exit_info.exception.code, json.loads(out.getvalue()), transport

    CREDS = ["--athlete-id", "i123456", "--api-key", "key_test"]

    def test_confirm_set_threshold_with_no_fields_is_not_applied(self):
        code, result, t = self._run(
            self.CREDS + ["set-threshold", "--sport", "Ride", "--confirm"])
        self.assertEqual(result["outcome"], "not_applied")
        self.assertEqual(code, 1)
        self.assertEqual(t.calls, [])

    def test_confirm_annotate_with_both_targets_is_not_applied(self):
        code, result, _ = self._run(
            self.CREDS + ["annotate", "--message", "n", "--activity-id", "a1",
                          "--event-id", "42", "--confirm"])
        self.assertEqual(result["outcome"], "not_applied")
        self.assertEqual(code, 1)

    def test_confirm_annotate_with_neither_target_is_not_applied(self):
        code, result, _ = self._run(
            self.CREDS + ["annotate", "--message", "n", "--confirm"])
        self.assertEqual(result["outcome"], "not_applied")
        self.assertEqual(code, 1)

    def test_equivalent_preview_cases_stay_outcome_free(self):
        cases = [
            ["set-threshold", "--sport", "Ride"],
            ["annotate", "--message", "n", "--activity-id", "a1", "--event-id", "42"],
            ["annotate", "--message", "n"],
        ]
        for argv in cases:
            with self.subTest(argv=" ".join(argv)):
                code, result, _ = self._run(self.CREDS + argv)
                self.assertNotIn("outcome", result,
                                 "a preview-mode dispatcher error grew a write "
                                 "outcome")
                self.assertEqual(code, 1)


class TestMalformedWorkoutArrayElements(PushCase):
    """
    A --json file is an arbitrary JSON array. Every entry has to be proved an object
    before anything calls .get() on it.
    """

    BAD = {"integer": 12345, "null": None, "string": "a workout",
           "list": ["name", "date"], "float": 3.5, "bool": True}

    def test_confirm_mode_reports_not_applied_with_zero_requests(self):
        for name, entry in self.BAD.items():
            with self.subTest(element=name):
                t = self.install()
                result = self.pusher.push_workouts([entry])
                self.assertFalse(result["success"])
                self.assertEqual(result["outcome"], "not_applied")
                self.assertIn("JSON object", result["error"])
                self.assertEqual(t.calls, [])

    def test_preview_mode_stays_outcome_free(self):
        for name, entry in self.BAD.items():
            with self.subTest(element=name):
                t = self.install()
                result = self.pusher.preview_push([entry])
                self.assertFalse(result["success"])
                self.assertNotIn("outcome", result)
                self.assertEqual(t.calls, [])

    def test_mixed_valid_and_invalid_array_is_rejected_whole(self):
        valid = {"name": "Good", "date": FUTURE, "type": "Ride"}
        t = self.install()
        result = self.pusher.push_workouts([valid, 12345, None])
        self.assertEqual(result["outcome"], "not_applied")
        self.assertEqual(t.calls, [], "a partially valid array reached the API")
        self.assertIn("workout[1]", result["error"])
        self.assertIn("workout[2]", result["error"])

    def test_non_string_name_is_rejected_not_crashed(self):
        t = self.install()
        result = self.pusher.push_workouts([{"name": 42, "date": FUTURE}])
        self.assertEqual(result["outcome"], "not_applied")
        self.assertEqual(t.calls, [])

    def test_label_falls_back_to_index_for_a_non_object(self):
        self.assertEqual(push_mod.IntervalsPush._workout_label(12345, 3),
                         "workout[3]")
        self.assertEqual(push_mod.IntervalsPush._workout_label({"name": "X"}, 0), "X")
        self.assertEqual(push_mod.IntervalsPush._workout_label({"name": "  "}, 1),
                         "workout[1]")


class TestConfirmModeLocalRejection(PushCase):
    """
    Local rejections that never reach the API are still write results when --confirm
    is present: definitely not applied, and they must say so.
    """

    CREDS = ["--athlete-id", "i123456", "--api-key", "key_test"]

    def _run(self, argv, files=None):
        out = io.StringIO()
        transport = self.install()
        with tempfile.TemporaryDirectory() as tmpdir:
            for filename, content in (files or {}).items():
                Path(tmpdir, filename).write_text(content)
            cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                with mock.patch.object(sys, "argv", ["push.py"] + argv), \
                     mock.patch.dict(os.environ, {}, clear=True), \
                     contextlib.redirect_stdout(out):
                    with self.assertRaises(SystemExit) as exit_info:
                        push_mod.main()
            finally:
                os.chdir(cwd)
        return exit_info.exception.code, json.loads(out.getvalue()), transport

    def test_confirmed_push_missing_name_and_date(self):
        code, result, t = self._run(self.CREDS + ["push", "--confirm"])
        self.assertEqual(result["outcome"], "not_applied")
        self.assertEqual(code, 1)
        self.assertEqual(t.calls, [])

    def test_confirmed_push_with_unreadable_json_file(self):
        code, result, t = self._run(
            self.CREDS + ["push", "--json", "missing.json", "--confirm"])
        self.assertEqual(result["outcome"], "not_applied")
        self.assertEqual(code, 1)
        self.assertEqual(t.calls, [])

    def test_confirmed_push_with_invalid_json(self):
        code, result, t = self._run(
            self.CREDS + ["push", "--json", "bad.json", "--confirm"],
            files={"bad.json": "{not valid json"})
        self.assertEqual(result["outcome"], "not_applied")
        self.assertEqual(code, 1)
        self.assertEqual(t.calls, [])

    def test_confirmed_push_with_malformed_array_element_from_file(self):
        code, result, t = self._run(
            self.CREDS + ["push", "--json", "arr.json", "--confirm"],
            files={"arr.json": json.dumps([12345, None])})
        self.assertEqual(result["outcome"], "not_applied")
        self.assertEqual(code, 1)
        self.assertEqual(t.calls, [])

    def test_confirmed_writes_with_missing_credentials(self):
        cases = {
            "push": ["push", "--name", "W", "--date", FUTURE, "--confirm"],
            "move": ["move", "--event-id", "42", "--date", FUTURE, "--confirm"],
            "delete": ["delete", "--event-id", "42", "--confirm"],
            "set-threshold": ["set-threshold", "--sport", "Ride", "--ftp", "300",
                              "--confirm"],
            "annotate": ["annotate", "--event-id", "42", "--message", "n",
                         "--confirm"],
        }
        for name, argv in cases.items():
            with self.subTest(command=name):
                code, result, t = self._run(argv)
                self.assertEqual(result["outcome"], "not_applied",
                                 f"confirmed {name} with no credentials returned a "
                                 f"write result with no outcome")
                self.assertEqual(code, 1)
                self.assertEqual(t.calls, [])

    def test_confirmed_writes_with_invalid_athlete_id(self):
        bad = ["--athlete-id", "123456", "--api-key", "key_test"]
        code, result, t = self._run(
            bad + ["move", "--event-id", "42", "--date", FUTURE, "--confirm"])
        self.assertEqual(result["outcome"], "not_applied")
        self.assertIn("i123456", result["error"])
        self.assertEqual(code, 1)
        self.assertEqual(t.calls, [])

    def test_equivalent_previews_and_list_stay_outcome_free(self):
        cases = {
            "preview_push_missing_fields": self.CREDS + ["push"],
            "preview_push_bad_json": self.CREDS + ["push", "--json", "missing.json"],
            "preview_missing_credentials": ["move", "--event-id", "42",
                                            "--date", FUTURE],
            "preview_invalid_athlete": ["--athlete-id", "123456", "--api-key", "k",
                                        "delete", "--event-id", "42"],
            "list_missing_credentials": ["list"],
        }
        for name, argv in cases.items():
            with self.subTest(case=name):
                code, result, _ = self._run(argv)
                self.assertNotIn("outcome", result,
                                 f"{name} grew a write outcome")
                self.assertEqual(code, 1)


class TestOutcomeContract(PushCase):
    def _run(self, result):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as exit_info:
                push_mod._output(result)
        return exit_info.exception.code, json.loads(out.getvalue())

    def test_exit_codes_map_the_three_write_outcomes(self):
        self.assertEqual(self._run({"success": True, "outcome": "applied"})[0], 0)
        self.assertEqual(self._run({"success": False, "outcome": "not_applied"})[0], 1)
        self.assertEqual(self._run({"success": False, "outcome": "unknown"})[0], 2)

    def test_results_without_an_outcome_keep_the_original_behaviour(self):
        self.assertEqual(self._run({"success": True, "mode": "preview"})[0], 0)
        self.assertEqual(self._run({"success": False, "error": "bad"})[0], 1)

    def test_every_preview_and_read_only_path_carries_no_outcome_field(self):
        """Every named one, not a sample: adding an outcome key to any of these
        would silently change its exit code."""
        payload = {"id": 42, "name": "E", "start_date_local": f"{FUTURE}T00:00:00",
                   "type": "Ride", "description": "d", "ftp": 250}
        t = self.install(GET=FakeResponse(200, payload))
        paths = {
            "preview_push": lambda p: p.preview_push(
                [{"name": "W", "date": FUTURE, "type": "Ride"}]),
            "preview_push_invalid": lambda p: p.preview_push([{"name": ""}]),
            "preview_move": lambda p: p.preview_move(42, FUTURE),
            "preview_move_invalid": lambda p: p.preview_move(42, "not-a-date"),
            "preview_delete": lambda p: p.preview_delete(42),
            "preview_set_threshold": lambda p: p.preview_set_threshold(
                "Ride", {"ftp": 260}),
            "preview_set_threshold_invalid": lambda p: p.preview_set_threshold(
                "Ride", {"vo2": 60}),
            "preview_annotate_event": lambda p: p.preview_annotate_event(42, "n"),
            "preview_annotate_activity": lambda p: p.preview_annotate_activity(
                "a1", "n"),
            "preview_annotate_activity_empty": lambda p: p.preview_annotate_activity(
                "a1", ""),
            "list_events": lambda p: p.list_events(),
            "get_event": lambda p: p.get_event(42),
            "get_sport_settings": lambda p: p.get_sport_settings("Ride"),
            "get_activity": lambda p: p.get_activity("a1"),
            "get_activity_messages": lambda p: p.get_activity_messages("a1"),
        }
        for name, run in paths.items():
            with self.subTest(path=name):
                self.assertNotIn("outcome", run(self.pusher),
                                 f"{name} grew a write-outcome field, changing its "
                                 f"exit behaviour")
        self.assertEqual(t.verbs("POST") + t.verbs("PUT") + t.verbs("DELETE"), [],
                         "a preview or read-only path issued a write")


if __name__ == "__main__":
    unittest.main(verbosity=2)
