# On-Demand Sync

Trigger a fresh Intervals.icu sync from your phone or browser, then download the data files. No local Python, no scheduled runs. You sync when you want to.

> **Want automatic sync on a schedule?** See [json-auto-sync](../json-auto-sync/SETUP.md) instead.

> **Running an agentic platform locally?** See [json-local-sync](../json-local-sync/SETUP.md). No GitHub needed.

---

## Overview

Date-only/exact-midnight workouts use the labelled 10:00 local default. Optional repository variables are set under **Settings > Secrets and variables > Actions > Variables**: `SECTION11_ROUTE_WEATHER=0` disables weather, and `SECTION11_ROUTE_WEATHER_DEFAULT_START=09:30` chooses a strict local HH:MM default. Unset/empty means on and 10:00; an invalid nonempty start makes assumed-departure weather unavailable. The shared workflow passes both settings, with details in [Optional route-weather variables](../json-auto-sync/SETUP.md#optional-route-weather-variables). The AI asks for the actual start or asks you to set it in Intervals.icu. New points/hours can fetch on the next user-triggered sync, subject to request limits and failure/provider backoff. No extra export/upload step is required. See [departure handling](../../README.md#route-weather-departure).

Uses the same GitHub Actions workflow as auto-sync, but without the cron schedule. You tap a link in your repo's README to trigger a sync, and download the resulting files as a ZIP artifact from the completed run.

On-demand keeps its current behavior at about **31 Intervals.icu requests per run**; first runs and larger refreshes can cost more. Its request savings come in a later release. Each run creates private request accounting and source responses fresh in the runner's `<data folder>/state/`, with `request-budget/<identity>/`, `sources/<identity>/` and a generated `README.md`. The supplied workflow never keeps, commits or uploads it in the artifact ZIP, so the AI does not receive it through the repository, connector or upload. `data_overview.state_note` and `READ_THIS_FIRST.state_note` explicitly tell AI tools to ignore `state/` if another path exposes it. The local `check_interval_minutes` setting does not change On-demand runs. See [private state and request limits](../json-auto-sync/SETUP.md#private-state-and-request-limits).

We recommend one setup per user. Stop the old timer or workflow before changing the sync path or moving machines, to protect Intervals.icu. Counts are per data folder, API key and athlete, with no coordination across folders.

`latest.json.source_freshness` travels with the normal export: each source's `fresh`/`stale`/`deferred`/`unavailable` status, acquisition age and coverage, plus local budget, schedule and warnings. Null age means unknown; the export timestamp does not renew source ages. See [Source freshness](../json-examples/README.md#source-freshness).

Each successful run with updated sync.py produces `latest.json.sleep_context`, using a 35-date wellness window (D−34..D) and preserving the original 28-date slice for existing consumers. There is no separate sleep file or history-refresh requirement. Retained wellness keeps its acquisition time in `source_updated_at`; `source_freshness` describes its refresh status. The shared workflow already includes latest.json in repository delivery and the download artifact, so this field needs no workflow or upload change. The AI discovers it through `READ_THIS_FIRST.sleep_context_note`. It is low-confidence context only, never readiness; missing dates, unknown athlete timezone or current-date mismatch remain explicit unavailable states. It refreshes only when you run sync, so an old attachment is not a current assessment.

For 11.80 / sync 3.146, replace sync.py and the shared workflow once, keeping your manual-only trigger. It publishes the sync-declared JSON/PNG file list under fixed validation rules, so future companion names/folders need only a script update. See the [GitHub setup update instructions](../json-auto-sync/SETUP.md#updating-an-existing-repository) for limits, safe fallback and the replacement steps. Compact forecast snapshots stay bounded.

The repository retains `route_eta_history.json` and up to four ordered `maps/weather/` PNG pages per ride, for six rides (24 pages) between runs. All companion locations in `latest.json.data_overview` are relative to the latest file's folder. The AI reads that overview first and resolves paths against the current data source. It reads and shows matching map pages in their listed order only when it can actually read each PNG; otherwise it uses the text brief. Maps and ETA history are not added to the download artifact ZIP. Download users keep their existing JSON workflow with no extra steps; folderless uploads are matched by filename.

**Flow:** Tap Sync Now → Run workflow → Download artifact ZIP → Attach to AI chat.

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
4. Check **Add a README file**
5. Click **Create repository**

Then add these files:

| File | Location | Source |
|------|----------|--------|
| `sync.py` | Root | [examples/sync.py](../sync.py) |
| `auto-sync.yml` | `.github/workflows/` | [examples/json-auto-sync/auto-sync.yml](../json-auto-sync/auto-sync.yml) |
| `README.md` | Root (replace default) | [DATA_REPO_README_TEMPLATE.md](../json-auto-sync/DATA_REPO_README_TEMPLATE.md) |

**Important:** Edit `auto-sync.yml` after copying. Remove the `schedule` block so only `workflow_dispatch` remains:

```yaml
on:
  workflow_dispatch:  # Allow manual trigger
```

This prevents automatic runs. The workflow only runs when you trigger it.

**To create the workflow folder:**
1. Click "Add file" → "Create new file"
2. Name it: `.github/workflows/auto-sync.yml`
3. Paste the workflow content, remove the `schedule` block
4. Commit

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

---

## Step 5: Update README Template

Replace `YOUR_GITHUB_USER` and `YOUR_REPO_NAME` in `README.md` with your actual GitHub username and repo name.

---

## Step 6: First Run

1. Go to your repo → **Actions** tab
2. If prompted, enable workflows
3. Click on "Auto-Sync Intervals.icu Data"
4. Click **Run workflow** → **Run workflow**
5. Wait 30–60 seconds for the run to complete

After the run completes:
- **Connector users:** Refresh, sync, or re-import so your AI picks up the new files. See the [connector table](../../README.md#platform-setup).
- **Download users:** Click the completed run → scroll to **Artifacts** → download **training-data** ZIP.

From now on, just tap **🔄 Sync Now** in your repo's README.

---

## Usage

**Calendar naming:** To let the calendar support a deload week, name its sessions with "Deload" or "Recovery week", for example "Recovery week - easy ride". Single recovery rides inside normal weeks are not read as a deload week. Names support the phase assessment; they do not establish it on their own.

### From your phone

Open your repo in a browser → tap **🔄 Sync Now** → **Run workflow**. When the run completes, download the artifact or refresh, sync, or re-import through your connector as required.

### With an AI connector

AI platforms with GitHub connectors can read the repo directly, but refresh behavior varies; some need a manual sync or re-import before they see the new files. Check the [connector table](../../README.md#platform-setup) for your platform, then refresh accordingly. No download needed once the connector has the current files.

### Without a connector

Download the **training-data** artifact ZIP from the completed run, then attach the JSON files to your AI chat.

---

## Security

Downloading the artifact ZIP and attaching the JSON to a chat takes your data outside GitHub authentication. A connector reads the repository directly, so processing and retention there are governed by that AI platform's terms rather than by Section 11. Where the files go from there depends on what you configure and which AI you point them at. This workflow publishes no GitHub Pages site. Private repos remain private. The workflow and required-secret handling are identical to auto-sync apart from the manual trigger. See [Privacy & Security](../../README.md#privacy--security) for the full policy.

---

## Updating an Existing Repository

When the workflow template changes, follow [Updating an Existing Repository](../json-auto-sync/SETUP.md#updating-an-existing-repository) in the auto-sync guide, with these differences. Skip its step 2 (**Choose a schedule**) and step 8 (**Watch the next scheduled run**). The current `auto-sync.yml` includes a `schedule` block, so in its step 4, remove the `schedule:` block again before you commit and keep `workflow_dispatch:`, as in Step 2 of this guide; otherwise the workflow starts running on a schedule. Reapply any other changes you still want as usual.

---

## Troubleshooting

See the [auto-sync troubleshooting guide](../json-auto-sync/SETUP.md#troubleshooting). The same workflow runs in both paths.

For request holds or a pause, check other runs and tools using the key and wait for the stated hold to expire before requesting another run. Each fresh runner has its own local count, not a complete daily total for the key. See [request allowance troubleshooting](../json-auto-sync/SETUP.md#request-allowance-provider-holds-or-stale-sources).
