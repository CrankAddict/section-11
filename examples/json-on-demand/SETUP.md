# On-Demand Sync

On-demand sync refreshes your Intervals.icu training files when you ask, from a phone or browser. GitHub does the work. You need Intervals.icu and GitHub accounts, but no Python installation or automatic schedule.

## Get help from your AI

You do the GitHub clicks and enter credentials; your AI explains the steps. Copy this prompt:

```text
Help me set up Section 11 On-demand sync, one step at a time; I do the clicks and enter credentials.
Read this guide first: https://github.com/CrankAddict/section-11/blob/main/examples/json-on-demand/SETUP.md (if you can open my installed section11/ folder, use its copy instead).
Keep my existing data and settings, and ask before changing anything.
```

For full guided setup, including your dossier and AI connection, give your AI this link: <https://github.com/CrankAddict/section-11/blob/main/SETUP_ASSISTANT.md>.

## Set up once

1. In Intervals.icu **Settings**, find your Athlete ID near the bottom and your API key under **Developer Settings**.
2. At [github.com/new](https://github.com/new), create a **Private** repository such as `training-data`, leaving **Add a README file** unchecked. Click **Create repository**.
3. Download `section11-YYYY.MM.DD-on-demand.yml` from the [latest official release](https://github.com/CrankAddict/section-11/releases/latest); a same-day release adds `-N` after the date. Wait if unavailable or `UNSEALED` ([workflow setup](#step-2-set-up-github-repository)).
4. In your repository, click **creating a new file** and name it `.github/workflows/auto-sync.yml`. Paste the downloaded contents and commit.
5. Under **Settings > Secrets and variables > Actions > New repository secret**, add `ATHLETE_ID` and `INTERVALS_KEY` with your values.
6. If required, select **Read and write permissions** under **Settings > Actions > General > Workflow permissions** and save ([permissions](#step-4-enable-workflow-permissions)).
7. Open **Actions > Auto-Sync Intervals.icu Data > Run workflow**, enabling workflows if prompted. Keep the default branch and **Operation: Sync**, leave the checkbox unticked, then run it.
8. When it finishes, check the repository contains the new files, including `latest.json` and `section11/`.

## Refresh and use your data

Need fresh data? Tap **Sync Now** in your repository's README, then **Run workflow**, and then **Run workflow** again.

When it's done, check that your AI can read the new files. Connected to GitHub? Refresh the connection. Uploading instead? On your repository page, press the green **Code** button and choose **Download ZIP**. Upload that ZIP, and replace it each time.

Set up your AI with [Section 11's project instructions](../../README.md#3-configure-your-ai-platform).

## Updates

When a new version is out, your AI mentions it. To install it, tap **Sync Now** in your repository's README, then **Run workflow**, set **Operation** to **Update**, and tap **Run workflow** again.

For automatic updates, open your repository on github.com and go to **Settings > Secrets and variables > Actions > Variables**. Add a variable named `SECTION11_AUTO_UPDATE` with the value `true`.

Already have a repository? See [updating an existing repository](#updating-an-existing-repository).

[Full technical guide on GitHub](#technical-guide)

# Technical guide

Trigger a fresh Intervals.icu sync from your phone or browser, then download the data files. No local Python, no scheduled runs. You sync when you want to.

> **Want automatic sync on a schedule?** See [json-auto-sync](../json-auto-sync/SETUP.md#github-sync-setup-guide) instead.

> **Running an agentic platform locally?** See [json-local-sync](../json-local-sync/SETUP.md#local-sync-setup-guide). No GitHub needed.

> **Already using On-demand sync?** Moving to the [current hosted workflow](../maintenance/UPDATING.md#move-to-the-final-hosted-workflow) is optional and enables same-day releases. Keep your repository, secrets, settings and data. An existing compatible installation stays in place in half mode until you choose Update.

---

## Overview

Date-only/exact-midnight workouts use the labelled 10:00 local default. Optional repository variables are set under **Settings > Secrets and variables > Actions > Variables**: `SECTION11_ROUTE_WEATHER=0` disables weather, and `SECTION11_ROUTE_WEATHER_DEFAULT_START=09:30` chooses a strict local HH:MM default. Unset/empty means on and 10:00; an invalid nonempty start makes assumed-departure weather unavailable. The shared workflow passes both settings, with details in [Optional route-weather variables](../json-auto-sync/SETUP.md#optional-route-weather-variables). The AI asks for the actual start or asks you to set it in Intervals.icu. New points/hours can fetch on the next user-triggered sync, subject to request limits and failure/provider backoff. No extra export/upload step is required. See [departure handling](../../README.md#route-weather-departure).

Uses the same GitHub Actions workflow as auto-sync, but without the cron schedule.
Tap Sync Now in your repo's README, then use the repository delivery flow below.
The completed run's artifact is a data-only extra; it does not include the
installed Section 11 files needed by the coach.

Each Sync also preserves `archive/carry-forward.state` in the repository through the managed publisher, in the same commit as the export. This compact recovery file changes only when its protected summaries change; the next runner can recover them if latest.json is damaged. Update and rollback preserve it. The producer and controller arrive together through the normal release and Update path, without replacing your workflow or adding Intervals.icu requests. The file is excluded from AI companions and the training-data download. AI tools must ignore it, even if a repository connector exposes it, and read only `latest.json.carry_forward` for recovery notices.

On-demand can use **4 requests on a quiet cache hit instead of about 31** with the updated workflow. Only profile settings, aggregate curves and current-window messages persist in a plain Actions cache outside the checkout. Raw core responses and request accounting stay runner-only. Neither the cache nor `state/` is committed or included in the download; AI tools use the training files and ignore both. First runs, refreshes and misses cost more. There is no hosted daily balance, step-down or budget pause; pacing and provider holds remain. See [private state and request limits](../json-auto-sync/SETUP.md#private-state-and-request-limits).

In a public repository, someone who deliberately opens a pull request can read the workflow cache: full power/HR curves, sport/zone settings, profile details (location, birth date, sex, height, weight and resting-HR fallbacks, and profile notes), and recent activity-note text. Most of this also appears in the published training files; the cache never holds keys, credentials, raw activities, wellness or health events.

GitHub deletes caches unused for 7 days, so rarely run On-demand gains little; a cache miss just means normal reads.

**Existing repositories:** keep optional environment settings and secret names in the published manual-only template. It has no schedule or unattended maintenance. Verified managed code retains export freshness, staging, cache restore and changed-only save after confirmed publication. Follow the [migration steps](#updating-an-existing-repository).

We recommend one setup per user. Stop the old timer or workflow before changing the sync path or moving machines, to protect Intervals.icu. Counts are per data folder, API key and athlete, with no coordination across folders.

`latest.json.source_freshness` travels with the normal export: each source's `fresh`/`stale`/`deferred`/`unavailable` status, acquisition age and coverage, plus the hosted per-run request count, source schedule and warnings. Null age means unknown; the export timestamp does not renew source ages. See [Source freshness](../json-examples/README.md#source-freshness).

Each successful run with updated sync.py produces `latest.json.sleep_context`, using a 35-date wellness window (D−34..D) and preserving the original 28-date slice for existing consumers. There is no separate sleep file or history-refresh requirement. Retained wellness keeps its acquisition time in `source_updated_at`; `source_freshness` describes its refresh status. The shared workflow already includes latest.json in repository delivery and the download artifact, so this field needs no workflow or upload change. The AI discovers it through `READ_THIS_FIRST.sleep_context_note`. It is low-confidence context only, never readiness; missing dates, unknown athlete timezone or current-date mismatch remain explicit unavailable states. It refreshes only when you run sync, so an old attachment is not a current assessment.

The shared publisher retains the sync-declared JSON/PNG file list and fixed
validation rules, so future companion names/folders need only a script update.
See [Owner-controlled workflow maintenance](../json-auto-sync/SETUP.md#owner-controlled-workflow-maintenance)
for limits, safe fallback and the replacement steps. Compact forecast snapshots stay bounded.
Personal files, private request state and active workflows stay outside the managed release.

The repository retains `route_eta_history.json` and up to four ordered `maps/weather/` PNG pages per ride, for six rides (24 pages) between runs. All companion locations in `latest.json.data_overview` are relative to the latest file's folder. The AI reads that overview first and resolves paths against the current data source. It reads and shows matching map pages in their listed order only when it can actually read each PNG; otherwise it uses the text brief. Maps and ETA history are not added to the data-only run artifact. Use the repository delivery below for the installed protocol and available companions; folderless uploads are matched by filename.

**Flow:** Tap Sync Now → Run workflow → use a connector or link to your own repo.
If the chat can use neither, use GitHub **Code > Download ZIP** on your own
repository and give that ZIP to the chat or project. It includes `section11/`.
An uploaded ZIP is a snapshot; re-upload for fresh data and after updates.

**GitHub connector users:** If your AI platform has a GitHub connector, you can skip the download, but refresh, sync, or re-import after the workflow commits, since not all connectors pick up changes automatically. See the [connector table](../../README.md#platform-setup).

---

## Prerequisites

- [Intervals.icu](https://intervals.icu) account with training data
- [GitHub](https://github.com) account
- 10 minutes for setup

---

## Step 1: Get Your Intervals.icu Credentials

- **Athlete ID**: Intervals.icu → Settings → bottom of page (e.g., `i123456`)
- **API Key**: Intervals.icu → Settings → Developer Settings → API Key

---

## Step 2: Set Up GitHub Repository

1. Go to [github.com/new](https://github.com/new)
2. Name it something like `training-data`
3. Set to **Private** (recommended)
4. Leave **Add a README file** unchecked. The first Sync installs the standard README with your Sync Now link; successful syncs update its timestamp.
5. Click **Create repository**

Use the published [On-demand workflow](auto-sync.yml), or the exact
`section11-YYYY.MM.DD-on-demand.yml` asset on the matching
[official release](https://github.com/CrankAddict/section-11/releases/latest).
For a same-day release, the asset name adds `-N` after the date.
Its bytes are verified against the release manifest. Use a release supporting the
final workflow, with **Other** and the first-adoption checkbox; do not use raw-main
code. **Old templates only:** `UNSEALED` means the template is not ready to use;
never invent its pins.
No release ZIP or hidden-folder upload is required.

1. Click **Add file > Create new file**, or edit the existing workflow.
2. Name it `.github/workflows/auto-sync.yml` and paste the On-demand template.
   It already has only `workflow_dispatch`. Keep optional settings and secrets.
3. If the repository already has Section 11 files, read this warning immediately
   before committing. Brand-new repositories can skip this warning:

   > Anything you added or changed inside section11/ will be deleted. Move what you want to keep to custom/ first.

   Any existing root `sync.py`, `push.py` and `pull.py` will be removed. Outside
   `section11/`, this applies to any file in any folder named exactly like a
   release or historical Section 11 file, except the [keep list](../maintenance/UPDATING.md#local-updates-and-automatic-toggle).
   Protection ignores case; removal requires exact spelling. Keep your own files
   in `custom/` or outside the data repository. Data, settings,
   custom files and the private dossier stay in place.
4. Hosted push users also replace `.github/workflows/push-workout.yml` with the
   [thin push stub](../agentic/push-workout.yml) in the **same owner commit, before
   the first Sync**. Use GitHub's web editor (`github.dev`, opened with `.` from
   the repository), edit both files, then stage and commit both through Source
   Control. Commit through your repository's normal policy.

That edit accepts installation. The first Sync installs the complete verified
release, receipt and missing custom guidance in one validated direct commit,
then publishes data separately. The standard README includes your repository's
Sync Now link.

The push stub keeps its dispatch URL, inputs and preview/confirm contract.
External imports of root tools move to `section11/examples/agentic/`. Until the
first Sync installs Section 11, push stops with:
"Section 11 is not installed yet; run Sync once first".

---

## Step 3: Add Repository Secrets

1. Go to your repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Add these secrets:

| Secret Name | Value |
|-------------|-------|
| `ATHLETE_ID` | Your Intervals.icu athlete ID (e.g., `i123456`) |
| `INTERVALS_KEY` | Your Intervals.icu API key |

**Optional secrets**: see [auto-sync SETUP](../json-auto-sync/SETUP.md#step-3-add-repository-secrets) for `WEEK_START` and `ZONE_PREFERENCE`.

---

## Step 4: Enable Workflow Permissions

1. In **Settings** → **Actions → General**
2. Scroll to **"Workflow permissions"**
3. Select **"Read and write permissions"**
4. Click **Save**

Effective `contents: write` and Actions-run read access are required. No
PR-creation setting or new personal token is needed. A protected-branch refusal
stops without retry or alternate credentials; the owner must supply a
policy-compatible route.

---

## Step 5: README link

Install, update and rollback refresh the standard README while retaining its sync
timestamp; Sync changes only that timestamp between updates. See the
[update guide](../maintenance/UPDATING.md#updating-section-11).

---

## Step 6: First Run

1. Go to your repo → **Actions** tab
2. If prompted, enable workflows
3. Click on "Auto-Sync Intervals.icu Data"
4. Click **Run workflow** → **Run workflow**
5. Wait 30–60 seconds for the run to complete

Confirm **Auto-Sync Intervals.icu Data** appears in Actions. If it is missing,
check YAML and default-branch registration before requesting a run. A file alone
is not proof of registration. Keep the default branch selected and Operation
**Sync**. Inspect the installation commit and receipt, then the data commit and
its remote readback. No PR or merge is involved.

After the run completes:
- **Connector users:** Refresh, sync, or re-import so your AI picks up the new files. See the [connector table](../../README.md#platform-setup).
- **Download users:** Use your own repository's **Code > Download ZIP**, as above.

From now on, just tap **🔄 Sync Now** in your repo's README.

---

## Usage

**Calendar naming:** To let the calendar support a deload week, name its sessions with "Deload" or "Recovery week", for example "Recovery week - easy ride". Single recovery rides inside normal weeks are not read as a deload week. Names support the phase assessment; they do not establish it on their own.

### From your phone

Open your repo in a browser → tap **🔄 Sync Now** → **Run workflow**. When the run completes, refresh your connector or repository link, or replace the uploaded repository ZIP as above.

### With an AI connector

AI platforms with GitHub connectors can read the repo directly, but refresh behavior varies; some need a manual sync or re-import before they see the new files. Check the [connector table](../../README.md#platform-setup) for your platform, then refresh accordingly. No download needed once the connector has the current files.

### Without a connector

Use a link to your own repository if the chat can read it. Otherwise use the
repository ZIP delivery above, which includes both data and installed Section 11 files.

---

## Security

Downloading the repository ZIP and giving it to a chat takes that copy outside GitHub authentication. A connector reads the repository directly, so processing and retention there are governed by that AI platform's terms rather than by Section 11. Where the files go from there depends on what you configure and which AI you point them at. This workflow publishes no GitHub Pages site. Private repos remain private. The workflow and required-secret handling are identical to auto-sync apart from the manual trigger. See [Privacy & Security](../../README.md#privacy--security) for the full policy.

---

## Section 11 updates

Use the same workflow's **Update**, **Status** or **Rollback** operation. Half mode
is the default: an outstanding verified update gives a fixed `update_notice` on the
next export, and **Update** installs it. `SECTION11_AUTO_UPDATE=true` opts into
automatic installation. Each run selects and verifies the latest official runtime;
half mode still uses the older compatible installed application. After data work,
both modes defer automatic application maintenance if another run is active or
finished within ten minutes, including failures. Completed skipped runs do not
count. The allowance does not skip data sync; a verification failure can still
stop the run. There is no check-only commit. On-demand checks only on runs you
start; there is no unattended check or backup schedule.

The Operation menu has **Sync**, **Update**, **Status**, **Rollback** and **Sync timer**,
plus **Other**. Its text field is only for operations added by later official
releases; unknown operations stop safely. Update, Status and Rollback do no data
sync. The first-adoption checkbox is for the first Sync after moving over, not
normal runs. A later good release fixes a broken runtime; Rollback remains for
a bad application release and may itself be blocked by a broken runtime.

**Old workflow (v11.105 only):** daily maintenance from 04:00 UTC still applies
on user-started runs until you move over.
Current workflows accept same-day releases. An old pinned workflow with a
recorded plain-date install keeps syncing and waits for the next plain-date
release. For new setups using outdated files, see [same-day release compatibility](../maintenance/UPDATING.md#same-day-releases).
See [updates and recovery](../maintenance/UPDATING.md#github-installation-and-updates).

## Updating an Existing Repository

Optionally [move to the final hosted workflow](../maintenance/UPDATING.md#move-to-the-final-hosted-workflow)
to receive same-day releases. Keep your optional settings and
secret names. Use the On-demand template as supplied; do not add the scheduled
template's cron. For older root-tool setups, Step 2 also covers the push stub;
hosted push users replace both stubs in the same owner commit, before the first Sync.

---

## Troubleshooting

See the [auto-sync troubleshooting guide](../json-auto-sync/SETUP.md#troubleshooting). The same workflow runs in both paths.

For request holds or a pause, check other runs and tools using the key and wait for the stated hold to expire before requesting another run. Each fresh runner has its own local count, not a complete daily total for the key. See [request allowance troubleshooting](../json-auto-sync/SETUP.md#request-allowance-provider-holds-or-stale-sources).
