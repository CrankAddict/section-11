# Developer validation

Maintainer validation material for this repository.

**If you are setting up Section 11 as an athlete, you do not need anything in this
folder.** `--init` and `--update` install it because the repository ships whole,
but nothing in the setup path, the protocol, the report templates or any user
workflow reads it or runs it. It can be ignored entirely.

The tests exist so that a change to `examples/sync.py` or
`examples/agentic/push.py` can be shown not to have broken behaviour that a live
run does not reach.

## Running

From the repository root:

```
python3 -m unittest discover dev/tests
```

**Run the suite with the same interpreter that runs `sync.py`.** The tests
themselves use only the standard library, but they import `sync.py`, which imports
`requests` at module scope. So the requirement is interpreter identity, not machine
identity: having a working `sync.py` somewhere on the machine is not enough if the
tests are launched from a different interpreter. `python3` above is a generic
example, and many platforms have no `python` executable at all.

If `sync.py` runs from a virtual environment, invoke that environment's Python, for
example `/path/to/.venv/bin/python -m unittest discover dev/tests`, or activate the
environment first.

Nothing else to install, no arguments, no configuration.

Local and manual by design. No CI, no hooks, no coverage tooling, no test
dependency.

## Conventions

**Standard library only.** `unittest` and `unittest.mock`, nothing else. No test
ever makes a network call: every HTTP boundary is patched, and each test module
installs a guard that raises a `BaseException` subclass if a call escapes anyway.
A guard deriving from `Exception` would not do, because both modules under test
catch broadly and would convert an unmocked call into an ordinary failure result,
letting the test pass without exercising anything.

**No real athlete data.** Every fixture is synthetic and built inline by a helper.
Real `latest.json` or `intervals.json` output must never be committed as a
fixture, including anonymised. If a test needs a shape that is awkward to
construct by hand, construct it by hand anyway. Scratch files a test writes go to
a `TemporaryDirectory` and are discarded with it.

**Modules are loaded by path.** `sync.py` and `push.py` live outside a package and
are not importable normally, so `importlib.util.spec_from_file_location` is used
against a path derived from `__file__`. Tests must not depend on the working
directory.

**Test behaviour, and say so when you cannot.** Assertions target state
transitions, retry deadlines, what survives a merge, and what a preview path is
allowed to do, so a refactor that preserves behaviour does not break the suite.
Where a helper is private and has no public entry point, the test binds it
directly on purpose. Much of the fetch-state suite does this, so this is not an
implementation independent suite and should not be described as one.

**Name the defect.** Where a test exists because something was once wrong, the
assertion message says what would break. "429 Retry-After leaked into a later
request" is more useful in a failure log than "assertion failed".

**Put back what you replace, and swap nothing at import time.** Each module
captures whatever it swaps on the HTTP layer when it is imported, installs the
guard in `setUpModule` and restores the saved value in `tearDownModule`, including
after a failing run. Installation is deferred deliberately: `unittest discover`
imports every test module before running any of them, so a guard installed at
import time would mutate the process-wide `requests` module while unrelated modules
are still importing, and anything that bound a verb by name in that window would
keep the blocker even after it was restored.

## Current coverage

`test_intervals_fetch_state.py` covers the per-endpoint fetch state in `sync.py`:
Retry-After parsing in both header forms and the guarantee that a value cannot
leak into the next request; the retry ladder and its boundaries; deadlines derived
from activity start; the paired-planned extension applying to intervals but never
to streams; expiry to tombstone; strict ID pairing with no date or sport fallback;
`zone_basis` resolution including the ambiguous and unresolvable cases;
partial-success handling in both orders; streams success requiring a usable
`dfa_a1`; `compute_error` held distinct from `no_data`; timeout and 5xx handling;
due-endpoint isolation; sibling-only merging without duplicate activity IDs; stale
`zone_basis` removal; state persistence across a restart; cache invalidation on
`script_hash` change; pruning by `present_activity_ids`; string key normalisation;
and retries reaching outside the 72-hour scan window.

It was written against `sync.py` v3.121 and Section 11 v11.53. That pairing is
provenance only. Behaviour is validated against the current `sync.py`.

`test_push_smoke.py` covers the preview boundary in `push.py`: `preview_push`
makes no HTTP call at all; the read-only previews (move, delete, set-threshold and
both annotate forms) issue GET and never POST, PUT or DELETE; a negative control
proves the write blocker actually fires; and the CLI dispatches to preview by
default, with `--confirm` selecting the write path.

## Not covered

Everything else. No DFA computation, no report generation, no `push.py` write
paths beyond proving the preview boundary holds, and no `sync.py` surface outside
per-endpoint fetch state. Treat this as two focused regression guards, not as
coverage of the repository.
