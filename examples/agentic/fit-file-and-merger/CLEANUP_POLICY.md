# Cleanup policy

Deletion rules and the gates in front of them. Read
[ARCHITECTURE.md](ARCHITECTURE.md) first for how the merged activity is produced.

## The governing rule

**A successful upload is not evidence that the upload is correct.**

An HTTP success tells you bytes were transmitted. It does not tell you the platform stored
what you sent, that the fields survived the import, or that downstream services received the
result. Every source recording is unrecoverable once deleted from every platform, so the
pipeline treats deletion as the last step of a verification chain, not as the cleanup half of
an upload.

Merge and upload are one operation. Cleanup is a separate one. They never run as a single
transaction, and a failure in cleanup never rolls back or re-runs an upload.

## Verification gates as implemented

The gates are not uniform across platforms. What follows is what the code does, in the order
it does it. Anything the design calls for but the code does not do is listed under
[Current gaps](#current-gaps) rather than described here as a guarantee.

Applies to every item, before any deletion on any platform:

1. **The merged activity exists on the upload target.** Located by start time, duration and
   distance tolerances, explicitly excluding the recorded source activity ids so a source
   cannot be mistaken for the output. Where several activities qualify, the lowest-scored
   candidate is taken and no ambiguity is raised.
2. **The merged activity is downloaded and inspected.** Not the local file that was uploaded:
   the copy the platform stored. AlphaHRV and temperature are presence checks. Left/right
   balance and enhanced respiration counts must match the merge exactly, but only where the
   merge recorded a count greater than zero; a recorded zero disables that comparison. Device
   identity, timeline and per-sample values are not checked.

Then, per platform:

| Step | Gate before deleting | Confirmation after deleting |
|------|----------------------|-----------------------------|
| Analysis platform (Intervals.icu) | The recorded head-unit source and merge are matched by exact Garmin external ids. Ambiguous or overlapping ids block cleanup. A missing merge always waits. | HTTP 200/204/404 completes that exact source request. HTTP 202 records an outstanding request and waits for later listing absence without resubmitting. No separate readback for synchronous success. |
| Upload target (Garmin), trigger-first item | Waits for the merged activity to be verified on the analysis platform, when analysis-platform cleanup is enabled. If that cleanup is disabled, the wait does not apply. | Each successful deletion or accepted exact-target 404 is checkpointed. Non-delete 404s and non-404 errors cannot mark a source deleted. No independent server readback. |
| Upload target (Garmin), file-first item | **No downstream wait.** The source is deleted once the merged activity has passed step 2, whether or not it has appeared on the analysis platform. | None, as above. |
| Strava | Waits until analysis-platform cleanup has completed, when that cleanup is enabled. Trigger-first: requires exactly one positively identified native activity and at most one of each import, with every candidate classified; the protected activity is re-read and re-confirmed as native immediately before any sibling is deleted. File-first: the candidate closest to the merge is kept only if its distance matches the merge within a small tolerance, and exactly one other candidate is deleted. | Yes. The cached read is invalidated and the API is queried again; an activity that still exists is an error. |
| Zwift Companion | Waits for upload-target and analysis-platform cleanup to complete, each when its cleanup is enabled. Requires three distinct recorded activity ids, exactly one protected native card, at most one of each import, and a consistent time label across them. Only cards exposing an imported-activity delete control are eligible. | Yes. The feed is reloaded after each deletion and again at the end; success requires the native card present and both imports absent. |

**Strava late-duplicate watch (trigger-first only).** When the protected native activity is
present but one or both imports are not, the imports that are present are deleted and the
item stays pending, with a healthy exit, for up to 24 hours from that first partial match. It
is rechecked 30 minutes and 2 hours into the watch and at its deadline, not on every scheduler
run. An import that appears during the watch is deleted normally. If none appears by the
deadline, the step completes without it. File-first items have no watch: a single candidate
that matches the merge completes the step immediately.

## Fail-closed conditions

Where a gate exists, an unsatisfied gate stops that platform's work for that pass and leaves
the source in place. The scope column matters: these are not all global.

| Condition | Scope | Behaviour |
|-----------|-------|-----------|
| Merged activity not found yet | All platforms for that item | Wait at least five minutes. Later items can progress. |
| Merged activity missing required fields, or a recorded non-zero count does not match | All platforms for that item | Persist a deterministic block. Nothing is deleted and the merged id is not recorded as verified. No automatic retry until reviewed. |
| Merged activity not yet present on the analysis platform | Analysis platform always; upload target for trigger-first items only | Wait. A file-first item's upload-target source is still deleted. |
| More than one candidate matches a duplicate role, or a candidate cannot be classified | Companion | Deterministic block. Exits unhealthy until reviewed. |
| The same, or the listing shows no native activity or more than one | Strava, trigger-first item | Nothing is deleted. The item stays pending with a healthy exit and no time limit, which the scheduler cannot tell apart from late sync. Inspect items still pending after the watch window. |
| No candidate, more than one duplicate, or a kept copy that does not match the merge | Strava, file-first item | Deterministic block. Not retried until reviewed, even when the cause is sync lag. |
| The activity to be preserved is missing, or no longer has the identity that made it protected | Strava, Companion | Stop. Treated as a hard block, not a retry. |
| Authentication expired | Per service | Garmin/Intervals 401/403 persist a service block for operator repair. Strava/Companion retain their minimum waits; failures remain unhealthy during recorded backoff. |
| Rate limited | Per service | Preserve Strava global limits; share Garmin/Intervals 429 backoff across items and honor exposed Retry-After. Do not poll each scheduler minute. |
| A delete attempt cannot be confirmed | Strava, Companion | Stop and record the failure. The item stays pending. |
| An activity feed or listing did not load | Companion | Treated as ambiguity. An empty view is never evidence that duplicates are gone. |
| An item is explicitly held | All platforms | Skipped entirely, regardless of every other condition. |

Two of these deserve emphasis, because they are the ones that look like success:

- **An empty result is not a clean result.** A feed that failed to load, a listing that lags,
  or a query that returned nothing all produce the same shape as "the duplicates are gone".
  The Companion path distinguishes them and defers.
- **Platform listings lag.** An activity deleted a moment ago can still appear, and a newly
  uploaded one can be missing. On Strava the post-delete check invalidates its cached read
  before re-querying. On the upload target and the analysis platform there is no post-delete
  check at all, so a deletion recorded as done is a deletion the client believes it made.

## Preview and approval: what is enforced and what is not

Cleanup has a dry-run mode that previews selected platforms without renaming or deleting
activities or saving cleanup progress. Live reads may refresh credentials, verification FIT
caches and shared rate-limit state, and a Companion preview starts the emulator and relaunches
the app. Existing blocks and backoff still apply.

**Running it first is an operator procedure, not an enforced gate.** Nothing in the code
requires a dry run before a live pass, and no per-item or per-deletion approval is requested
at run time. The intended habit is still:

1. Run the dry run.
2. Read the preserved activity and the deletion list, per platform.
3. Only then run live.

What is enforced is coarser: each platform's deletion is behind an independent flag. Three of
those flags default to on in the runner (upload target, analysis platform, Strava). The
Companion flag defaults to off and additionally requires the dry-run flag to be omitted.

Enabling a flag authorises the mechanism for every pending item, not a specific deletion. The
per-deletion protection is the gate table above, and that table is uneven. Treat a live run
with the default flags as authorisation to delete sources for every item that passes its
gates, because that is what it is.

## Per-platform final state

| Platform | Keep | Remove | Rationale |
|----------|------|--------|-----------|
| Upload target (Garmin) | The verified merged activity | The head-unit source activity, and the native virtual-platform source where one was imported | The merged activity supersedes both. A wait for downstream verification is enforced for trigger-first items, and only while analysis-platform cleanup is enabled. File-first items have no downstream wait. |
| Analysis platform (Intervals.icu) | The verified merged activity | The recorded head-unit source matched by its exact Garmin external id | The supplied implementation does not remove every possible synced original. Additional source roles need a separate policy change. |
| Strava | The native virtual-platform activity | The head-unit import and the merged trainer import | See the provenance note below. |
| Zwift Companion | The native virtual-platform activity | Imported head-unit and trainer copies | Same reason. Only cards that expose an imported-activity delete control are eligible, so a native activity cannot be deleted by this path even if matching went wrong. |
| Local caches | Source and merged FIT files | Nothing | Rollback evidence. Downstream success is not a reason to delete them. |

Note the asymmetry: the merged activity is authoritative on the upload target and the
analysis platform, while the native activity is authoritative on Strava and Companion. This
is deliberate, and it is the point of the policy.

## Current gaps

Hardening the policy above implies but the implementation does not do. Listed here so the
policy is not read as a description of what is enforced.

| Gap | Why it matters |
|-----|----------------|
| No post-delete read on the upload target or the analysis platform | A delete call that returned success but did not take effect is recorded as complete. A subsequent pass will not retry it. |
| Exact-target not-found is client evidence only | Garmin and Intervals can reconcile an absent target, but a misrouted response or invalid historical state is not disproved by a 404. Identity gates and operator review remain necessary. |
| File-first items delete the upload-target source without downstream verification | The source is removed while the merged activity may not yet have reached the analysis platform. The merged activity does remain on the upload target, and the local caches are intended as rollback evidence. Neither makes the exposure nil: redundancy is reduced at the moment the source goes, and the verification that authorised the deletion is itself incomplete, since it checks field presence and recorded counts but not identity, timeline or values. |
| No per-deletion approval | Flags authorise a mechanism for all pending items, not a reviewed deletion. |
| Merged-activity selection does not report ambiguity | Several qualifying candidates resolve silently to the closest one. |
| Obsolete earlier merged activities are neither tracked nor removed | They are not excluded from candidate selection either, since only recorded source ids are excluded. Worse, an item that already holds a verified merged id skips re-verification, so a stale id keeps being used. |
| File-first Strava has no late-duplicate watch | A single candidate matching the merge completes the step, so a source copy that syncs later remains. |
| Trigger-first Strava ambiguity does not alert | Nothing is deleted, but the scheduler sees a healthy exit indefinitely. Items that stay pending past the watch window need inspection. |
| Completion is relative to an explicit policy | Excluded destinations may still contain duplicates. Exclusion never sets deletion flags; an existing explicit policy can reopen unfinished work. Completed legacy records without a saved policy remain grandfathered by a persisted policy-origin marker until a reviewed migration replaces the policy and clears that marker. |

None of these is a reason to widen the flags. Each is a reason to run the dry run and read
its output.

## Provenance and racing integrity

On Strava and in Zwift Companion, the natively uploaded virtual-platform activity is
preserved and the merged copy is not substituted for it.

The native upload carries the virtual platform's own origin markers: its device name and its
platform-issued external identifier. Those markers are what associate the effort with the
platform that recorded it. A merged file re-uploaded from a trainer identity does not carry
them, however accurate its data.

Race and event results are commonly reviewed against the activity as the platform originally
published it. Deleting or replacing that activity removes the record a review would examine,
and can leave a result unverifiable or contested. Treat this as a safety rule rather than a
prediction: platforms differ, and their procedures change. The rule costs nothing when it is
unnecessary and is not recoverable when it turns out to have been necessary.

The corresponding technical control is that the preserved activity is identified positively,
by platform origin markers rather than by elimination, and is re-confirmed immediately before
any sibling is deleted. If the protected activity cannot be positively identified, nothing is
deleted.

## Recovery after interrupted cleanup

The cleanup implementation records verification and completed platform transitions immediately,
including individual Garmin outcomes and, for trigger-first items, individual Strava outcomes.
Item and platform failures are isolated; checkpoint failure stops all further remote work. A
crash between remote success and the local save remains possible, so exact-target absence must
be reconciled on restart.

Completion uses the saved explicit policy for both source modes. A disabled platform is
excluded only by an explicit policy, never by inventing a successful deletion. An isolated
manual command preserves saved obligations; enabling unfinished required work reopens an
item that already carries that policy. Completed legacy records without a saved policy retain
only destinations already recorded complete. A persisted grandfathered policy origin
keeps later runner flags from reopening them until a reviewed migration replaces the policy
and clears the marker. Companion can remain disabled while the three required core platforms
complete.

The verified merged id and cached verification FIT are reused. This avoids repeated downloads
but does not detect a subsequently removed or replaced merge. Replacement reconciliation
remains manual. Do not treat a saved id as fresh live verification.

Expected propagation waits, the trigger-first Strava late-duplicate watch and Strava rate waits
remain healthy pending states. Transport failures, Garmin and Intervals rate limits and
deterministic blocks remain unhealthy during backoff. Two Strava cases are easy to misread:
trigger-first ambiguity is a healthy pending state with no time limit, and file-first sync lag
can be a deterministic block (see [Fail-closed conditions](#fail-closed-conditions)). Unknown
deterministic failures require review; restarting the scheduler does not clear them.
See the deployment and bounded validation procedure in [RUNBOOK.md](RUNBOOK.md).
