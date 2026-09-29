# Architecture

How a multi-source activity is discovered, merged, uploaded and verified. Everything here
describes behaviour established by the working implementation. The cleanup behaviour
summarised in the README's [cleanup reliability](README.md#cleanup-reliability) section has
offline regression coverage and a bounded live observation. Cases that are not
established are named as such in [Untested and unsupported](#untested-and-unsupported).

## Components

The pipeline is four cooperating roles rather than one program.

| Role | Responsibility |
|------|----------------|
| Runner | A scheduled shell entry point. Holds a single-instance lock, discovers sources, sequences merge, upload and cleanup, and enforces the wait windows. |
| Merger | Finds the donor, downloads it, performs the merge and the identity rewrite, self-validates the output and uploads it. |
| Cleanup | Checks the uploaded result on Garmin, then removes source duplicates per platform. Gates and post-delete confirmation differ per platform and have documented gaps; see [CLEANUP_POLICY.md](CLEANUP_POLICY.md). |
| Support helpers | FIT fingerprinting for duplicate detection, a legacy CSV-based DFA injector used only when no donor is found, and an attachment collector for that CSV path. |

The merger and cleanup roles both depend on the vendored `fit_tool` library that ships
inside the upstream FIT File Faker package, and on that package's profile configuration for
Garmin credentials.

## Source discovery

Two independent entry paths exist. Both end at the same merge.

### File-first path

The virtual platform writes a FIT file into a cloud-synced folder. The runner:

1. Refreshes the cloud provider's directory listing, because a stale listing is common on
   file-provider mounts and an empty scan is not evidence that nothing arrived.
2. Enumerates candidates through three independent providers (a direct directory scan, a
   metadata index query, and a combined scan) and takes the union. Each provider runs under
   an external timeout that kills the whole process group, because a hung provider must not
   stall the run.
3. Skips any candidate whose FIT fingerprint matches an already-uploaded activity, or an
   already-staged local file for the same activity. Fingerprints are derived from record
   timestamps, record count and final distance, so a renamed copy is still recognised.
4. Copies the file locally before anything reads it, retrying while the cloud placeholder
   hydrates, and verifies the FIT magic bytes on both source and copy. Zero-byte, temporary
   and hidden FIT files are quarantined rather than uploaded.

If the cloud folder cannot be listed within a few seconds the whole file-first path is
skipped for that run. The other path and cleanup still proceed.

### Trigger-first path

The native Zwift activity is not a local file, so discovery starts from the local mirror of
the athlete's Intervals.icu activity list. An entry becomes a trigger only when all of these
hold:

- it carries a DFA stream,
- its name matches the head unit's indoor-cycling label exactly,
- its type is a virtual ride,
- no existing cleanup item from the file-first path already claims a start time within the
  pairing tolerance.

A trigger is only a wake signal. It authorises one Garmin lookup; it never authorises a
merge. The lookup requires both halves of the pair to be present in Garmin metadata:

| Role | Required Garmin attributes |
|------|----------------------------|
| Base | manufacturer ZWIFT, activity type `virtual_ride`, has a polyline |
| Donor | manufacturer GARMIN, activity type `indoor_cycling` |

Both must start within the pairing tolerance of the trigger and of each other. Where several
combinations qualify, the pair with the smallest combined start deviation wins.

If no pair is found, the trigger is retried on a bounded backoff and then abandoned with an
explicit status rather than merged against a partial match. Idle scans and scans inside a
backoff window perform no Garmin login at all; this is asserted by regression tests, because
an unnecessary login on every scheduler tick is both a rate-limit risk and an availability
risk.

## Identity and rewrite layer

Garmin treats an activity differently depending on the device identity recorded in it.
Training effect, training load, device-linked challenges and badges depend on the platform
recognising the recording device. A file uploaded with an unrecognised or generic identity is
still stored, but is not presented or credited the same way.

The merged output is therefore rewritten to a fixed trainer identity before upload:

| Message | Action |
|---------|--------|
| `file_id` | Replaced. Manufacturer becomes Tacx, product and Garmin product become the Tacx App product id, product name becomes the Tacx App name. Creation time and file type are carried over from the base. |
| `sport` | Base sport messages are dropped. One synthetic message is emitted with sport cycling and sub-sport virtual activity. |
| `device_info` | Base device messages are dropped. A synthetic set is emitted at both the first and last record timestamp: the trainer app at device index 0, the smart-trainer hardware at index 1, and the heart-rate strap at index 2. |
| `session`, `lap` | Sport and sub-sport are forced to cycling and virtual activity. All other summary values stay as the base recorded them. |

The donor's own `device_info` messages are also carried into the output, with their device
indexes shifted past the synthetic block so the two sets cannot collide. This preserves the
donor's sensor provenance without displacing the primary identity. The copy is unfiltered:
every donor device record is carried, including any that fall outside the base timeline.

### When the upstream rewrite applies, and when it does not

The upstream FIT File Faker rewrite is used for files this pipeline did not handle itself. It
is the fallback for anything left in the local inbox after the merge and upload loop, and it
is the tool of choice for a plain third-party FIT that needs an identity but no merge.

It is deliberately not applied to merged output. Merged files are uploaded raw, directly to
Garmin, precisely so the Tacx-primary identity written during the merge survives intact. A
second rewrite pass over an already-correct file is an opportunity to lose it.

## Fusion layer

The base supplies the timeline and the structural virtual-ride data. The merge walks the
base file record by record and copies it through, and the donor contributes an explicit,
named set of fields under the precedence below. Those donor fields are not limited to gaps:
left/right power balance replaces an existing base value on every matched record where the
donor has one.

What the ordering does guarantee is narrower and still the important part: the route, the
virtual distance, the speed, the altitude and the workout structure are never displaced,
because no donor field in the precedence table touches them.

### Field precedence

| Data | Source | Condition |
|------|--------|-----------|
| Route, GPS, distance, speed, altitude | Base | Always. |
| Power, heart rate, cadence | Base | Always. |
| Laps, events, session summary | Base | Always, except the sport fields and the two fields below. |
| Base developer fields | Base | Preserved. Regression tests assert the base field set is a subset of the merged field set. |
| `Alpha1`, `Artifacts`, `RespirationRate`, `RRa1_ratio` | Donor | Appended to each base record that pairs with a donor record and has a non-empty encoded value. Non-empty is the only test: these are not checked against the FIT invalid sentinel. |
| Temperature | Donor | Only where the base record already carries a temperature field container. Where it does not, no temperature is added. |
| Left/right power balance | Donor | The donor value replaces the base value on every matched record where the donor has one, and the field is added where the base lacks it. This is a replacement, not a gap fill. Base values survive only on records the donor does not cover. |
| Enhanced respiration rate | Donor | Where the donor has a value for that timestamp. Where it does not and the base does, the base value is re-encoded rather than dropped. |
| Workout feel, workout RPE | Donor | Read raw from the donor session and written onto the base session when present. |
| Donor developer-field metadata | Donor | Copied with developer data indexes remapped to avoid collision with base indexes. |
| Donor `device_info` | Donor | Copied wholesale with shifted device indexes. No timeline or validity filtering is applied, so donor device records from outside the base window are carried into the output. Current behaviour, and a limitation. |

Enhanced respiration and the two session summary fields are read directly from the donor's
raw bytes rather than through the profile decoder, because the vendored FIT profile can be
older than the fields a current head unit writes. Reading raw and writing raw avoids a
silent decode failure turning into a missing field.

### Exclusions and why

| Excluded | Reason |
|----------|--------|
| Raw RR intervals | Deliberate. A locally derived alpha1 produced non-equivalent values and false threshold crossings, so only the donor's own computed fields are carried. |
| Donor samples outside the base timeline | Read and indexed, but not copied, because there is no base record to attach them to. Iteration is driven by the base, so a donor that started earlier or stopped later contributes nothing beyond the base window. Donor `device_info` messages are the exception noted above. |
| Any donor standard field other than those listed above | Not copied. The donor's own speed, distance and altitude describe a different measurement of the ride and would corrupt the base. |
| Donor session fields other than workout feel and RPE | Not copied. Donor summaries are computed over the donor's timeline, not the merged one. |
| A standard field whose values are all absent or all the FIT invalid sentinel | Skipped. The test is over the whole field: a field with any valid value is copied intact, and this filter does not apply to developer fields at all. |
| Base `device_info` and `sport` messages | Dropped by design and replaced, as described above. |

Nothing outside this list is copied from the donor. Unknown or unclassified donor messages
are not carried into the output.

## Timeline handling and match gates

Records are paired on exact timestamp, falling back to the nearest donor record within one
second. The two source modes gate differently, because the trigger-first path has already
confirmed both identities through Garmin metadata while the file-first path has not.

| Gate | File-first mode | Trigger-first mode |
|------|-----------------|--------------------|
| Base manufacturer | Not checked | Must be ZWIFT |
| Donor manufacturer | Must be GARMIN | Must be GARMIN |
| Start difference | 120 s | 300 s |
| Duration difference | 180 s | Not gated |
| Matched record count | Not gated | At least 300 |
| Base overlap ratio | Not gated | At least 0.80 |

The trigger-first mode does not gate on duration because a donor recording legitimately runs
longer than the virtual ride; the overlap ratio is the meaningful test there. The file-first
mode has no overlap gate. A donor that satisfies the start and duration windows is accepted
on those alone, so a donor covering only part of the ride passes and produces a merged file
whose donor-derived fields are populated on some records and absent on others. Nothing
downstream rejects that result: the exact-count validation described below confirms the
merge wrote what it intended to write, not that the donor covered the ride. Check the
reported matched-record count against the base record count when a recording was
interrupted.

Two further preconditions apply in both modes: the donor must carry an `Alpha1` field unless
that requirement is explicitly waived, and the base must not already carry one unless the
merge is forced. If no `Alpha1` record ends up injected, the merge fails rather than emitting
a file that looks merged but is not.

### Donor selection in the file-first mode

Garmin is searched across a three-day window around the base start. Candidates are scored on
start and duration deviation, plus penalties designed to stop the pipeline merging against
its own earlier output: a non-Garmin manufacturer is penalised, a name suggesting a merged or
virtual-platform upload is penalised, and a candidate whose distance is close to the base
distance is penalised heavily, because the donor's trainer-derived distance normally differs
while a previous merged upload's does not.

## Upload

Merged output is uploaded raw to Garmin. A duplicate rejection from Garmin is reported as a
conflict rather than an error, so a retry after a partially completed run does not look like
a failure.

Upload success is recorded, but it is not evidence of anything beyond transmission. The
activity is not considered correct until the verification step below has run against the
copy Garmin actually stored.

## Verification

The merge self-validates before the file leaves the machine, and cleanup re-validates after
Garmin has stored it.

**At merge time.** The output is written, then re-parsed from disk. Two exact-map assertions
run over the re-parsed file: left/right balance and enhanced respiration must match, per
timestamp and per value, the union of the base's own values and every donor value the merge
intended to write. A missing timestamp, an extra timestamp or a changed value all fail the
merge. This catches definition and header mismatches that a record count alone would miss.
The merge reports both the intended counts and the counts validated from the written file.

**At cleanup time.** The uploaded activity is located on Garmin by start time, duration and
distance tolerances, excluding the known source activity ids. Where several activities fall
inside those windows, the lowest-scored candidate is taken; multiple qualifying candidates
are not reported as ambiguous. That candidate is downloaded in its original format and
checked as follows:

| Check | Strength |
|-------|----------|
| AlphaHRV records present | Presence only. One record satisfies it. |
| Temperature records present | Presence only. One record satisfies it. |
| Left/right balance record count | Exact equality against the count recorded at merge time, but only when that recorded count is greater than zero. A recorded count of zero disables the check. |
| Enhanced respiration record count | Same rule. |
| Device identity | **Not checked.** Nothing confirms the stored copy still presents the intended trainer identity. |
| Timeline and per-sample values | **Not checked.** Only the counts above are compared. |

Only when those checks pass is the merged activity id recorded as verified. This is a
meaningful gate against a lost or truncated field set, and it is not a full verification of
the uploaded result. See [CLEANUP_POLICY.md](CLEANUP_POLICY.md).

## State flow

Two state records drive the pipeline. Neither is a log; both are the resume point after an
interrupted run.

**Trigger state** tracks each discovered trigger through `pending`, then `ready` once a merge
has produced a file, then `uploaded`. A trigger that cannot be paired records its attempt
count and next attempt time, and finally becomes `ignored_no_native_zwift_pair`. A duplicate
trigger at an already-known start time is not re-queued, so a re-synced activity list cannot
cause a second merge of the same ride.

**Cleanup state** is created from the merge result at upload time. It carries the source
activity ids, the merged activity name, the start time, duration and distance used for
matching, and the field counts the verification step must reproduce.

Cleanup checkpoints verification, rename, per-platform completion, individual Garmin target
outcomes and, for trigger-first items, individual Strava target outcomes. A failed checkpoint
stops all further remote work. Each item has independent step records; a platform failure
does not abort later safe stages or later items. Verification or Garmin rename failure still
stops that item's downstream work.

The JSON state keeps its original version and adds records rather than replacing them: each
item's required-platform policy and the origin of that policy, per-step outcomes with retry
deadlines, an optional item-level block, per-target upload-target delete outcomes, an
outstanding analysis-platform delete request, and a shared per-service backoff. Invalid JSON
or an invalid top-level shape fails visibly rather than becoming an empty queue.

The runner explicitly supplies the completion policy from its switches. Without an explicit
required-platform policy, a manual command uses the saved policy, or Garmin, Intervals and
Strava for an unfinished legacy item. Enabled deletion flags add obligations; omitting flags
does not remove saved obligations. Completed legacy records without a saved policy are
grandfathered to the destinations already recorded complete. A persisted grandfathered policy
origin prevents later runner flags from reopening them; a reviewed migration must replace the
policy and clear that origin. Companion applies only to trigger-first
items. An explicit policy can exclude a disabled platform without marking it deleted. Both
source modes reopen when an existing explicit policy requires unfinished work. With every
deletion flag off, no work runs.

Expected propagation waits use a five-minute minimum and exit healthy. Transport or adapter
failures, including Garmin and Intervals HTTP 429, exit unhealthy while backed off, starting
at 30 minutes and doubling to a six-hour cap. Longer existing Strava/Companion deadlines and
exposed Retry-After values are retained. Garmin and Intervals HTTP 401/403 blocks and 429
deadlines are shared across items; deterministic failures are blocked until reviewed. Strava
keeps a global rate limit, which is a healthy wait, and a late-duplicate watch for
trigger-first items; both are described in [CLEANUP_POLICY.md](CLEANUP_POLICY.md).

Garmin source-delete 404 handling is confined to the exact deletion call. Structured status
is preferred; contradictory status or endpoint metadata is rejected. A narrowly matched
Garmin wrapper message is supported when metadata is absent. This is client evidence of
absence, not independent proof that a service routed the request correctly. Non-delete 404s
do not complete a deletion. Intervals 202 records a pending request and waits for listing
absence without resubmitting that deletion.

## Untested and unsupported

- **Sports other than cycling.** The output sport, the platform queries and every fixture are
  cycling. Nothing else has been exercised.
- **Split or multi-part base recordings.** The merge takes exactly one base and one donor,
  and pair selection returns exactly one pair. Multi-part bases are not concatenated. A split
  ride must be resolved before the pipeline runs.
- **Multiple donors.** Same limit, same reason.
- **Bases from virtual platforms other than the two in use.** The file-first mode does not
  check the base manufacturer, so another platform's FIT would technically pass through it.
  That path has not been tested and should not be assumed to work.
- **Explicit donor cropping.** There is no cropping step. Every donor record is read and
  indexed; samples with no matching base record are simply never copied. The observable
  result resembles cropping; the mechanism is not.
- **Automatic replacement cleanup.** Cleanup state records the original source recordings
  only. Nothing identifies or removes an obsolete earlier merged activity, and an obsolete
  merged copy left on Garmin is itself a candidate during merged-activity selection, because
  only the recorded source ids are excluded.
- **Post-upload identity verification.** Nothing re-reads the stored activity's device
  identity. A rewrite or normalisation applied by the platform after upload would not be
  detected.

## Adaptation points

The sections above describe one deployment. This section names the contracts an implementer
would have to redefine to point the same design at different sources or destinations.

**These are architectural seams, not an adapter SDK.** The scripts expose no plugin
interfaces, no registry and no configuration surface for any of this. The seams are visible
in the structure of the implementation, and working at them means editing source.

| Contract | What it decides |
|----------|-----------------|
| Base selection and authority | Which recording owns the timeline and structure, and what is never allowed to displace it. |
| Donor discovery and identity | How a candidate donor is found, and what proves it is the same effort rather than a near neighbour. |
| Clock alignment, overlap and ambiguity | Pairing tolerance, minimum overlap, and what happens when more than one candidate qualifies. |
| Field allowlist, precedence and invalid values | Which fields cross, which direction wins per field, and how absent or sentinel values are treated. |
| Sport, sub-sport and device identity | Whether identity is normalised or preserved, and to what. |
| Pre-upload validation | What the merge must prove about its own output before the file leaves the machine. |
| Post-upload verification | What is re-read from the destination, and whether identity, timeline, field set and values are all in scope or only some. |
| Destination and downstream adapters | Upload target, analysis service and any social or companion platform, each with its own client, auth and rate behaviour. |
| Duplicate classification and protected provenance | How each platform's copies are told apart, which one is protected there, and whether a delete is confirmed afterwards. |
| Durable state, idempotency, completion and approval | What is persisted and when, what makes an item complete, what can reopen, and whether a human approves each deletion. |

### Current implementation against a possible adaptation

| Contract | Current implementation | Possible adaptation | Required validation |
|----------|------------------------|---------------------|---------------------|
| Base selection | Two fixed modes: a file arriving in a cloud folder, or a native activity discovered through a local mirror | Any FIT-producing source whose timeline is authoritative for the effort | Field inspection against real files, timing characterisation, fixtures |
| Donor identity | Donor must be a Garmin FIT; the trigger-first base must be a Zwift FIT | Any characterised source in either role | Identity checks per source, plus a negative case proving a wrong source is rejected |
| Alignment gates | 120 s start and 180 s duration in one mode; 300 s start with 300 matched records and 0.80 overlap in the other | Tolerances derived from the new sources' clock behaviour | Regression tests at and just past each boundary |
| Field allowlist | Four named developer fields, temperature, left/right balance, enhanced respiration, two session summary fields | Whatever the new donor uniquely carries | Per-field precedence decision, then an exact-map assertion per field |
| Identity policy | Fixed trainer manufacturer, product and device set, with cycling and virtual-activity sport | Whatever the destination needs to present the activity correctly | Round-trip through the destination, then inspection of the stored copy |
| Pre-upload validation | Re-parse from disk, exact-map assertions on two fields | Extend to every field the new allowlist carries | A deliberate corruption must fail the assertion |
| Post-upload verification | Presence checks plus exact counts where a count was recorded; identity, timeline and values not checked | Identity and value verification where the destination allows it | A stored copy that differs must be detected, not merely counted |
| Destinations | One upload target, one analysis service, one social platform, one companion app | Substituted per deployment | Auth expiry, rate limiting and lag behaviour proven per platform |
| Duplicate rules | Device name and external-id classification, with the native activity protected on two platforms | New rules for whichever platform now holds provenance | An ambiguity case must fail closed, and a protected activity must never be a target |
| State and completion | Two state records; checkpointed cleanup progress and explicit completion policy | Redefine required destinations and retry policy deliberately | Interrupted-pass and policy-change tests per platform |

Nothing in this table is a work plan. It is the list of decisions someone would have to make
deliberately, and the evidence they would need before trusting the result.
