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
| Analysis platform (Intervals.icu) | Both the merged activity and the source are looked up by the upload target's activity ids. Merged present and source present: the source is deleted. Merged present and source absent: the step records the source as already absent and completes. Merged absent: the item waits, whether or not the source is there. | None. The delete call accepts HTTP 200, 202, 204 or 404 as success, with no confirming read. |
| Upload target (Garmin), trigger-first item | Waits for the merged activity to be verified on the analysis platform, when analysis-platform cleanup is enabled. If that cleanup is disabled, the wait does not apply. | None. Each deleted id is recorded immediately after the call returns, with no server readback. |
| Upload target (Garmin), file-first item | **No downstream wait.** The source is deleted once the merged activity has passed step 2, whether or not it has appeared on the analysis platform. | None, as above. |
| Strava | Waits until analysis-platform cleanup has completed, when that cleanup is enabled. Requires exactly one positively identified native activity and at most one of each import, with every candidate classified. The protected activity is re-read and re-confirmed as native immediately before any sibling is deleted. | Yes. The cached read is invalidated and the API is queried again; an activity that still exists is an error. |
| Zwift Companion | Waits for upload-target and analysis-platform cleanup to complete. Requires three distinct recorded activity ids, exactly one protected native card, at most one of each import, and a consistent time label across them. Only cards exposing an imported-activity delete control are eligible. | Yes. The feed is reloaded after each deletion and again at the end; success requires the native card present and both imports absent. |

## Fail-closed conditions

Where a gate exists, an unsatisfied gate stops that platform's work for that pass and leaves
the source in place. The scope column matters: these are not all global.

| Condition | Scope | Behaviour |
|-----------|-------|-----------|
| Merged activity not found yet | All platforms | Wait. Retry next pass. |
| Merged activity missing required fields, or a recorded non-zero count does not match | All platforms | Stop. Nothing is deleted and the merged id is not recorded as verified. |
| Merged activity not yet present on the analysis platform | Analysis platform always; upload target for trigger-first items only | Wait. A file-first item's upload-target source is still deleted. |
| More than one candidate matches a duplicate role, or a candidate cannot be classified | Strava, Companion | Stop as ambiguous. |
| The activity to be preserved is missing, or no longer has the identity that made it protected | Strava, Companion | Stop. Treated as a hard block, not a retry. |
| Authentication expired | Strava, Companion | Stop, record the reason, retry after a fixed backoff. |
| Rate limited | Strava | Stop for the whole run, not only the item that hit the limit. Retry after the platform's reset. |
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

Cleanup has a dry-run mode that reports exactly which activity it would delete on each
platform, which it would preserve, and why each step is or is not ready. It changes nothing.

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
| Analysis platform (Intervals.icu) | The verified merged activity | The source duplicates that synced from the upload target | Duplicate activities distort load and fitness calculations. |
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
| Analysis-platform deletion accepts a not-found response as success | A wrong id, or an id that never existed, is indistinguishable from a successful deletion. |
| File-first items delete the upload-target source without downstream verification | The source is removed while the merged activity may not yet have reached the analysis platform. The merged activity does remain on the upload target, and the local caches are intended as rollback evidence. Neither makes the exposure nil: redundancy is reduced at the moment the source goes, and the verification that authorised the deletion is itself incomplete, since it checks field presence and recorded counts but not identity, timeline or values. |
| No per-deletion approval | Flags authorise a mechanism for all pending items, not a reviewed deletion. |
| Merged-activity selection does not report ambiguity | Several qualifying candidates resolve silently to the closest one. |
| Obsolete earlier merged activities are neither tracked nor removed | They are not excluded from candidate selection either, since only recorded source ids are excluded. Worse, an item that already holds a verified merged id skips re-verification, so a stale id keeps being used. |
| File-first completion depends on the invocation | An isolated pass closes the item using only the flags that were enabled, leaving disabled platforms unfinished with no way to reopen. |

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

Cleanup is re-entrant by design. It records progress rather than assuming a pass completes.

- Per-platform completion flags are written as each platform finishes.
- Deleted activity ids are recorded individually, immediately, so a pass that stops between
  two deletions resumes at the second.
- A source that is already absent is recorded as handled rather than treated as an error.
- A verified merged activity id is stored once, so a later pass does not re-download and
  re-verify what has already passed.
- Completion is computed differently by mode. A trigger-first item uses a canonical
  four-platform contract: it closes only when the upload target, the analysis platform,
  Strava and Companion have all finished, regardless of which flags a given invocation had.
  A file-first item computes completion from the flags enabled for that invocation alone, so
  a single-flag pass can close it while the platforms whose flags were off still hold
  duplicates.
- Reopening is narrower still. A completed trigger-first item can be reopened for unfinished
  Companion cleanup. Nothing reopens a completed item for any other stage, and nothing
  reopens a completed file-first item at all.

The practical consequence: re-running cleanup after any interruption is safe and is the
correct first response. It does not repeat a deletion it has recorded, and it does not skip a
gate because an earlier pass got further. The caveat follows from the gaps above: on the
upload target and the analysis platform, "recorded" means the call returned, not that the
activity is confirmed gone, so a deletion that silently failed will not be retried.
