# Updating Section 11

An update installs the latest official Section 11 release. You can skip releases you missed. Automatic installation is off by default; refreshing your training data does not turn it on.

## Before you update

Your training data, settings, dossier and files in `custom/` are kept. Everything inside `section11/` is replaced, including your edits and extra files: move anything you want to keep to `custom/` first. Unprotected same-name files elsewhere in the data folder can also be removed; read the [removal rules](#local-updates-and-automatic-toggle).

## Update on your computer

Open a terminal in your existing data folder (Terminal on Mac, PowerShell on Windows), using the Python environment that normally runs sync. Run `python3 section11/examples/sync.py --update`, read the listed changes and timer information, then accept if you agree. On Windows, use `py -3` instead of `python3`. If the script is missing or your setup is old, use the [local installation steps](../json-local-sync/SETUP.md#initial-setup).

An AI with command access to that computer can help. Copy this prompt:

> Help me update Section 11. Before acting, read the full guide at https://github.com/CrankAddict/section-11/blob/main/examples/maintenance/UPDATING.md. If you can access my installed section11/ folder, read the same file there at section11/examples/maintenance/UPDATING.md. Confirm my data folder and your command access. Explain the changes and ask before accepting. Keep my existing sync and update preferences.

## Update on GitHub

In your data repository, open **Actions > Auto-Sync Intervals.icu Data > Run workflow**. Keep the default branch, choose **Operation: Update**, then click **Run workflow**. **That click is your yes**, with no later approval. Choose **Status** first if you want to see the plan. A chat AI can guide you; you do the clicks unless it has permission and tools to act. If the Operation menu is missing, follow [workflow installation](#github-update-review).

## Automatic updates and undo

Automatic checks happen at most once a day and need a sync run. To allow installation without asking each time, follow [local automatic updates](#local-updates-and-automatic-toggle) or [GitHub automatic updates](#automatic-github-updates). The same replacement rules apply.

Undo goes back one installation, not any version you choose. Locally, run `python3 section11/examples/sync.py --rollback`; on GitHub, choose **Operation: Rollback**. It needs a usable previous installation and can refuse after later code edits: see [local recovery](#rollback-and-interruption-recovery) or [GitHub recovery](#utc-timing-rejection-and-rollback).

After an update or rollback, check any files you keep in `custom/` and replace uploaded Section 11 files or pasted project instructions separately.

[Full technical guide on GitHub](#technical-guide)

# Technical guide

Updates install the latest official date release (`YYYY.MM.DD`) directly,
without downloading missed releases. They verify its pinned commit, manifest and
managed file hashes, and refuse moved tags and known downgrades. An unknown local
identity can be repaired by an explicitly accepted installation.
If no published date release exists yet, nothing is installed; wait for the first
official release.

Keep managed files unchanged in `section11/`, your own files in `custom/` or outside the data folder, and
data, config and your dossier at the data root. Updates preserve those personal
files. Review custom code compatibility and refresh uploaded protocol files or
pasted project instructions separately after an update or rollback.

Request accounting and cached Intervals.icu responses stay in `<data folder>/state/`,
beside the live JSON, separate from `section11/`, `custom/` and the updater's
`.section11-state/`. Release checks contact GitHub only and do not use the
Intervals.icu allowance or ledger. Updates and rollback preserve private sync
state; never delete it to force another request.

## Local updates and automatic toggle

Run from your data directory with your normal Python environment:

```sh
python3 section11/examples/sync.py --status
python3 section11/examples/sync.py --update
```

`--status` verifies the target and reports installed identity, possibly unknown,
without installation or policy writes. `--init` and `--update` use the same
installer for every local starting point. A damaged manifest with a readable
release receipt remains an ordinary repair and keeps the installation's layout. Obtain the release bootstrap from the
[local guide](../json-local-sync/SETUP.md#initial-setup) if the managed entry is missing.

First adoption asks once, after this exact warning, without a file list:

> Anything you added or changed inside section11/ will be deleted. Move what you want to keep to custom/ first.

It also lists every removal outside `section11/`, ordinary clone metadata loss,
the one rollback ZIP and any timer changes. Declining writes nothing. Later
updates list changed/removed paths and ask once. Both replace all
of `section11/`, including ordinary extras. Missing custom guidance is created,
while existing `custom/` files, data, settings, private state and the dossier remain.

Every install/update removes any ordinary file outside `section11/`, in any
folder, named exactly like a file in the release being installed or a historical
Section 11 file, except the keep list below. Spelling is case-sensitive:
`notes/README.md` and `backup/sync.py` are removed; `readme.md` and `License` stay.
The rule includes unrelated files with those names, not just edited or older copies.
Historical names include `INSTRUCTIONS.md`, `gitignore.txt`,
`PRE_WORKOUT_TEMPLATE.md` and `POST_WORKOUT_TEMPLATE.md`.
Files in root `section11-legacy-github*` / `section11-legacy-dev*` directories
remain in scope, subject to the same protections. There is no content matching.
The plan lists every removed name before acceptance, and full mode logs them.
No additional removal question is asked.

Local and Manual also remove root `README.md` and retain it in the rollback ZIP;
`--rollback` restores it. The generated `state/README.md` is unaffected. Hosted
repositories keep a root README, with the installation behavior described below.

Fixed exceptions always win at any depth and in any spelling: `custom/`, `DOSSIER.md`,
`latest.json`, `history.json`, `intervals.json`, `routes.json`, `saved_workouts.json`,
`ftp_history.json`, `route_eta_history.json`, `maps/`, `archive/`, `state/`,
`.section11-state/`, `.sync_config.json`, `sync.log`, dot-files and dot-folders
(including `.git/`, `.github/`, `.gitignore`, `.secrets` and `.venv`), credentials,
Python environments at any depth and the active interpreter. These protected names
also remain inside old copied folders. A legacy directory containing a detected Python
environment is retained in full. Root `latest.json` stays even when the release
contains a same-named example. Only unprotected parent directories made empty by
removals are pruned; unrelated files and empty folders remain.
`Custom/`, `Archive/` and `dossier.md` are protected on every platform.
The search skips protected folders and never follows symlinks or Windows
junctions or enters hosted submodules. Unrelated links and submodules stay
untouched; one whose own name matches a Section 11 filename stops the update
before deletion. Cloud placeholders are ordinary files and folders for this
scan. An unreadable folder, incomplete discovery or selected non-regular entry
also stops the update before deletion.

Both init and update install or refresh the standard Section 11 timer at
`check_interval_minutes`. If you set up your own timer before, remove it.
Other timers are never inspected or changed. Cron reads its table only to preserve
unrelated lines while managing the exact standard marker. `--no-timer` removes
only the standard timer and persists `"auto_sync": false`; `--timer` re-enables it.
See the [timer details](../json-local-sync/SETUP.md#automate-the-refresh).

Automatic release installation is **off by default** (half mode), independently
of auto sync. Half mode gives a fixed `update_notice` on the next export while a verified update
or repair plan remains outstanding, including a same-date repair. It clears when
resolved, suppressed or no longer matched to the installation. A failed re-check
retains a previously verified reminder while its installation preimage still matches.
A timer-only reminder clears as soon as the timer is resolved or no longer needed,
without another release lookup.
Set `"auto_update": true`
or pass `--auto-update` for full mode. The name rule above applies without a prompt,
including for existing full-mode users: keep your own files in `custom/` or outside
the data folder. `--no-auto-update` suppresses all automatic
maintenance for that invocation. There is no historical recognition or metadata
enrollment. Unadopted new code exports with its fixed short notice until accepted.
The advisory uses official releases, never unpublished main content.

Both modes check once per UTC day on the first run starting at or after **04:00 UTC**,
after its data work even if sync failed or was deferred, including missing credentials.
Local uses the invocation's UTC start; GitHub uses original run creation. Crossing
04:00 or midnight during data work does not change that eligibility time.
Unknown data publication holds maintenance for reconciliation and is never retried.
The day is claimed before release discovery or missing-guidance repair. Recreated
guidance uses verified release bytes, never an editable installed copy; existing
personal guidance stays unchanged. A rerun may claim an
unclaimed day. A failed or unknown maintenance attempt consumes the day and is
never replayed automatically. Standalone history runs do not trigger maintenance. Full mode logs
replacements/removals and replaces the entire verified tree without prompting.
Known downgrades and moved tags stop. Higher installed version labels hold full
mode and are disclosed for explicit review. Unknown provenance stays unknown.

Checks share a 40-request allowance, a 60-second admission deadline and at most
ten seconds per request. Counted redirects have a fixed allowlist; there is no
automatic retry or historical ZIP search. In-flight requests may outlast the
admission deadline. A maintenance failure does not change an already successful export.

The old 3.165 updater can clear history/interval/route caches during its raw-main
first hop. That result has no receipt and is not silently adopted on the next
timer invocation. One later accepted installer gets the latest verified release,
even after many intervening releases.

### Rollback and interruption recovery

One verified ZIP retains the complete previous installation in `.section11-state/`,
including edited/unknown files, empty directories, modes, nested ordinary `.git`,
root tools, every file removed by the name rule, and standard timer recovery data.
No readable old source files remain after success. The ZIP is verified against
the preimages before any loose source is removed. The next installation
that changes files, metadata or timer policy replaces it; an identical reinstall
or a custom-guidance-only repair preserves the existing rollback slot.
This ZIP is short-term recovery until the next changing install, not a backup.
Restore without network:

```sh
python3 section11/examples/sync.py --rollback
```

The existing old-tree limit remains 256 MiB and 10,000 entries. Removed outside
copies have a separate 256 MiB and 10,000-entry limit; the combined archive also
allows timer recovery data. An oversized or non-ordinary preimage stops before
activation and requires owner resolution.

Rollback checks archive integrity independently of the old manifest, extracts
into journalled staging on the installation's filesystem, verifies bytes and
modes, then activates the restored files. It needs no release download. It preserves
later data/dossier/custom and unrelated settings, restores the prior timer policy,
and refuses later changes to managed code, root entries or standard timer definition.
Root-only adoption can restore its original root tools. Fresh installation has no
previous usable producer. The restored release skips the rejected date in automatic
mode; explicit `--update` installs it and clears that skip.

The journal is written before any staging. The next run removes staging from an
interrupted pre-activation run and finishes journalled cleanup after a completed
installation. It never replays an uncertain timer operation. Handled failures
before timer activation restore the old tree. A killed process during activation,
power loss, scheduler refusal or uncertain write can leave `transaction.json`.
Stop the timer and preserve `section11/` and `.section11-state/`; the journal
blocks another install or sync until owner reconciliation. Do not delete it to
unblock execution. A pending transaction can retain its staging and verified
recovery ZIP; the completed slot is named by `previous.json`. The journal records
the prior `auto_sync` setting without copying your credentials.
Verify the recorded digests and actual scheduler state before restoring or
completing activation.
Cron recovery stores table digests and removed sync lines; it reconstructs the
previous table only from a matching current table, without saving unrelated jobs.
Restore only the installation and timer, never replace newer data with an old backup.
An uncertain scheduler write is not retried automatically.

## GitHub installation and updates

### GitHub update review

Use **Auto-Sync Intervals.icu Data** on the default branch. Its **Operation**
defaults to **Sync**, so existing Sync Now links still work. **Update** accepts
the latest verified replacement, **Status** shows the plan without installing,
and **Rollback** restores a compatible previous managed installation.

The owner installs the published sync workflow through GitHub's editor, keeping
every existing literal cron, optional setting and secret name. Hosted push
users replace `auto-sync.yml` and `push-workout.yml` with their published stubs
in the **same owner commit, before the first Sync**. Push dispatch inputs and the
preview/confirm contract stay the same. No release ZIP upload, PR
approval setting, validator workflow or new privileged secret is required.
The [scheduled](../json-auto-sync/SETUP.md) and [On-demand](../json-on-demand/SETUP.md)
guides supply the appropriate template. On-demand has no schedule.

Immediately before committing the workflow replacement, read:

> Anything you added or changed inside section11/ will be deleted. Move what you want to keep to custom/ first.

That owner action accepts first installation. The first Sync run verifies the
latest official release, commits its complete `section11/` tree and receipt,
creates missing `custom/README.md`, and removes the same exact-name Section 11
copies listed above in that installation commit. Git history retains their
preimages. It reads back that commit before running the producer. Unknown,
edited or receiptless old copies need no historical-content recognition or PR
history. Existing data, settings, secrets, dossier and custom files stay intact.

Every hosted install, update and rollback refreshes root `README.md` from the
template in the release being installed or restored, with repository values and
Sync Now. It carries over the current successful-sync timestamp; without one,
the placeholder remains until a successful Sync. Plans list the replacement;
old text stays in Git history, and personal notes belong in `custom/`. If that
release has no README template, the current README is kept and this is reported.
Syncs between these events change only the "Last successful sync" line.

Effective `contents: write` and read access to the run's Actions metadata are
required. A protected branch may prohibit direct writes. A denial stops with no
retry or alternate credential; the owner must provide a policy-compatible route.
The workflow never changes active workflows or bypasses repository policy.
The log names retained Section 11 workflows under `.github/workflows/`, including
`auto-sync.yml`, `push-workout.yml` and `section11-*` workflows, and tells the owner
to keep compatible stubs, replace old stubs or remove obsolete Section 11 workflows
in GitHub. The Actions
token cannot perform that workflow cleanup.

### Workflow compatibility

The stable workflow passes wrapper API 2 to verified managed logic. A mismatch
stops with an owner-workflow message. The published workflow pins a reviewed
bootstrap commit and digest; the bootstrap separately pins its trusted verifier.
An unsealed pin stops before installation or commits, with no raw-main fallback.
Only use the published, sealed template after its compatible release is available.

The `--wrapper-api` value on its `run:` line is checked against the managed
entrypoint. [`examples/maintenance/wrapper-api.json`](wrapper-api.json) records
`auto-sync.yml` 2 and `push-workout.yml` 1. A mismatch stops the updater with
`owner wrapper update required`.

Controller code is authenticated from the official installed release before it
runs with publication authority. Each invocation makes two authenticated,
blob-pinned source reads through GitHub's official Git blobs API using the job
token, with no redirects or retries, Git blob identity and SHA256 verification
before execution. The SHA256 check independently authenticates bytes even though
the Git object address uses SHA1. Pins can be computed before a commit; maintainers
verify their availability and exact bytes after publishing the source.
Each allows ten seconds and at most 1 MiB for the bootstrap or 8 MiB for the verifier.
The token is removed before importing the verifier. Release authentication then
uses the ordinary token-free bounded release transport. These trust reads are
separate from the daily latest-release check; they never select a newer installed
controller merely because it is newer. First accepted installation is the exception
that needs a compatible latest release.
Producer execution receives no GitHub publication token, and checkout credentials
are not persisted. Later releases update managed logic without editing the stub;
future incompatible action/runtime changes still require owner workflow recovery.

### Automatic GitHub updates

Half mode is the default: Actions reports an available official release, and the
next data export carries a fixed privacy-safe `update_notice` while a verified
update or repair plan remains outstanding, including a same-date repair. The
reminder clears when resolved, suppressed or no longer matched to the installation.
Both half and full mode save the verified plan before installation; failed
discovery or installation retains a matching plan and never repeats an uncertain write. Choose
**Update** once to install it. Status is optional. Normal updates list changed and
removed paths, including unknown managed files. Direct updates have no human
pre-merge diff checkpoint; the Update dispatch accepts the verified replacement.

Set repository variable `SECTION11_AUTO_UPDATE=true` for full mode, under
**Settings > Secrets and variables > Actions > Variables**. Full mode replaces the
complete managed tree and removes unprotected exact-name copies in any folder,
including unrelated same-name files, without another approval. An absent or
false value retains half mode. A malformed value stops automatic maintenance after
the daily claim; explicit Update and first acceptance do not depend on that preference. Its failed or
unknown outcome is reported separately; an already successful data export remains
successful. Set false to stop future automatic
installations; cancel an in-flight run separately and inspect its commit readback.
Full mode never grants workout-write authority.

Each installation is one child commit of the observed default tip, with an exact
validated tree and no force. Data publication is a separate validated commit.
Any competing default-branch commit causes a stop, including human data, custom
or workflow edits. The controller does not retry or rebase. It verifies the
remote tree after success or failure. A lost response can be confirmed from
history; an unknown result is not a failed write and must be reconciled before
another run. If later commits already followed a confirmed installation, inspect
both the confirmed commit and current state.

### UTC timing, rejection and rollback

Automatic maintenance follows the first run **created at or after 04:00 UTC**,
after its data work even if sync failed, with no closing hour. Unknown data
publication holds maintenance for reconciliation. The daily claim precedes
missing-guidance repair and target discovery. Creation time controls eligibility
even when the runner starts later. The literal crons are preserved.
On-demand runs only when requested, checks only on those runs at or after
04:00 UTC, and has no unattended maintenance.

A guarded control commit claims the UTC day before latest-target discovery.
Failed or unknown maintenance attempts consume that day; reruns do not repeat
them. A rerun may claim the day if no earlier attempt claimed it. This costs a small
control commit even on a no-update day. Explicit Update, Status and Rollback work
at any time. `.section11-update.json` contains only strict date/policy bookkeeping,
plus a digest of the installation for an outstanding verified plan, not private
data, credentials, PR history or a release-fingerprint catalogue. It stays outside
the training-data artifact.
The separate upstream trust reads and data/control requests are counted apart
from the daily target check and Intervals.icu accounting.

The daily allowance limits automatic discovery and installation of updates,
including a failed attempt. It does not limit authentication of code about to run.
Claiming the day with unverified checkout code would give that code publication
authority before verification. Therefore an already-claimed day can still read
and authenticate the installed release, but cannot make another automatic latest
check. A trust failure stops the invocation before any claim, export or commit;
there is no automatic retry. Manual Status/Update and first accepted adoption
remain explicit operations. This distinction is a request-cost limitation, not
a claim that all GitHub reads occur once a day.

Choose **Rollback** to restore the previous compatible managed tree in one new
commit and suppress the rejected date. It checks the recorded installation's
scope and current preimages, refuses later code edits, and preserves newer data,
custom files and settings. Local and hosted keep only the current rejected release,
replaced by the next rollback, with no accumulated rejection history. Automatic
checks skip that date; an explicit
**Update** installs the selected date and clears its skip, without editing control
files or variables.

Rollback locates the last installation through path-filtered history queries,
independent of the number of later data/control commits. It restores the exact
previous ordinary tree, including edited and extra files, while checking the
recorded commit scope and the current installation preimage. A missing prior
release identity or incompatible history still requires owner recovery.
When an installation only removes outside copies, the private control record
retains one changed path (the legacy directory for legacy copies) for one
additional bounded history query, so that
cleanup-only installation also has an exact rollback target.

A return to a pre-adoption root-only setup requires owner workflow recovery.
Rollback stops before publishing an unusable tree: restore the earlier
`auto-sync.yml` and, if used, `push-workout.yml` from repository history together
with their matching managed tree and root tools. Restore only those installation
paths, preserving newer data, custom files, settings and dossier. The Actions
token cannot restore workflows. Do not revert the whole data repository.
