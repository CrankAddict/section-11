"""
Shared loading and network-guard helpers for the developer suite.

Not a test module. The leading underscore keeps it outside `unittest discover`'s
default `test*.py` pattern, so it is imported by the test modules and never
collected as one.

It exists because the suite reached three modules, which was the agreed point to
stop copying the same loader and the same guard lifecycle into each one. What it
does NOT do is unify the two seams:

  * `sync.py` imports `requests` at module scope and its fetchers reference
    `requests.exceptions` inside `except` clauses, so only the named verbs may be
    replaced and `requests.exceptions` must stay reachable.
  * `push.py` has no module-level `requests`. It binds a module global `_requests`
    lazily through `_ensure_requests()`, so the seam is that whole object.

Those are different mechanisms protecting different code, and collapsing them
would weaken both. So there is no single installer: the verb seam has
`install_verb_guard` / `restore_verb_guard`, and the object seam is just the
`RefuseEverything` sentinel, which a module assigns over the binding it saved and
assigns back on teardown. Each test module still owns its own `setUpModule` /
`tearDownModule` pair.

Nothing here mutates anything at import time. `unittest discover` imports every
test module before running any of them, so an import-time swap would leave the
process-wide HTTP layer mutated while unrelated modules are still importing, and
anything that bound a verb by name during that window would keep the blocker even
after it was restored.
"""

import importlib.util
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNC_PATH = REPO_ROOT / "examples" / "sync.py"
PUSH_PATH = REPO_ROOT / "examples" / "agentic" / "push.py"

HTTP_VERBS = ("get", "post", "put", "delete", "patch", "head", "options", "request")


def budget_test_start():
    """An explicit UTC test base, selectable without consulting wall time."""
    value = datetime.fromisoformat(os.environ.get(
        "S11_TEST_BUDGET_START", "2026-10-28T12:00:00+00:00"))
    if value.tzinfo is None or value.utcoffset().total_seconds() != 0:
        raise ValueError("S11_TEST_BUDGET_START must be an explicit UTC instant")
    return value.timestamp()


class BudgetClock:
    def __init__(self, stamp=None):
        self.now = budget_test_start() if stamp is None else stamp
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class BudgetDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls.fromtimestamp(budget_test_start(), timezone.utc)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


class NetworkBlocked(BaseException):
    """
    Raised when a test reaches the HTTP layer without patching it.

    Derives from BaseException on purpose. Both modules under test catch broadly:
    sync.py converts a RequestException into a ("transient", ...) result and push.py
    converts almost anything into {"success": False, ...}. An Exception-derived guard
    would be swallowed and a test could assert "no write happened" while nothing ran
    at all.
    """


def load_module_by_path(name, path):
    """
    Import a file that is not on sys.path and not part of a package.

    sync.py and push.py live outside any package, so the suite loads them from a
    path derived from __file__ and never from the working directory.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    if hasattr(module, "RequestBudget"):
        # Existing transport tests get a real, isolated controller and an elapsed
        # clock. Acceptance tests inject their own shared ledger explicitly.
        import tempfile

        def budget_factory(data_dir, caller, error_type, identity):
            from unittest import mock
            scratch = tempfile.TemporaryDirectory(prefix="request-budget-")
            clock = BudgetClock()
            with mock.patch.dict(os.environ, {"SECTION11_STATE_DIR": str(Path(scratch.name) / "request-budget")}):
                budget = module.RequestBudget(data_dir if data_dir is not None else scratch.name,
                                              caller, error_type, identity,
                                              clock=clock, sleep=clock.sleep,
                                              jitter=lambda: 0)
            budget._test_scratch = scratch
            return budget
        for name in ("IntervalsSync", "IntervalsPush"):
            cls = getattr(module, name, None)
            if cls is not None:
                cls._budget_factory = staticmethod(budget_factory)
    return module


def _blocked_verb(name):
    def _blocked(*args, **kwargs):
        raise NetworkBlocked(f"unmocked HTTP call: requests.{name}")
    return _blocked


class RefuseEverything:
    """Module-scope default for an object seam: any HTTP verb at all is a defect."""

    def __getattr__(self, name):
        return _blocked_verb(name)


def install_verb_guard(requests_module, verbs=HTTP_VERBS):
    """
    Replace named verbs on a real `requests` module, leaving everything else,
    `requests.exceptions` above all, reachable.

    Returns the saved originals for `restore_verb_guard`. On any failure part-way
    through, what was already replaced is put back before the error propagates.
    """
    originals = {name: getattr(requests_module, name)
                 for name in verbs if hasattr(requests_module, name)}
    replaced = []
    try:
        for name in originals:
            setattr(requests_module, name, _blocked_verb(name))
            replaced.append(name)
    except BaseException:
        for name in replaced:
            setattr(requests_module, name, originals[name])
        raise
    return originals


def restore_verb_guard(requests_module, originals):
    """Put the real verbs back, whatever the outcome of the run."""
    for name, fn in originals.items():
        setattr(requests_module, name, fn)
