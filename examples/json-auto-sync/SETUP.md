# Data Mirror Setup Guide

This guide explains how to create an automated JSON data mirror of your Intervals.icu training data for use with AI coaching systems.

> **Prefer an interactive guide?** Paste [SETUP_ASSISTANT.md](../../SETUP_ASSISTANT.md) into any AI chat and it will walk you through this entire setup step by step.

> **Running an agentic platform locally?** If your AI coach runs on the same machine as your data (OpenClaw, Claude Code, Cowork, etc.), consider [local sync](../json-local-sync/SETUP.md) instead (simpler setup, and no GitHub repository in the path). Where your data goes still depends on what you configure and which AI you point at it; see [Privacy & Security](../../README.md#privacy--security).

---

## Overview

The data mirror syncs your Intervals.icu metrics to a GitHub repository on a schedule, every 30 minutes by default, producing JSON files that AI systems can read through a GitHub connector or other authenticated repository access, or by URL for a public repository. GitHub runs scheduled workflows on a best-effort basis, so a scheduled sync can be late or skipped. For fresh data right after a workout, use [Sync Now](#sync-now). See [Sync Schedule and GitHub Actions Usage](#sync-schedule-and-github-actions-usage) before choosing a different schedule.

**Result:** these files in your repository, shown here as raw URL patterns. Plain raw URLs work without GitHub authentication only for a public repository; for a private repository, see [Step 6](#step-6-verify) and [Usage with AI](#usage-with-ai).
- `https://raw.githubusercontent.com/[you]/[repo]/main/latest.json`
- `https://raw.githubusercontent.com/[you]/[repo]/main/history.json`
- `https://raw.githubusercontent.com/[you]/[repo]/main/ftp_history.json`
- `https://raw.githubusercontent.com/[you]/[repo]/main/intervals.json`
- `https://raw.githubusercontent.com/[you]/[repo]/main/routes.json` (always written; route entries only for planned events with GPX/TCX attachments)
- `https://raw.githubusercontent.com/[you]/[repo]/main/saved_workouts.json`

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

### Create a new private repo

> **Don't fork Section 11 for this.** Forks of a public repository are always public and their visibility cannot be changed. A forked data repo would publish your training data.

1. Go to [github.com/new](https://github.com/new)
2. Name it something like `training-data`
3. Set to **Private**. See the [connector table](../../README.md#platform-setup) for platform support.
4. Check Add a README file
5. Click **Create repository**

Then add these files to your repository:

| File | Location | Description |
|------|----------|-------------|
| `sync.py` | Root | The sync script |
| `auto-sync.yml` | `.github/workflows/` | GitHub Actions workflow |
| `DATA_REPO_README_TEMPLATE.md` | Root (rename to `README.md`) | README template with sync badge and Sync Now link |

**To create the workflow folder:**
1. Click "Add file" → "Create new file"
2. Name it: `.github/workflows/auto-sync.yml`
3. Paste the workflow content from examples/json-auto-sync/auto-sync.yml
4. Commit

The workflow syncs every 30 minutes by default. To use Fast mode or a hybrid schedule instead, edit its `schedule` block as described in [Sync Schedule and GitHub Actions Usage](#sync-schedule-and-github-actions-usage).

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

If not set, defaults to `mon` (ISO week). This controls phase detection windows (ensures deload/build classification aligns with your actual training week structure).

**Optional:** If you want HR zones used for aggregations in specific sports (e.g., running with auto-generated watch power):

| Secret Name | Value |
|-------------|-------|
| `ZONE_PREFERENCE` | Per-sport zone override, e.g. `run:hr,cycling:power` |

Only override what you need. Unspecified sports default to power-preferred with HR fallback. Valid values per sport are `power` or `hr`. Sport families: `cycling`, `run`, `ski`, `rowing`, `swim`, `walk`, `strength`, `other`.

**Note:** `GITHUB_TOKEN` is provided automatically by GitHub Actions.

---

## Step 4: Enable Workflow Permissions

1. Still in **Settings**, click **Actions → General** in the left sidebar
2. Scroll down to **"Workflow permissions"**
3. Select **"Read and write permissions"**
4. Click **Save**

This allows the sync workflow to commit updated data files to the repo. The workflow file also requests `contents: write` for itself. Whether that request alone is enough without this repository setting has not yet been validated, so keep this setting for now. If GitHub refuses the push, the run fails with an error in its log; it does not fail silently.

---

## Step 5: Enable GitHub Actions

1. Go to your repo → **Actions** tab
2. If prompted, enable workflows
3. Click on "Auto-Sync Intervals.icu Data" workflow
4. Click **Run workflow** → **Run workflow** (green button)

Leave the branch selector on your default branch (normally `main`). A manual run started from any other branch stops at its first step without syncing.

Wait 30-60 seconds, then check if `latest.json` has been updated. This manual run is the same [Sync Now](#sync-now) you can use at any time.

If the run fails with a permission error, go back and check that workflow permissions are set to "Read and write" in Step 4.

---

## Step 6: Verify

Check the result in your repository's normal **Code** view on github.com:

1. Confirm that the latest commit is a new `Sync training data` commit
2. Open `latest.json` and check that `metadata.last_updated` changed to the time of this sync
3. Open `history.json`, `ftp_history.json`, `intervals.json`, `routes.json` and `saved_workouts.json` to confirm they are there

Do not check a private repository with plain `raw.githubusercontent.com` URLs. They normally return 404 for a private repository when the request carries no GitHub authentication, and being signed in to github.com in your browser does not make them a reliable check. When your AI needs the files, use a GitHub connector or other authenticated repository access (see [Usage with AI](#usage-with-ai)).

For reference, each file's raw URL follows this pattern. These URLs are for a public repository, or for tooling that explicitly supplies authenticated GitHub access:
```
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/latest.json
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/history.json
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/ftp_history.json
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/intervals.json
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/routes.json
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/saved_workouts.json
```

- `latest.json`: current 7-day snapshot with activities, wellness, fitness metrics, and derived Section 11 values. Rewritten on every successful sync.
- `history.json`: longitudinal data with tiered granularity: daily (90 days), weekly (180 days), and monthly (up to 3 years). Generated automatically on first run, regenerated when outdated.
- `intervals.json`: per-interval segment data for recent structured sessions (14-day retention). Written on every successful sync; its activity list can be empty when no recent activity has detected interval structure.
- `routes.json`: route/terrain data for planned events with GPX/TCX attachments. Includes climb/descent detection, course character, and polyline. Written on every successful sync, with `"events": []` when no planned event has an applicable attachment. Parsed routes are cached by attachment ID.
- `saved_workouts.json`: read-only mirror of your Intervals.icu saved workouts, with folders and complete workout definitions. Refreshed on its own 6-hour throttle rather than every sync, and the last good copy is kept when a refresh fails.

---

## Sync Schedule and GitHub Actions Usage

### Sync Now

**Sync Now is the way to get fresh data right after a workout.** Scheduled syncs are best-effort and can arrive up to a full interval later, or not at all.

1. Open your data repository and tap **🔄 Sync Now** in its README, or go to **Actions → Auto-Sync Intervals.icu Data**
2. Click **Run workflow**, keep your default branch selected, and confirm
3. When the run completes, the new data is committed to the repository

A manual run also uploads the generated JSON files as a **training-data** artifact on the run page, kept for seven days, for uploading to an AI chat. If another sync is already running, your run waits for it to finish. Each manual run counts toward your GitHub Actions minutes like any other run.

### Default schedule

```yaml
- cron: '7,37 * * * *'
```

- Checks every 30 minutes, at 7 and 37 minutes past each hour (UTC)
- The offsets avoid the start of the hour, which GitHub documents as its busiest time for scheduled workflows
- When GitHub runs the schedule on time, new data in Intervals.icu waits on average 15 minutes, and at most 30 minutes, for the next scheduled sync
- GitHub can still delay or drop scheduled runs, so Sync Now remains the immediate path

### GitHub Actions minutes

In a private repository, every run uses your account's GitHub Actions minutes. GitHub rounds each job up to a whole minute, so a sync that finishes in under a minute still counts as one billed minute. The monthly allowance for standard runners is 2,000 minutes on GitHub Free and 3,000 minutes on GitHub Pro and Team, shared by all private-repository workflows in your account. See [GitHub's billing documentation](https://docs.github.com/en/billing/concepts/product-billing/github-actions) for current figures. What happens after the allowance is used depends on your account's payment and budget settings.

Estimates below use the worst case: a 31-day month with every scheduled run executed.

| Schedule | Jobs per day | Jobs in 31 days | GitHub Free (2,000) | Pro or Team (3,000) |
|----------|-------------:|----------------:|---------------------|---------------------|
| Default, every 30 minutes | 48 | 1,488 | 512 minutes left | 1,512 minutes left |
| Fast mode, every 15 minutes | 96 | 2,976 | Exceeds the allowance by 976 | 24 minutes left |

- The minutes left must also cover Sync Now runs, failed runs, re-runs and any other workflows in your account, such as `push-workout.yml`
- GitHub sometimes delays or skips scheduled runs, so real usage can be lower. Do not rely on that: budget for the full count
- If you do not know your plan, assume GitHub Free
- Public repositories do not use standard-runner minutes, but a public repository publishes all of your committed training data. See [Privacy Notes](#privacy-notes)

### Fast mode

```yaml
- cron: '7,22,37,52 * * * *'
```

Fast mode checks every 15 minutes, all day. It is **not suitable for GitHub Free** unless you have intentionally set up paid usage beyond the allowance, and it uses almost all of a Pro or Team allowance before any manual runs or other workflows.

### Advanced hybrid schedules

A hybrid schedule checks more often during an active window that you set in UTC, and hourly otherwise. It uses two ordinary cron lines, which GitHub reads in UTC like the Default and Fast schedules. Do not add a `timezone:` line to either entry: Section 11 does not rely on it, because in testing an entry with `timezone:` ran as if its hours were in UTC. Sync Now remains the way to get fresh data immediately.

The window is fixed in UTC, and the schedule does not adjust itself. Where daylight saving time applies, the same UTC window normally moves by one hour on your local clock when your UTC offset changes. To keep the same local-clock hours all year, recalculate the UTC hours after each offset change and replace both lines yourself; this is optional manual maintenance. With a half-hour or quarter-hour UTC offset, the window starts and ends partway through a local hour. That is expected: the UTC hours remain authoritative.

**Standard hybrid:** 16 active hours (06:00 to 21:59 UTC), every 20 minutes while active, hourly otherwise. 56 jobs a day, 1,736 in 31 days, leaving 264 minutes of a GitHub Free allowance.

```yaml
on:
  schedule:
    - cron: '7,27,47 6-21 * * *'
    - cron: '7 0-5,22-23 * * *'
  workflow_dispatch:
```

**Extended hybrid (lower headroom):** 18 active hours (06:00 to 23:59 UTC), every 20 minutes while active, hourly otherwise. 60 jobs a day, 1,860 in 31 days, leaving only 140 minutes of a GitHub Free allowance.

```yaml
on:
  schedule:
    - cron: '7,27,47 6-23 * * *'
    - cron: '7 0-5 * * *'
  workflow_dispatch:
```

**Fast hybrid (lower headroom):** at most 12 active hours (07:00 to 18:59 UTC here), every 15 minutes while active, hourly otherwise. 60 jobs a day, 1,860 in 31 days, leaving only 140 minutes of a GitHub Free allowance.

```yaml
on:
  schedule:
    - cron: '7,22,37,52 7-18 * * *'
    - cron: '7 0-6,19-23 * * *'
  workflow_dispatch:
```

To build your own window, choose its start hour in UTC (`H`, 0 to 23), its length in whole hours (`A`, 1 to 23) and its active interval (`I`, 20 or 15 minutes). The active hours are `H` through `H+A-1`, continuing from 23 to 0, and every other hour is outside the window. The active line uses minutes `7,27,47` at 20 minutes or `7,22,37,52` at 15 minutes; the outside line uses minute `7`. Then check its Actions usage against your plan's allowance in [GitHub Actions minutes](#github-actions-minutes):

```text
jobs/day = active hours × (60 / active interval) + outside-window hours
monthly worst case = jobs/day × 31
minutes left = allowance − monthly worst case
```

- **Above your allowance:** do not use it unless you have deliberately set up paid usage beyond the allowance
- **Fewer than 140 minutes left:** not recommended
- **140 to 263 minutes left:** lower headroom, like the Extended and Fast hybrid profiles
- **264 minutes or more left:** acceptable under this calculation, but the minutes left must still cover Sync Now runs, failed runs and other workflows
- **GitHub Free:** 20 minutes is the shortest safe active interval for a 16- or 18-hour window with hourly checks outside it
- 13 active hours at 15 minutes gives 1,953 jobs and leaves only 47 minutes. It is not recommended
- 16 active hours at 15 minutes gives 2,232 jobs, and 18 hours at 15 minutes gives 2,418 jobs. Both exceed GitHub Free
- Faster or longer windows need Pro, Team or paid usage, or a shorter active window
- Every hour from 0 to 23 must appear in exactly one of the two lines, and `workflow_dispatch:` must stay
- A window that crosses midnight uses split hour ranges, never a wrap-around range such as `14-5`. For example, an active window from 14:00 to 05:59 UTC at 20 minutes uses `'7,27,47 0-5,14-23 * * *'` and `'7 6-13 * * *'`
- A UTC schedule has no daylight-saving transitions, so the 31-day estimate applies all year

## How the Workflow Works

The workflow file is the authority for this behavior. In outline:

- **Actions:** GitHub's checkout, setup-python and upload-artifact actions are pinned to full commit SHAs of their current Node 24 releases, with the release version in a comment
- **Permissions:** the workflow requests only `contents: write`
- **One sync at a time:** runs share one concurrency group and queue instead of cancelling each other. After a GitHub outage, several queued runs may execute one after another, and each counts as a billed minute
- **Time limit:** a run is stopped after 15 minutes. A normal sync finishes in well under a minute, but a first sync that builds `history.json` can take longer; if a first run is stopped at the limit, raise `timeout-minutes` in the workflow
- **Default branch only:** a manual run started from another branch stops before any secret is used or anything is synced
- **Credential masking:** `sync.py` prints the first five characters of your athlete ID and API key; the workflow registers both with GitHub's log masking before `sync.py` runs
- **Output checks:** the run fails if `latest.json` is missing, is not valid JSON, or was not rewritten by this sync, or if any other generated file is not valid JSON
- **Artifact first:** a manual run uploads the training-data artifact before anything is committed, so a later publishing problem does not remove your download
- **One commit:** the generated files, the daily archive file and the README timestamp are committed together and pushed once, on top of the latest state of your default branch. Your own changes to other files, including the README, are kept
- **Generated files changed during the run:** if a generated file changed in the repository after the run started, for example because you deleted `history.json`, the run fails without publishing and the next run syncs again
- **Push outcome:** if a push does not report success, the workflow reads the branch back before doing anything else:
  - if this run's commit is on the branch, the run succeeds
  - if it is confirmed absent, the workflow retries, up to three attempts in total, and then fails with a message that no commit from this run is on the branch
  - if the branch cannot be read back, or the check cannot be completed, the run stops with **OUTCOME UNKNOWN** (exit code 2) and does not retry, because the commit may or may not have landed

### Archive

- Each successful run copies `latest.json` to `archive/YYYY-MM/YYYY-MM-DD.json`, using the UTC date
- Later successful runs on the same UTC day overwrite that file, so the current tree gains at most one archive file per day
- This limits the number of files in the current tree; it does not shrink Git history, which keeps every committed version
- Timestamped archive files written by earlier versions of the workflow (`YYYYMMDD_HHMMSS.json`) are left untouched. You can delete them in a normal commit if you want a smaller current tree, for example for platforms with file-count import limits. That removes them from the current tree only; they remain in Git history
- Rewriting Git history to remove old files is destructive and is not covered by this guide

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
- The file may be rewritten on every sync without any content change; Git only records a change when an FTP value changes
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
| < -2% | Significant regression. Investigate |

**Note:** Requires ~8 weeks of data before Benchmark Index becomes available.

---

## Usage with AI

Once set up, configure your AI platform using the instructions in the [main README](../../README.md#web-chat-setup).

**Private repository with a GitHub connector or authenticated repository access (recommended):** If your AI platform has a GitHub connector, connect your data repo directly and ask the AI to read the files by path: `latest.json`, `history.json`, `intervals.json`, `routes.json` and `saved_workouts.json`, plus `ftp_history.json` when needed. It can read any other committed files the same way. No raw URLs are needed. Whether the AI sees new commits automatically, or needs you to refresh, sync or re-import, depends on the platform; see the [connector table](../../README.md#platform-setup). If you commit `DOSSIER.md` and `SECTION_11.md` to the repo as well, one connection covers your data, your dossier and the protocol. Check what the connector is actually scoped to. Where it exposes only the JSON, supply `SECTION_11.md` and the dossier separately.

A GitHub connector is normally read-only. Where its write access is unavailable or unverified, your AI cannot update `DOSSIER.md` in place: it returns the revised dossier as an artifact and says plainly that the source was not updated. You then commit that file over the official `DOSSIER.md`, or replace the official copy with it, as would a repository writer whose access you have verified separately. Nothing in the automated pipeline does this for you. The sync workflow commits only the generated data files and the repository README; it never touches your dossier.

**Public repository with URL fetch:** Use this only if your data repository is public. Everything committed to it, including your training data, is then readable by anyone (see [Privacy Notes](#privacy-notes)). Provide these URLs to your AI coach:
```
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/latest.json
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/history.json
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/ftp_history.json
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/intervals.json
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/routes.json
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/saved_workouts.json
```

**Private repository without a connector:** Run [Sync Now](#sync-now), download the **training-data** artifact from the run page, and upload the JSON files to your AI chat, or use another delivery path that supplies GitHub authentication. Plain raw URLs will not work for a private repository.

`latest.json` has the current 7-day snapshot, `history.json` provides longitudinal context for trend analysis, `intervals.json` has per-interval detail for recent structured sessions, `routes.json` has route/terrain data for planned events with GPX/TCX attachments (its `events` list is empty when there are none), and `saved_workouts.json` mirrors your Intervals.icu saved workouts.

---

## Troubleshooting

### Workflow fails with "secret not set"
- Check secret names match exactly: `ATHLETE_ID`, `INTERVALS_KEY`
- Secrets are case-sensitive

### Manual run stops at "Verify default branch"
- The run was started from a branch other than your default branch
- Start it again from **Run workflow** with the default branch selected

### Run fails with "latest.json was not updated by this sync"
- `sync.py` finished without writing `latest.json`
- Check that the `python sync.py` step in your workflow still passes `--output latest.json` (see [Customization](#customization)) and that the step's `env:` block still sets `ATHLETE_ID` and `INTERVALS_KEY`

### Run fails with "Generated data changed in the repository during this run"
- A generated file was changed, added or deleted in the repository while the run was in progress
- Nothing from that run was published; the next run syncs again from the updated repository

### Run fails with "The push was not accepted after 3 attempts"
- Read-back confirmed that no commit from this run is on the branch
- Check the log for a permission error (see [Step 4](#step-4-enable-workflow-permissions)), then run the workflow again

### Run stops with "OUTCOME UNKNOWN"
- A push did not report success and the workflow could not confirm whether it landed, so it did not retry
- Check the latest commit on your default branch. If it is this run's `Sync training data` commit, the data was published; otherwise run the workflow again

### Scheduled runs are late or missing
- GitHub runs schedules best-effort and can delay or drop them; use [Sync Now](#sync-now) when you need fresh data
- Check your Actions minutes (see [GitHub Actions minutes](#github-actions-minutes)); runs stop or incur charges once the allowance is used, depending on your settings
- In a public repository, GitHub disables scheduled workflows after 60 days without repository activity

### No data in latest.json
- Verify your Intervals.icu API key is valid
- Check you have activities in the last 7 days
- Look at workflow logs for specific errors

### ftp_history.json not updating on GitHub
- The file only changes when your indoor or outdoor FTP changes
- Use the current `auto-sync.yml`, which commits it together with the other generated files
- Check workflow logs for git errors

### history.json not generated
- History generates automatically on first run, then regenerates when outdated
- Delete `history.json` from your repo and re-run to force regeneration. Do this while no sync is running; a run already in progress fails without publishing and the next run regenerates it
- Check workflow logs. History generation is non-critical and won't fail the sync

### 404 error on JSON URL
- Ensure `latest.json` exists in repo root; check it in the repository's **Code** view
- **Private repository:** a plain `raw.githubusercontent.com` URL normally returns 404 when the request carries no GitHub authentication. This is expected, and being signed in to github.com in your browser does not make such a URL a reliable check. Use the **Code** view to check files, and a GitHub connector or the **training-data** artifact to give them to your AI (see [Usage with AI](#usage-with-ai))
- **Public repository:** verify the URL format (use `main` not `master`)
- For private repo access from AI platforms, see the [main README troubleshooting](../../README.md#troubleshooting)

For general AI platform issues (data not fetching, AI fabricating metrics, connector problems), see the [main README troubleshooting guide](../../README.md#troubleshooting).

---

## Customization

**Change sync frequency:**
Edit the `schedule` block in `auto-sync.yml`. For Default, Fast mode and hybrid schedules and their Actions usage, see [Sync Schedule and GitHub Actions Usage](#sync-schedule-and-github-actions-usage). For other schedules:
- Avoid minute `0`, the busiest time for GitHub scheduled workflows
- Every hour: `7 * * * *`
- Every 6 hours: `7 */6 * * *`
- Keep `workflow_dispatch:` so Sync Now keeps working, and check the monthly job count before committing

**Change data range:**
In the **Run sync** step, change only the `--days` value and keep the rest of the command:
```yaml
          python sync.py \
            --athlete-id "$ATHLETE_ID" \
            --intervals-key "$INTERVALS_KEY" \
            --days 14 \
            --output latest.json || {
              echo "❌ Sync script failed with exit code $?"
              exit 1
            }
```
Keep `--output latest.json`: without it, `sync.py` does not write `latest.json` and the run fails at the output check.

---

## Privacy Notes

The script does not anonymize your data. Only `metadata.athlete_id` is redacted; activity names, date of birth, sex, height, location, timezone, athlete notes, and route coordinates are passed through, and `saved_workouts.json` carries your saved workouts in full: their names, descriptions, folder names and complete structures, which reveal planning intent such as goal events, target adaptations and prescribed intensities. Publishing the repo publishes all of it. See [Privacy & Security](../../README.md#privacy--security).

Activity and event IDs are always real (opaque database keys, not PII) to enable features like coach annotations and planned-vs-actual pairing. Indoor/virtual ride names are preserved for workout identification.

For additional privacy, use a **private repository** and a separate GitHub account for your data repository.

GitHub Actions billing and repository visibility are separate questions. Billing concerns the runner minutes your workflows use. Visibility decides who can read your committed training data: a public repository does not use standard-runner minutes, but it publishes that data. The training-data artifact from a manual run stays behind your repository's access controls while GitHub stores it; for a public repository that means any signed-in GitHub user. Once you download the artifact or upload its files to an AI platform, that copy is handled under the recipient platform's terms and retention. Section 11 does not operate a hosted backend; your data moves only between Intervals.icu, GitHub and the services you choose.

---

## Files Reference

| File | Purpose | Auto-created |
|------|---------|--------------|
| `latest.json` | Current 7-day training data for AI consumption | Yes |
| `history.json` | Longitudinal data: daily (90d), weekly (180d), monthly (3y) | Yes |
| `intervals.json` | Per-interval segment data for recent structured sessions | Every sync (activity list may be empty) |
| `routes.json` | Route/terrain data for planned events with GPX/TCX attachments | Every sync (`events` may be `[]`) |
| `saved_workouts.json` | Read-only mirror of your Intervals.icu saved workouts | Every sync (own 6h refresh throttle) |
| `ftp_history.json` | FTP progression tracking for Benchmark Index | Yes |
| `archive/` | Daily snapshots of `latest.json` (`archive/YYYY-MM/YYYY-MM-DD.json`, UTC date, overwritten during the day) | Yes |

## Update Notifications

**This setup does not notify you of upstream updates.** Two separate mechanisms exist, and neither reaches you here. The one that opens a GitHub Issue runs only when `sync.py` publishes to GitHub itself, using a token and repository you have configured; this workflow deliberately avoids that path, invoking `sync.py` in output-only mode so the workflow does the committing. The other is a local notice that prints a single line during a sync run and creates no GitHub Issue or other notification artifact; it looks for a `section11/` directory beside your data, and a data mirror built from this guide has none. Nothing will appear in your Issues tab.

Staying current is manual, and the three files you copied in Step 2 are not updated the same way. Watching the [Section 11 repository](https://github.com/CrankAddict/section-11) will tell you that something changed, but it is not the update itself.

- **`sync.py`** is a verbatim copy. Compare it against the hash in the repository's `manifest.json` and replace it outright when it differs.
- **`.github/workflows/auto-sync.yml`** matches the published hash only while you have not changed it. If you changed its schedule or any other line, a hash mismatch is expected. When the template changes, do not replace your copy blindly: follow [Updating an Existing Repository](#updating-an-existing-repository) so you keep the customizations you want.
- **`README.md`** is not comparable that way. You replaced its placeholders during setup, and the workflow rewrites its **Last successful sync** line on every run, so it will always differ from the template. Read what changed in `DATA_REPO_README_TEMPLATE.md` and merge anything that applies into your own README by hand. Do not overwrite it from the template, and do not read a hash mismatch as an update.

For local setups (non-GitHub), see [json-local-sync](../json-local-sync/SETUP.md#staying-up-to-date) for the local update mechanism.

## Updating an Existing Repository

Use this sequence when the workflow template changes, including the change from the earlier 15-minute workflow to the current one.

> **Manual-only setup?** If you removed the `schedule` block so the workflow runs only when you trigger it, keep that choice: after replacing the workflow in step 3, remove `schedule:` again and keep `workflow_dispatch:`. See [On-Demand Sync](../json-on-demand/SETUP.md#updating-an-existing-repository).

1. **Record your current setup.** Note the `schedule` block in `.github/workflows/auto-sync.yml` and any other lines you changed, such as `--days`. If you used the earlier `*/15 * * * *` schedule, you were effectively running Fast mode; check [GitHub Actions minutes](#github-actions-minutes) before keeping that frequency.
2. **Choose a schedule:** Default, Fast mode or a hybrid. See [Sync Schedule and GitHub Actions Usage](#sync-schedule-and-github-actions-usage).
3. **Replace the workflow.** Replace the contents of `.github/workflows/auto-sync.yml` with the current `examples/json-auto-sync/auto-sync.yml`. Keep the filename: your README badge and Sync Now link depend on it.
4. **Reapply only what you still want.** Edit the `schedule` block for the schedule you chose, and reapply other recorded changes you still need. Do not copy back the old publishing steps.
5. **Keep your README.** Do not replace a customized `README.md` with the template. Keep its status badge line, its Sync Now link and its `**Last successful sync:**` line; merge any template wording you want by hand.
6. **Keep your secrets.** `ATHLETE_ID`, `INTERVALS_KEY`, `WEEK_START` and `ZONE_PREFERENCE` keep the same names; nothing needs to change.
7. **Run Sync Now** from the default branch and check that the run is green, that exactly one new `Sync training data` commit contains the updated data files, today's archive file and `README.md`, that the **training-data** artifact is on the run page, and that the README timestamp changed.
8. **Watch the next scheduled run** to confirm the new schedule starts.
9. **Optional:** delete old timestamped files under `archive/` in a normal commit, as described in [Archive](#archive). This changes the current tree only.

**Rollback:** restore the previous `.github/workflows/auto-sync.yml` from your repository's commit history (for example by reverting the commit that replaced it). Your data files, secrets and README are not affected. Archive files written by either version can stay side by side.

`sync.py` updates are separate from workflow updates; follow [Update Notifications](#update-notifications) for them.
