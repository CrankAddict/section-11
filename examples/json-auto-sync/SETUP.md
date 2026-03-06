# Data Mirror Setup Guide

This guide explains how to create an automated JSON data mirror of your Intervals.icu training data for use with AI coaching systems.

> **Prefer an interactive guide?** Paste [SETUP_ASSISTANT.md](../../SETUP_ASSISTANT.md) into any AI chat and it will walk you through this entire setup step by step.

---

## Overview

The data mirror automatically syncs your Intervals.icu metrics to a GitHub repository every 15 minutes, producing a static JSON URL that AI systems can read.

**Result:**
- `https://raw.githubusercontent.com/[you]/[repo]/main/latest.json`
- `https://raw.githubusercontent.com/[you]/[repo]/main/history.json`
- `https://raw.githubusercontent.com/[you]/[repo]/main/ftp_history.json`

---

## Prerequisites

- [Intervals.icu](https://intervals.icu) account with training data
- [GitHub](https://github.com) account
- 10 minutes for setup

---

## Step 1: Get Your Intervals.icu Credentials

**Finding your credentials:**
- **Athlete ID**: Intervals.icu → Settings → bottom of page (e.g., `i123456`)
- **API Key**: Intervals.icu → Settings → Developer Settings → API Key

---

## Step 2: Set Up GitHub Repository

### Option A: Fork (fastest)

1. Go to [github.com/CrankAddict/section-11](https://github.com/CrankAddict/section-11) → **Fork**
2. Rename to `training-data` or similar
3. Set to **Private** in repo settings
4. Skip to **Step 3: Add Repository Secrets**

### Option B: Create new repo

1. Go to [github.com/new](https://github.com/new)
2. Name it something like `training-data`
3. Set to **Private** (recommended) — most AI platforms now have GitHub connectors that can access private repos. See the [main README](../../README.md#platform-setup) for details.
4. Check Add a README file
5. Click **Create repository**

Then add these files to your repository:

| File | Location | Description |
|------|----------|-------------|
| `sync.py` | Root | The sync script |
| `auto-sync.yml` | `.github/workflows/` | GitHub Actions workflow |
| `DATA_REPO_README.md` | Root (rename to `README.md`) | README template with sync badge |

**To create the workflow folder:**
1. Click "Add file" → "Create new file"
2. Name it: `.github/workflows/auto-sync.yml`
3. Paste the workflow content from examples/json-auto-sync/auto-sync.yml
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

**Optional:** If your training week starts on a day other than Monday, add one more secret:

| Secret Name | Value |
|-------------|-------|
| `WEEK_START` | Training week start day: `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, or `sun` |

If not set, defaults to `mon` (ISO week). This controls phase detection windows — ensures deload/build classification aligns with your actual training week structure.

**Note:** `GITHUB_TOKEN` is provided automatically by GitHub Actions.

---

## Step 4: Enable Workflow Permissions

1. Still in **Settings**, click **Actions → General** in the left sidebar
2. Scroll down to **"Workflow permissions"**
3. Select **"Read and write permissions"**
4. Click **Save**

This allows the sync workflow to commit updated data files to the repo. Without this, the workflow may fail silently on push.

---

## Step 5: Enable GitHub Actions

1. Go to your repo → **Actions** tab
2. If prompted, enable workflows
3. Click on "Auto-Sync Intervals.icu Data" workflow
4. Click **Run workflow** → **Run workflow** (green button)

Wait 30-60 seconds, then check if `latest.json` has been updated.

If the run fails with a permission error, go back and check that workflow permissions are set to "Read and write" in Step 4.

---

## Step 6: Verify

Your data should now be accessible at:
```
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/latest.json
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/history.json
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/ftp_history.json
```

Test by opening the URLs in your browser — you should see your training data as JSON.

- `latest.json` — current 7-day snapshot with activities, wellness, fitness metrics, and derived Section 11 values
- `history.json` — longitudinal data with tiered granularity: daily (90 days), weekly (180 days), and monthly (up to 3 years). Generated automatically on first run, regenerated when outdated.

---

## FTP History Tracking

The sync script automatically creates and maintains `ftp_history.json` to track FTP changes over time. This enables **Benchmark Index** calculation.

```json
{
  "indoor": {
    "2025-10-15": 255,
    "2025-11-03": 260,
    "2025-12-01": 265
  },
  "outdoor": {
    "2025-10-15": 265,
    "2025-11-03": 270,
    "2025-12-01": 278
  }
}
```

- Created automatically on first run of `sync.py`
- New entries added only when FTP **changes** (not on every run)
- Indoor and outdoor FTP tracked separately
- GitHub Actions workflow commits updates automatically

### Benchmark Index

The Benchmark Index measures FTP progression over 8 weeks:

```
Benchmark Index = (Current FTP - FTP 8 weeks ago) / FTP 8 weeks ago
```

| Value | Interpretation |
|-------|----------------|
| +5% | Strong progression |
| +2% to +5% | Normal build phase gains |
| 0% to +2% | Maintenance |
| -2% to 0% | Minor regression (may be normal in recovery) |
| < -2% | Significant regression — investigate |

**Note:** Requires ~8 weeks of data before Benchmark Index becomes available.

---

## Usage with AI

Once set up, configure your AI platform using the instructions in the [main README](../../README.md#web-chat-setup).

Your JSON URLs:
```
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/latest.json
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/history.json
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/ftp_history.json
```

Provide all 3 URLs to your AI coach — `latest.json` has the current 7-day snapshot and `history.json` provides longitudinal context for trend analysis.

---

## Troubleshooting

### Workflow fails with "secret not set"
- Check secret names match exactly: `ATHLETE_ID`, `INTERVALS_KEY`
- Secrets are case-sensitive

### Workflow fails with "untracked working tree files would be overwritten"
- This happens when generated files (like `history.json`) conflict during `git pull`
- Use the latest `auto-sync.yml` from this folder — it stages all generated files before pulling

### No data in latest.json
- Verify your Intervals.icu API key is valid
- Check you have activities in the last 7 days
- Look at workflow logs for specific errors

### ftp_history.json not updating on GitHub
- Ensure your `auto-sync.yml` includes `git add ftp_history.json`
- Check workflow logs for git errors

### history.json not generated
- History generates automatically on first run, then regenerates when outdated
- Delete `history.json` from your repo and re-run to force regeneration
- Check workflow logs — history generation is non-critical and won't fail the sync

### 404 error on JSON URL
- Ensure `latest.json` exists in repo root
- If using a public repo, verify URL format (use `main` not `master`)
- For private repo access from AI platforms, see the [main README troubleshooting](../../README.md#troubleshooting)

For general AI platform issues (data not fetching, AI fabricating metrics, connector problems), see the [main README troubleshooting guide](../../README.md#troubleshooting).

---

## Customization

**Change sync frequency:**
Edit the cron schedule in `auto-sync.yml`:
- Every 15 min: `*/15 * * * *`
- Every hour: `0 * * * *`
- Every 6 hours: `0 */6 * * *`

**Change data range:**
Edit `sync.py` call in workflow:
```yaml
run: python sync.py --days 14
```

**Disable anonymization:**
```yaml
run: python sync.py --no-anonymize
```

---

## Privacy Notes

By default, the script anonymizes your data:
- Athlete ID → "REDACTED"
- Outdoor activity names → "Training Session"

Activity and event IDs are always real (opaque database keys, not PII) to enable features like coach annotations and planned-vs-actual pairing. Indoor/virtual ride names are preserved for workout identification.

For additional privacy, use a **private repository** and a separate GitHub account for your data repository.

---

## Files Reference

| File | Purpose | Auto-created |
|------|---------|--------------|
| `latest.json` | Current 7-day training data for AI consumption | Yes |
| `history.json` | Longitudinal data — daily (90d), weekly (180d), monthly (3y) | Yes |
| `ftp_history.json` | FTP progression tracking for Benchmark Index | Yes |
| `archive/` | Timestamped snapshots of each sync | Yes |

## Update Notifications

The sync script automatically checks for upstream protocol updates from the [Section 11 repository](https://github.com/CrankAddict/section-11). When a new version is available, a GitHub Issue is created in your data repo with a summary of changes. No action is needed — just watch your Issues tab.
