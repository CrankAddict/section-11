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
6. **Cleanup pass.** Process every unfinished cleanup item under its gates.

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
| Cleanup dry run | Report exactly what cleanup would delete on each platform, and why it is or is not ready, changing nothing. |
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
| Upload succeeded but the activity was not renamed | The rename call failed and aborted the cleanup pass before its state was written. No deletion had occurred, because the rename runs before every deletion gate. | Re-run. The next pass re-verifies from scratch and retries the rename. |
| Upload reported a conflict | Garmin already had the file. This is reported as a conflict, not an error. | Confirm the existing activity is the merged one, then let cleanup verify it normally. |
| Cleanup reports it is waiting for the merged Garmin activity | Garmin has not finished processing, or the merged activity falls outside the start, duration or distance match window. | Wait one cycle. If it persists, check whether the uploaded activity's duration or distance drifted beyond the match window. |
| Cleanup reports missing required fields on the merged activity | One of several checks failed: no AlphaHRV record present, no temperature record present, or a mismatch against a recorded balance or respiration count that was greater than zero. This is the gate doing its job. | Do not override. Determine which of the checks failed, then compare the merge's reported values with the downloaded copy. |
| Garmin source is gone but the analysis platform still shows it, item still pending | Not an ordering effect: the normal pass processes the analysis platform before the upload target. It usually means the two deletion flags differed, or this was a file-first item whose upload-target deletion does not wait for downstream verification, or the analysis-platform listing was stale, or its delete call reported success without taking effect. | Re-run cleanup with the analysis-platform flag enabled. The step removes the source once both it and the merged activity are visible there. If it persists, check the platform directly, since that deletion has no post-delete confirmation. |
| Garmin source is gone but the analysis platform still shows it, item already marked complete | A file-first item closed by an isolated invocation that had only the upload-target flag enabled. File-first completion is computed from the flags of that invocation alone, and a completed file-first item is never reopened. | Re-running will not help: the item is no longer pending, and no ordinary rerun reopens it. Remove the downstream duplicate by hand, or have the implementation owner reconcile cleanup state. |
| Platform listings lag behind reality | An activity was deleted but still appears, or a new one has not appeared yet. | The pipeline treats an absent source as already handled and an absent merge as not ready. Both resolve on a later pass. Note the converse case is not detected: on the upload target and the analysis platform a delete call that returned success but did not take effect is recorded as done and will not be retried, so confirm those two manually if a duplicate persists. |
| Strava authentication expired | Detected explicitly, either as a login redirect or as a missing delete control on the activity page. Nothing was deleted. | Log the browser profile back in. The item retries after its backoff. |
| Strava rate limit hit | Recorded for the whole run, not just the item that hit it. | Wait. The recorded reset time governs the next attempt. |
| Companion cleanup blocked as ambiguous | The feed did not show exactly one protected native activity and at most one of each import, or the saved Garmin ids were not distinct. | Inspect the feed manually. An unloaded or empty feed is treated as ambiguity, never as success. |
| Cleanup stopped halfway through | Persistence differs by platform. The upload target saves its deleted-id list after each individual delete call. Analysis-platform and Strava flags are normally written at the end of the pass, so an abort can lose an in-memory flag for work that did complete. Companion keeps no per-card ids and reconciles by reloading the feed. | Re-run. Upload-target deletions are not repeated. A lost flag causes a re-check, not a second deletion, because each step re-reads the platform before acting. |
| A trigger was abandoned with no pair found | The Garmin pair never appeared within the retry window, or one half of it failed its metadata requirements. | Confirm both activities exist on Garmin with the required manufacturer and type, then reset the trigger to pending. |

## What is never removed automatically

Local caches of the downloaded source files and the merged output are the rollback evidence
for everything above. Nothing deletes them, and successful downstream cleanup is not a reason
to. Keep them at least until the merged activity has survived a full sync cycle on every
platform you care about.
