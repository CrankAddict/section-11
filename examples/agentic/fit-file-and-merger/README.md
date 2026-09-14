# FIT File & Merger

Rewrite, merge, verify, upload and safely clean up multi-source FIT activities.

An indoor ride is often recorded twice. The virtual platform (Zwift, BikeTerra) owns the
route, the virtual speed and distance, the elevation profile and the workout structure. A
head unit recording the same ride owns the sensor detail: AlphaHRV developer fields,
temperature, left/right power balance and native enhanced respiration. Neither recording is
complete, and uploading both leaves duplicates scattered across Garmin, Intervals.icu,
Strava and Zwift Companion.

FIT File & Merger builds one authoritative activity from those recordings, uploads it under
a consistent trainer identity, verifies the uploaded result by downloading it again, and only
then removes the source duplicates that are safe to remove.

## Layers

| Layer | Responsibility |
|-------|----------------|
| Identity | Rewrite the output to a consistent Tacx-primary virtual-ride identity so Garmin presents it as an indoor trainer ride rather than an unrecognised import. |
| Fusion | Keep the virtual platform as the data base for the timeline and the structural virtual-ride fields, and take an explicit, named set of fields from the donor under a documented precedence. Some of those donor fields replace base values rather than filling gaps. |
| Verification | Re-download the uploaded activity from Garmin and check the donor-derived fields before treating it as usable. Field presence and, where a count was recorded, exact counts. Device identity is not re-checked; see [Current gaps](#current-gaps). |
| Cleanup | Remove source duplicates per platform. The gates differ by platform and are not uniform. On Strava and in Zwift Companion the native activity carrying race provenance is never a deletion target; on Garmin the native virtual-platform source is itself removed once the applicable gates pass, because the merged activity supersedes it there. |

The identity layer builds on [FIT File Faker](https://github.com/jat255/Fit-File-Faker) by
Joshua Taillon. The fusion, verification, upload policy and cleanup layers are separate
extensions and are not affiliated with or endorsed by that project. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Supported scenarios

| Scenario | Behaviour |
|----------|-----------|
| Virtual platform file plus a matching head-unit recording | Merged into one Tacx-primary activity, uploaded raw to Garmin. |
| Native Zwift activity plus a matching head-unit recording | Both downloaded from Garmin, merged, uploaded as a new activity; the native Zwift upload on Strava and Companion is preserved. |
| Virtual platform file with no donor found | After a bounded wait, the file is rewritten to the trainer identity and uploaded without donor fields. |
| Plain third-party FIT | Identity rewrite and upload only, with no merge. |
| Donor that starts or stops outside the base recording | The base timeline is authoritative. Donor samples outside it are read but not copied. In the trigger-first mode an insufficient overlap fails the merge; in the file-first mode there is no overlap gate, so a thin donor can yield partially populated donor fields. |
| Replacement upload | Manual. The pipeline verifies and cleans up original source recordings only; it does not identify or remove an obsolete earlier merged activity. See [RUNBOOK.md](RUNBOOK.md). |

## Not supported

These are stated as limits, not as work in progress.

- **Cycling only.** The output sport is fixed to cycling with the virtual-activity
  sub-sport, platform queries filter on cycling, and every regression fixture is a ride. The
  design may generalise later; nothing else has been tested.
- **One base and one donor per activity.** Split or multi-part base recordings and multiple
  donors are not combined. A split ride has to be resolved before the pipeline runs.
- **Raw RR intervals are excluded.** A locally derived alpha1 stream was removed after it
  produced values that were not equivalent to the donor's own, and the exclusion has not
  been revisited.
- **Automatic replacement cleanup.** Cleanup state tracks the original source recordings.
  There is no mechanism to identify or delete an obsolete earlier merged activity.

## Current gaps

These are things the design calls for that the implementation does not yet do. They are
listed so nobody reads the sections above as stronger guarantees than they are.

| Gap | Consequence |
|-----|-------------|
| The uploaded activity's device identity is not re-checked after upload | Verification confirms donor-derived fields survived, not that the stored copy still presents the intended trainer identity. |
| Merged-activity selection takes the best-scoring candidate | Where several activities fall inside the start, duration and distance windows, the closest wins and no ambiguity is reported. |
| Garmin and Intervals.icu deletions have no post-delete read | Success is recorded from the call, not from a confirming query. Only Strava and Companion re-check. |
| File-first Garmin deletion does not wait for downstream verification | The trigger-first mode waits; the file-first mode does not. |
| Deletion is flag-gated, not approval-gated | Three of the four deletion flags default on in the runner. The dry run is an operator habit, not an enforced per-item gate. |

## Reuse beyond the current deployment

Everything above describes one cycling-tested implementation. The design underneath it is not
specific to the two platforms it currently reads from, and this package is meant to be usable
as a reference for the general problem: two or more recordings of the same effort, each
holding something the other lacks.

The pattern is these eight decisions, in order:

1. Choose one recording as the authoritative base for the timeline and structure.
2. Choose one or more conceptual donor sources for complementary fields.
3. Define precedence field by field, in writing, before any code.
4. Decide the device-identity policy deliberately: normalise it, or preserve it.
5. Validate the produced file before upload, against what the merge intended to write.
6. Inspect the stored result after upload, not the file that was sent.
7. Clean duplicates per platform, according to which activity carries provenance there.
8. Persist state so interrupted work can be reconciled rather than repeated.

**Base and donor are policy choices, not fixed vendor roles.** The source holding the
authoritative timeline or structure should be the base; the other contributes only fields
that were explicitly selected. Which recording plays which role depends on the ride, not on
who made the software.

Any FIT-producing software, service or device can conceptually take either role, once its
timestamps, field semantics and identity have been characterised. That includes virtual
training platforms such as Zwift, BikeTerra, TrainerRoad, TrainerDay, MyWhoosh, ROUVY and
icTrainer, and equally head units, trainers, wearables and standalone sensor loggers. Naming
them describes the shape of the problem. It is not a claim that any of them works today, and
none except the two currently in use has been tested.

### Adaptations, organised by the problem being solved

Each of these is a possible adaptation of the pattern. None is a supported scenario in the
supplied implementation.

| Problem | Shape of the adaptation |
|---------|-------------------------|
| One recording has the route, workout structure, laps or virtual distance; another has better sensor streams | Base on the first, donate the sensor fields from the second. |
| Two recordings each hold complementary trainer, head-unit, wearable or environmental data | Base on whichever owns the timeline, then allowlist the specific fields the other contributes. |
| The primary recording lacks developer fields a secondary device produced | Carry the developer metadata and the named fields across, remapping data indexes. |
| A destination platform mishandles or ignores the file's identity or metadata | Identity rewrite with no fusion at all. The merge step is optional. |
| A native activity must stay intact for provenance while analytics need an enriched copy | Upload the enriched copy to the analysis destination and protect the native one where it lives. |
| The same effort has produced duplicates across connected platforms | Duplicate classification plus per-platform cleanup rules. |
| The destinations differ: another upload target, analysis service or social platform | Substitute the discovery, upload, analysis and cleanup adapters. |
| More than one donor, or sports other than cycling | Requires new precedence, identity and validation rules first. Not a configuration change. |

### What adaptation actually costs

The implementation is modular, and the changes concentrate at documented seams rather than
spreading through the code. That is a real property and it is worth having. It is not the
same as being adaptable by configuration.

The current code fixes the cycling and virtual-ride sport identity, the specific upload,
analysis, social and companion platforms it talks to, the named field allowlist, and a macOS
file-provider discovery path. Any other use means source changes. It also means FIT-field
inspection against real files from the new source, identity characterisation, representative
fixtures, regression tests, and fresh safety validation of the cleanup rules for whatever
platform now holds provenance.

FIT merging is easy to get subtly wrong, and the two places it goes wrong quietly are device
identity and deletion. Treat an adaptation as new work with its own verification, not as a
settings change. The seams to work at are listed in
[ARCHITECTURE.md](ARCHITECTURE.md#adaptation-points).

## Package contents

| Document | Read it for |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Source discovery, identity rewrite, field precedence, exclusions, timeline gates, upload and state flow. |
| [RUNBOOK.md](RUNBOOK.md) | Setup assumptions, the automatic workflow, manual operations, fallbacks and partial-failure recovery. |
| [CLEANUP_POLICY.md](CLEANUP_POLICY.md) | Verification gates, fail-closed conditions, the preview and approval boundary, and per-platform final state. |
| [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) | Pinned upstream version, attribution and both licence texts. |

## Status

This is a documentation package. The working implementation runs on one operator's machine
and is not published here: no scripts, fixtures or executable examples are included in this
phase. The documents describe behaviour observed in that implementation, and mark cases that
are unresolved or untested rather than implying support for them.
