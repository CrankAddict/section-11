"""
Smoke tests for push.py: the preview paths write nothing, and the CLI defaults
to preview.

Standard library only: unittest and unittest.mock, no third-party test packages,
no real athlete data, no network, no credentials. Every payload is synthetic and
built inline. Importing push.py itself needs nothing beyond the standard library,
since push.py imports `requests` lazily and this suite never lets it do so. The
run still shares an interpreter with the sync tests, so use the one that runs
sync.py.

Run from the repository root:

    python3 -m unittest discover dev/tests

Use the same interpreter or virtual environment that runs sync.py.

push.py has no module-level `requests` attribute. It binds a module global
`_requests` on first use via `_ensure_requests()`, so the seam these tests use is
`push_mod._requests`. Replacing it with a recording transport is what makes the
"no write occurred" assertions mean something: the transport refuses POST, PUT and
DELETE outright, so a preview path that regressed into a write fails loudly rather
than silently succeeding.

Scope is deliberately narrow. This is the smoke test that lets the harness cover
push.py at all. It is not coverage of push.py's write paths, its validation rules,
or its error handling.
"""

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _harness import (NetworkBlocked, PUSH_PATH, REPO_ROOT, RefuseEverything,
                      load_module_by_path)

push_mod = load_module_by_path("s11_push", PUSH_PATH)


# ── network guard ────────────────────────────────────────────────────────────

# push.py wraps almost every call site in `except Exception`, converting any
# error into {"success": False, ...}. An Exception-derived guard would therefore
# be swallowed and a test could assert "no write happened" while nothing ran at
# all. NetworkBlocked derives from BaseException so it propagates.
#
# The module global is saved at import, installed in setUpModule and restored in
# tearDownModule, so this module cannot leave push.py holding a test double,
# including after a failing run and including during discovery's import phase.

_ORIGINAL_REQUESTS = push_mod._requests


def setUpModule():
    """Activate the guard only once this module's tests are about to run.

    Same lifecycle as the fetch-state module: importing this file must not leave
    push.py holding a test double, because discovery imports every test module
    before running any of them. The seam differs, though, and deliberately stays
    different: push.py has no module-level `requests`, so the whole lazily-bound
    `_requests` object is what gets replaced.
    """
    try:
        push_mod._requests = RefuseEverything()
    except BaseException:
        push_mod._requests = _ORIGINAL_REQUESTS
        raise


def tearDownModule():
    """Put push.py's lazy requests binding back, whatever the outcome of the run."""
    push_mod._requests = _ORIGINAL_REQUESTS


# ── synthetic transport ──────────────────────────────────────────────────────

class FakeResponse:
    """
    Minimal stand-in for a requests Response.

    status_code and headers exist because push.py v0.6 inspects the status before
    deciding whether a read is eligible for retry. They are not what these tests are
    about; they are the smallest shape that lets the real code path run.
    """

    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.headers = {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _fixture_for(url):
    """Synthetic payloads keyed off the endpoint shape. No recorded traffic."""
    if "sport-settings" in url:
        return {"ftp": 250, "indoor_ftp": 240, "lthr": 160, "max_hr": 185}
    if "/activity/" in url:
        return {
            "id": "a1",
            "name": "Synthetic Activity",
            "start_date_local": "2099-01-01T00:00:00",
            "description": "existing text",
        }
    return {
        "id": 42,
        "name": "Synthetic Endurance",
        "start_date_local": "2099-01-01T00:00:00",
        "type": "Ride",
    }


class RecordingTransport:
    """Stands in for `requests`. Reads return fixtures; writes are refused."""

    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url))
        return FakeResponse(_fixture_for(url))

    def post(self, url, **kwargs):
        self.calls.append(("POST", url))
        raise NetworkBlocked("POST issued on a path that must not write")

    def put(self, url, **kwargs):
        self.calls.append(("PUT", url))
        raise NetworkBlocked("PUT issued on a path that must not write")

    def delete(self, url, **kwargs):
        self.calls.append(("DELETE", url))
        raise NetworkBlocked("DELETE issued on a path that must not write")

    @property
    def writes(self):
        return [c for c in self.calls if c[0] != "GET"]


WORKOUT = {
    "name": "Synthetic Endurance",
    "date": "2099-01-01",
    "type": "Ride",
    "duration_minutes": 90,
    "tss": 70,
}


class PushSmokeCase(unittest.TestCase):
    """Installs a fresh recording transport per test and restores the guard after."""

    def setUp(self):
        self.transport = RecordingTransport()
        self._saved = push_mod._requests
        push_mod._requests = self.transport
        self.pusher = push_mod.IntervalsPush("i123456", "key_test")

    def tearDown(self):
        push_mod._requests = self._saved


# ── previews must not write ──────────────────────────────────────────────────

class TestPreviewPathsMakeNoWrite(PushSmokeCase):
    def test_preview_push_makes_no_http_call_at_all(self):
        result = self.pusher.preview_push([WORKOUT])
        self.assertTrue(result["success"], f"preview_push rejected a valid workout: {result}")
        self.assertEqual(result["mode"], "preview",
                         "preview_push did not report preview mode")
        self.assertEqual(self.transport.calls, [],
                         "preview_push contacted the API; it is meant to be pure")

    def test_read_only_previews_use_get_only(self):
        previews = [
            ("preview_move", self.pusher.preview_move(42, "2099-01-02")),
            ("preview_delete", self.pusher.preview_delete(42)),
            ("preview_set_threshold", self.pusher.preview_set_threshold("Ride", {"ftp": 260})),
            ("preview_annotate_event", self.pusher.preview_annotate_event(42, "note text")),
            ("preview_annotate_activity", self.pusher.preview_annotate_activity("a1", "note text")),
        ]
        for name, result in previews:
            self.assertTrue(result["success"], f"{name} failed against synthetic data: {result}")

        self.assertEqual(self.transport.writes, [],
                         "a preview path issued a write to the calendar")
        self.assertTrue(self.transport.calls,
                        "no GET recorded, so the previews never reached the fixtures "
                        "and their success values prove nothing")

    def test_write_blocker_is_load_bearing(self):
        """Negative control. If this stops raising, the assertions above are hollow."""
        with self.assertRaises(NetworkBlocked):
            self.pusher.move_event(42, "2099-01-02")
        self.assertEqual([c[0] for c in self.transport.writes], ["PUT"],
                         "move_event did not attempt the write the blocker exists to catch")


# ── CLI dispatch ─────────────────────────────────────────────────────────────

class TestCliDefaultDispatch(PushSmokeCase):
    """Drives the real argparse parser, so the default of --confirm is proven."""

    ARGV = [
        "--athlete-id", "i123456", "--api-key", "key_test",
        "push", "--name", "Synthetic Endurance", "--date", "2099-01-01",
        "--duration", "90", "--tss", "70",
    ]

    def _run_main(self, argv):
        """Run main() in a temporary cwd so no real .sync_config.json can be read."""
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                with mock.patch.object(sys, "argv", ["push.py"] + argv), \
                     contextlib.redirect_stdout(stdout):
                    with self.assertRaises(SystemExit):
                        push_mod.main()
            finally:
                os.chdir(original_cwd)
        return stdout.getvalue()

    @staticmethod
    def _recorders(seen):
        def preview(self, workouts):
            seen.append("preview")
            return {"success": True, "mode": "preview"}

        def write(self, workouts):
            seen.append("write")
            return {"success": True}

        return (mock.patch.object(push_mod.IntervalsPush, "preview_push", preview),
                mock.patch.object(push_mod.IntervalsPush, "push_workouts", write))

    def test_default_selects_preview(self):
        seen = []
        preview_patch, write_patch = self._recorders(seen)
        with preview_patch, write_patch:
            self._run_main(self.ARGV)
        self.assertEqual(seen, ["preview"],
                         "push without --confirm did not dispatch to the preview path")
        self.assertEqual(self.transport.writes, [],
                         "the default CLI path issued a write")

    def test_confirm_selects_the_write_path(self):
        """Mirror of the above. Without it, the default test proves nothing."""
        seen = []
        preview_patch, write_patch = self._recorders(seen)
        with preview_patch, write_patch:
            self._run_main(self.ARGV + ["--confirm"])
        self.assertEqual(seen, ["write"],
                         "--confirm did not dispatch to the write path")


if __name__ == "__main__":
    unittest.main(verbosity=2)
