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

**Shared helpers live in `_harness.py`.** The loader, the `NetworkBlocked` type,
the verb-seam installer and restorer, and the `RefuseEverything` object-seam
sentinel are shared by all four modules. There is no single guard installer,
because the two seams are not the same mechanism: the verb seam swaps named
attributes on a real module and restores them, while the object seam replaces one
lazily-bound object with `RefuseEverything` and assigns the saved original back. The leading underscore keeps the file outside
`unittest discover`'s `test*.py` pattern, so it is imported and never collected.
What it deliberately does not share is the seam: `sync.py` needs its named verbs
replaced with `requests.exceptions` left reachable, and `push.py` needs its
lazily-bound `_requests` object replaced wholesale. Those protect different code
and stay separate, and each module still owns its own `setUpModule` and
`tearDownModule`.

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

`test_http_policy.py` covers the HTTP policy added in `sync.py` v3.133 and
`push.py` v0.6. An AST guard walks `sync.py`, `push.py` and `pull.py` and fails if
any direct request carries no timeout, with a negative control that removes one
timeout from a copy of the real source and proves the same checker catches it.
Beyond that: retry eligibility by exception and status; the admission cap measured
from the start of the call, including time spent inside the request; the decision
to retry taken before sleeping, so an oversized `Retry-After` cannot buy a long
sleep followed by no request; the per-instance extra-attempt budget, shared across
a run and never reset; preservation of the original `RequestException` subclass so
`_build_health_context` still degrades rather than raising; the conditional
`chat_notes_status` marker and its consecutive-failure circuit breaker; the
`publish_to_github` pre-read gate, where only a confirmed 404 permits a create and
every other failed pre-read stops before the PUT; verification after an ambiguous
write on both services; and the `applied` / `not_applied` / `unknown` outcome
contract with its 0/1/2 exit codes. The load-bearing case is
`TestNoAutomaticReissue`, which drives all seven `push.py` write operations through
an ambiguous transport and asserts each verb was issued exactly once.

`test_push_smoke.py` covers the preview boundary in `push.py`: `preview_push`
makes no HTTP call at all; the read-only previews (move, delete, set-threshold and
both annotate forms) issue GET and never POST, PUT or DELETE; a negative control
proves the write blocker actually fires; and the CLI dispatches to preview by
default, with `--confirm` selecting the write path.

`test_workout_summary.py` covers the planned-workout `workout_summary` renderer in
`sync.py` v3.134 to v3.136 (issue #28): the two-step repeat, nested alternating and flat
alternating emitters assign no step role such as `rec`, however the targets
compare; an expansion oracle turns each summary back into ordered duration and
target steps and compares them with the synthetic `workout_doc`, so a dropped
step, a lost target or a reordering fails; the flat detector no longer skips the
step after a trailing rep. It also pins that the change is rendering only: which
workouts get a summary, the `×` / `sets` markers, `workout_summary_stats`,
`hard_sessions_planned` and the near/far tier fields equal constants captured from
v3.133, and the fictional `latest.example.json` interval summaries equal what the
producer emits. Content the renderer cannot show (a step without a duration, a
repeat block it cannot compress, the unmatched final child of a nested repeat, a
target it cannot print as W or bpm: a relative unit, range bounds, an empty or
null target, a string value) must appear as an in-place marker on every output
path. v3.136 adds repeat semantics (a nested repeat is shown as a repeat or marked,
never by its aggregate duration; a malformed repeat shape is marked), repeat-count
and duration validity (zero, negative, fractional, non-finite, boolean and string
values), and the 2 W tolerance checked on raw values before rounding. Every
fixture step and repeat declares its expected rendering when it is built (`P`,
`T`, `A`, `X`, `R`, `XR`), so the oracle never calls `sync.py` and never inspects
a count, duration, target or `steps` shape; it is shown to reject the outputs of
both rejected candidates. An unmarked summary is checked to list every step with
its duration and primary power or HR target, within the stated tolerance
(targets within 2 W and durations within 2 s of the first compressed step);
secondary targets such as cadence are out of scope. The three fixtures whose summary
availability v3.136 changes are listed and justified in the module. The PRE and
POST report templates are checked against the producer: they must name its
markers, keep the labelled-recovery rule and the stated scope of an unmarked
summary, and for a null or marked summary must name the description field that the
producer puts on each row tier, with the near/far boundary and preview length they
state matching the producer's. No report is rendered.

## Not covered

Everything else. No DFA computation, no report generation, and no `sync.py`
surface outside per-endpoint fetch state, HTTP policy and the `workout_summary`
renderer with its report-template field contract. `push.py` write paths are
covered for their transport behaviour and outcome classification only, not for
their validation rules or their calendar semantics. Treat this as focused regression guards, not as
coverage of the repository.
