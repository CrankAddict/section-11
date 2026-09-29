# Runbook

Operating procedures for the pipeline described in [ARCHITECTURE.md](ARCHITECTURE.md).
Deletion rules and their gates are in [CLEANUP_POLICY.md](CLEANUP_POLICY.md).

Paths, profile names, device names and schedules below are placeholders. Substitute your
own. Nothing in this package should be treated as a working configuration.

## Setup assumptions

| Requirement | Notes |
|-------------|-------|
| FIT File Faker installed in its own virtual environment | Supplies the CLI used as an upload fallback and the vendored `fit_tool` library every component imports. Pin the version you test against; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). |
| A Garmin Connect profile in the upstream tool's configuration | Credentials are read from that configuration and a token store is kept per profile. Never commit either. |
| An Intervals.icu API key | Used for the local activity mirror, and for downstream verification and duplicate removal. |
| Strava API credentials with refresh token | Read-only API access. Deletion is not available through the Strava API and is done through an authenticated browser session instead. |
| A browser profile with a logged-in Strava session | Used only for deletion. Expiry is detected and fails closed. |
| An Android emulator image with the Zwift Companion app, logged in | Optional. Only required for Companion cleanup. |
| A scheduler entry running the runner at a fixed interval | The runner is safe to run frequently: it takes a single-instance lock and does nothing when there is nothing to do. |

Secrets belong in files outside the repository with least-privilege access, or in the
platform keychain. No credential, token, account name, activity id or personal path should
ever appear in a committed file.

### Portability items to change before reuse

- The local timezone used to interpret mirror timestamps is a hard-coded default.
- The synthetic trainer identity encodes a specific trainer product and hardware serial.
  Substitute your own hardware, or accept that the output will claim a device you do not own.
- The trigger match depends on the exact activity name your head unit writes for indoor
  cycling.
- Cloud-folder discovery is written for a macOS file provider and its metadata index.

## Safety flags

Deployment and activation are separate steps. The runner reads flags from the environment so
code can ship disabled.

| Flag | Default | Effect |
|------|---------|--------|
| Trigger-first pipeline | Off | The whole trigger-first discovery, merge and upload branch is skipped. |
| Delete on Garmin | On | Allows source deletion on Garmin, still behind every verification gate. |
| Delete on Intervals.icu | On | Same, for Intervals. |
| Delete on Strava | On | Same, for Strava. |
| Delete Companion imports | Off | Companion cleanup is opt-in and additionally requires omitting the dry-run flag. |
| Discovery-only mode | Off | Lists the source files the process can see, then exits. Nothing is staged, merged or uploaded. |

Enabling a flag is not the same as approving a deletion. A flag authorises the mechanism for
every pending item; it is not a per-item or per-deletion gate, and nothing requires a dry run
first. The protections that do apply are uneven across platforms and are set out in
[CLEANUP_POLICY.md](CLEANUP_POLICY.md). Note that three of the four deletion flags default to
on, so a runner deployed with defaults will delete sources once an item passes its gates.

The runner passes an explicit required-platform policy derived from the enabled switches.
A manual subset of deletion flags preserves the saved completion policy. Only an explicit
replacement policy removes obligations; excluded platforms remain undeleted in state.
Completed legacy records without a saved policy retain the destinations already recorded
complete under a persisted grandfathered policy origin until an operator explicitly replaces
the policy and clears that origin. All switches off means no cleanup work, not proof that
duplicates are absent. Audit the effective scheduler environment rather than assuming script
defaults: a scheduler-level override wins. Disable a switch with an explicit off value; in the
reference runner an empty value falls back to the default, which is on for three of the four
deletion flags. Keep the Companion deletion flag off unless Companion deletion is separately
reviewed and approved.

## Normal automatic workflow

One scheduled run performs, in order:

1. **Lock.** If another run holds the lock and its process is alive, exit. A stale lock whose
   owner is gone is recovered.
2. **Trigger-first branch**, if enabled. Ingest new triggers from the local mirror. If one is
   due, look up its Garmin pair, download both files, merge, and write the output to a ready
   directory. Upload it raw. On success, record cleanup state and mark the trigger uploaded.
3. **File-first branch**, if the cloud folder is readable. Collect any DFA CSV exports, then
   stage new FIT files locally, skipping anything already uploaded.
4. **Per staged file:** attempt the donor merge. On success, upload raw and record cleanup
   state. On no-donor, apply the wait or fallback described below.
5. **Fallback upload.** Anything still sitting in the local inbox is handed to the upstream
   CLI's upload-all mode.
6. **Cleanup pass.** Reconcile each item against the selected completion policy and gates.
   Failed items do not stop later safe work. The runner propagates cleanup's nonzero
   exit and treats a missing cleanup executable as failure. Expected waits exit zero;
   errors and deterministic blocks remain nonzero even during their retry delay. A
   trigger-first Strava ambiguity is also a zero-exit pending state; see
   [CLEANUP_POLICY.md](CLEANUP_POLICY.md#fail-closed-conditions).

A run that finds nothing still does work: it refreshes and scans the cloud folder through
the file provider and its metadata index, and it invokes the upstream fallback upload scan
over the local inbox. What the regression tests establish is narrower and specific: trigger
discovery performs no Garmin login when idle or inside a retry backoff, and a cleanup pass
with no pending item performs no Garmin login either. Do not read that as zero network
activity for the runner as a whole.

## No-donor fallback

When a staged base file has no matching donor:

1. **Wait.** If the source file is younger than the donor wait window, the staged copy is
   discarded and the file is retried on the next run. This gives the head unit time to
   sync to Garmin. Uploading immediately would produce an activity with no DFA data and a
   duplicate to clean up later.
2. **CSV injection.** After the wait expires, a matching DFA CSV export is looked for. If one
   covers enough of the ride, its alpha1 and artifacts streams are injected as developer
   fields. This path exists for rides recorded without the head unit and is not the primary
   route.
3. **Identity-only rewrite.** Failing both, the file is rewritten to the trainer identity
   without donor fields and uploaded raw.

Each step degrades the result but never blocks the ride from reaching Garmin.

## Manual operations

All of these are separate commands against the same components. Read-only operations are
listed first.

| Operation | Purpose |
|-----------|---------|
| Discovery-only run | Show which source files this process can actually see. The first thing to run when a file appears in the cloud folder but nothing happens. |
| Find donor | Report the best-scoring Garmin donor for a given base file without merging. |
| Explicit merge | Merge a named base and donor into a named output. Takes an explicit source mode, a force flag for a base that already carries `Alpha1`, and a flag to waive the donor `Alpha1` requirement. |
| Identity-only rewrite | Rewrite a base file to the trainer identity with no donor. |
| Raw upload | Upload a prepared file to Garmin without the upstream metadata rewrite. |
| Cleanup dry run | Preview selected platforms without renaming, deleting activities or saving cleanup progress. Live reads can refresh credentials, verification caches and rate-limit state. A Companion preview starts the emulator and relaunches the app. |
| Strava dry run | The same, narrowed to Strava, optionally for one date. |
| Trigger reset | Return an abandoned or failed trigger to pending so the next run retries it. |

Run a cleanup dry run before any first live cleanup on a new setup, and after any change to
matching tolerances.

## Non-standard cases

### Donor starts late or stops late

Handled without intervention, with one caveat. The base timeline is authoritative: donor
samples with no matching base record are read but never copied. In the trigger-first mode a
donor that misses more than twenty percent of base records fails the overlap gate and no file
is produced.

The file-first mode has no overlap gate. A donor that satisfies the start and duration windows
is accepted on those alone, and a donor covering only part of the ride will produce a merged
file with donor-derived fields populated on some records and absent on others. Nothing
rejects that result. Check the reported matched-record count against the base record count
whenever a recording was interrupted.

### Split or multi-part base recording

Not supported. The merge accepts exactly one base and one donor, and pair selection returns
exactly one pair. There is no concatenation step.

The safe handling is to resolve the split before the pipeline sees it: either re-export a
single continuous file from the virtual platform, or treat one part as the ride and accept
the loss. Do not upload both parts and rely on cleanup to sort it out. How cleanup responds to
two overlapping bases has not been tested, and the merged-activity selection step takes the
closest qualifying candidate rather than reporting ambiguity, so a safe outcome should not be
assumed.

### Ride recorded without the head unit

Follows the no-donor fallback above. The result is a correctly identified virtual ride with
no donor-derived fields added. Fields the base file already carried are untouched, so
temperature, balance or respiration may still be present if the virtual platform wrote them.
Where the CSV fallback applied, it adds its own alpha1 and artifacts developer fields.
Cleanup for that item has no head-unit source duplicate to remove on Garmin.

### Replacement upload

**Not supported automatically. Handle this manually.**

When a merged activity has to be replaced, for example because a defect in an earlier merge
was found, the obsolete copy exists in two places: on the upload target and on the analysis
platform, which already synced it. Cleanup will not remove either. Cleanup state records the
original source recordings only; there is no field carrying an obsolete merged activity id
and no step that looks for one.

There is a second hazard. Merged-activity selection excludes the recorded source ids and then
takes the closest qualifying candidate. An obsolete merged activity left on the upload target
is not excluded, so it can be selected as the activity to verify. If it happens to satisfy
the field checks, cleanup will treat the old copy as the verified merge.

There is a third hazard, and it is the reason this cannot be finished by re-running cleanup.
If the item already carries a verified merged activity id, that id points at the obsolete
copy and verification is skipped on subsequent passes. Cleanup will then delete the original
source recordings against the stale selection.

Until explicit old and new merged ids are tracked, verified and reconciled in cleanup state,
the procedure is manual throughout:

1. Produce and upload the replacement.
2. Confirm by inspection which activity is the replacement and which is obsolete. Do not rely
   on cleanup to tell them apart.
3. Delete the obsolete copy manually on the upload target, and its synced duplicate on the
   analysis platform.
4. Do not simply re-run cleanup for that item. Its state may still hold the obsolete verified
   merged id, and reconciling that is an implementation-owner task, not an operator one.

Replacement handling, removal of the obsolete duplicates and reconciliation of cleanup state
are all manual and unsupported. Nothing in the pipeline detects the stale copy, and the
pipeline can act on it. Never delete the obsolete copy before the replacement has been
downloaded and checked.

## Recovery from partial failure

| Symptom | What actually happened | Action |
|---------|------------------------|--------|
| Upload succeeded but the activity was not renamed | Verification is checkpointed before rename; rename failure stops downstream work for that item. | Inspect the error. Transient failures retry after backoff; deterministic failures require review. Do not reset verified progress merely to retry naming. |
| Upload reported a conflict | Garmin already had the file. This is reported as a conflict, not an error. | Confirm the existing activity is the merged one, then let cleanup verify it normally. |
| Cleanup reports it is waiting for the merged Garmin activity | Processing may be delayed, or the activity falls outside the unchanged match windows. | Wait until the recorded retry time, at least five minutes. Persistent absence requires inspection, not wider tolerances. |
| Cleanup reports missing required fields | The verification gate failed and its step is blocked without automatic polling. | Compare the saved merge counts with a freshly downloaded result under separate authorization. Preserve cached evidence. Only after repair and review clear that step block; never set a verified or deleted flag by assumption. |
| Garmin source is gone but the analysis platform still shows it, item still pending | Intervals runs first, but Garmin's trigger-first gate requires the downstream merge, not completed source deletion. An Intervals error or pending 202 after merge verification can leave this state. File-first Garmin cleanup has no downstream gate. | Keep the Intervals flag enabled and respect its retry deadline. Confirm the retained merged activity; do not reset completed Garmin targets. |
| A disabled platform still has a duplicate on a completed item | Completion applies to the saved policy, not every possible destination. | Include that destination in the explicit policy and enable its deletion flag only after preview and authorization. Unfinished work reopens in both source modes. |
| Platform listings lag behind reality | A deleted source may still appear, or a merge may be absent. | Respect backoff. An exact-target Garmin delete 404 can reconcile absence; a lookup or rename 404 cannot. Intervals 202 remains pending until listing absence. Synchronous successful deletes still lack independent readback. |
| Strava authentication expired | A login redirect or missing delete control stops that target. Earlier sibling deletions may already have completed and been checkpointed. | Restore the browser session and respect the recorded backoff. Do not reset successfully reconciled targets. |
| Rate limit hit | Strava limits apply globally and are a healthy wait. Garmin/Intervals 429 deadlines are shared across items, and the pass exits nonzero until they pass. | Wait for the recorded deadline. Do not clear rate state to force retries. |
| Companion cleanup blocked as ambiguous | The feed did not show exactly one protected native activity and at most one of each import, or the saved Garmin ids were not distinct. | Inspect the feed manually. An unloaded or empty feed is treated as ambiguity, never as success. |
| Strava step blocked on a file-first item | Strava showed no candidate, more than one duplicate, or a kept copy that does not match the merge. Ordinary sync lag can cause this, and the block is not retried. | Confirm the Strava listing directly. When exactly the merge and one source copy are present, clear only that item's Strava step block and let the next pass re-match. |
| Trigger-first item still pending on Strava long after the ride | Either the late-duplicate watch, up to 24 hours, or an ambiguous Strava listing or one without exactly one native activity. Both exit zero. | If still pending after the watch deadline, inspect the listing for extra, missing or unclassified copies. Do not widen classification rules to force completion. |
| Cleanup stopped halfway through | Verified transitions, individual Garmin outcomes and trigger-first Strava outcomes are checkpointed. Companion reconciles its feed. A crash between remote success and checkpoint remains possible. | Resume with the same policy after inspecting the error. Exact-target absence reconciles a lost checkpoint; never bulk-mark pending flags complete. Persistence failure stops the whole pass. |
| A trigger was abandoned with no pair found | The Garmin pair never appeared within the retry window, or one half of it failed its metadata requirements. | Confirm both activities exist on Garmin with the required manufacturer and type, then reset the trigger to pending. |

## Deploying and validating cleanup changes

Deployment is separate from activation. Pause the scheduled runner first; installing a
cleanup change with default-on flags and an active scheduler would enable deletion. Back up
the script, the full runner and cleanup state without removing caches. Stage the exact change,
run the offline tests, and check integration against the complete runner, including its lock
and exit handling, rather than an excerpt.

Review every item the selected policy could reopen. Confirm that completed legacy records
without a saved policy remain grandfathered across repeated passes; migrate only individually
reviewed records when a new destination is intentionally required, replacing the saved policy
and clearing the grandfathered policy origin together. Before migrating a record whose
analysis-platform source was already removed, check that it carries the analysis-platform merge
confirmation; without it, the later Strava step waits indefinitely with a healthy exit while
analysis-platform cleanup is enabled. Keep unrelated work explicitly held during a
bounded recovery. Preserve existing verified ids, completed flags, per-target outcomes, watch
deadlines and rate limits. Do not manufacture completed deletion flags.

With separate live-read authorization, inspect the exact source and merged ids, download the
current merged FIT for field verification, and confirm the downstream merge and protected
native activity. Cached verification and a saved verified id do not prove current presence.
Run a deletion-free preview with the intended flags and policy. Preview can update local
credential, verification-cache or rate-limit data; it is not a filesystem-read-only command.

Only after approval of the concrete target list run one bounded live cleanup. Inspect JSON
health, saved transitions and exact platform results. Confirm retained activities directly.
A deterministic block requires correcting its cause and clearing only the reviewed
step record, item-level block, or shared authentication service block as applicable.
Never clear a rate deadline or delete evidence as a recovery shortcut.

Resume scheduling only after confirming that expected waits exit zero, actual failures stay
nonzero during backoff, and no unexpected items or destinations are enabled. Confirm the
effective scheduler command omits every disabled destination before the first restored run.
The deployed Garmin client version and its exception metadata must be validated before
activation whenever that dependency changes.

## What is never removed automatically

Local caches of the downloaded source files and the merged output are the rollback evidence
for everything above. Nothing deletes them, and successful downstream cleanup is not a reason
to. Keep them at least until the merged activity has survived a full sync cycle on every
platform you care about.
