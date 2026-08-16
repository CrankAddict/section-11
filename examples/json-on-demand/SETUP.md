# On-Demand Sync

Trigger a fresh Intervals.icu sync from your phone or browser, then download the data files. No local Python, no scheduled runs — you sync when you want to.

> **Want automatic sync on a schedule?** See [json-auto-sync](../json-auto-sync/SETUP.md) instead.

> **Running an agentic platform locally?** See [json-local-sync](../json-local-sync/SETUP.md) — no GitHub needed.

---

## Overview

Uses the same GitHub Actions workflow as auto-sync, but without the cron schedule. You tap a link in your repo's README to trigger a sync, and download the resulting files as a ZIP artifact from the completed run.

**Flow:** Tap Sync Now → Run workflow → Download artifact ZIP → Attach to AI chat.

**GitHub connector users:** If your AI platform has a GitHub connector, you can skip the download — but refresh, sync, or re-import after the workflow commits, since not all connectors pick up changes automatically. See the [connector table](../../README.md#platform-setup).

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

**Important:** Edit `auto-sync.yml` after copying — remove the `schedule` block so only `workflow_dispatch` remains:

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

**Optional secrets** — see [auto-sync SETUP](../json-auto-sync/SETUP.md#step-3-add-repository-secrets) for `WEEK_START` and `ZONE_PREFERENCE`.

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
- **Connector users:** Refresh, sync, or re-import so your AI picks up the new files — see the [connector table](../../README.md#platform-setup).
- **Download users:** Click the completed run → scroll to **Artifacts** → download **training-data** ZIP.

From now on, just tap **🔄 Sync Now** in your repo's README.

---

## Usage

### From your phone

Open your repo in a browser → tap **🔄 Sync Now** → **Run workflow**. When the run completes, download the artifact or refresh, sync, or re-import through your connector as required.

### With an AI connector

AI platforms with GitHub connectors can read the repo directly, but refresh behavior varies — some need a manual sync or re-import before they see the new files. Check the [connector table](../../README.md#platform-setup) for your platform, then refresh accordingly. No download needed once the connector has the current files.

### Without a connector

Download the **training-data** artifact ZIP from the completed run, then attach the JSON files to your AI chat.

---

## Security

All data stays behind GitHub authentication. No public pages, no tokens stored in the browser. Private repos remain private. This is the same security model as auto-sync — the only difference is you trigger the workflow manually.

---

## Troubleshooting

See the [auto-sync troubleshooting guide](../json-auto-sync/SETUP.md#troubleshooting) — the same workflow runs in both paths.
