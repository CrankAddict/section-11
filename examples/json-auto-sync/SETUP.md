# GitHub Sync Setup Guide

GitHub sync keeps your Intervals.icu training files in your own private GitHub repository, a folder stored online. GitHub refreshes them, so your computer can be off. Your AI needs access to those files afterwards.

## Get help from your AI

You create the repository and enter secrets; your AI explains the steps. Copy this prompt:

```text
Help me set up Section 11 GitHub sync, one step at a time; I do the clicks and enter credentials.
Read this guide first: https://github.com/CrankAddict/section-11/blob/main/examples/json-auto-sync/SETUP.md (if you can open my installed section11/ folder, use its copy instead).
Keep my existing repository, data, schedule and settings; ask before changing anything.
```

For full guided setup, including your dossier and AI connection, give your AI this link: <https://github.com/CrankAddict/section-11/blob/main/SETUP_ASSISTANT.md>.

## Set up a new repository

1. In Intervals.icu **Settings**, find your Athlete ID near the bottom and your API key under **Developer Settings**.
2. At [github.com/new](https://github.com/new), create a **Private** repository such as `training-data`, leaving **Add a README file** unchecked. Click **Create repository**, not Fork.
3. Download `section11-YYYY.MM.DD-auto-sync.yml` from the [latest official release](https://github.com/CrankAddict/section-11/releases/latest). Wait if unavailable or `UNSEALED` ([workflow setup](#step-2-set-up-github-repository)).
4. In your repository, click **creating a new file** and name it `.github/workflows/auto-sync.yml`. Paste the downloaded contents, keep the defaults and commit.
5. Under **Settings > Secrets and variables > Actions > New repository secret**, add `ATHLETE_ID` and `INTERVALS_KEY` with your values.
6. If required, select **Read and write permissions** under **Settings > Actions > General > Workflow permissions** and save ([permissions](#step-4-enable-workflow-permissions)).
7. Open **Actions > Auto-Sync Intervals.icu Data > Run workflow**, enabling workflows if prompted. Keep the default branch and **Operation: Sync**, leave the checkbox unticked, then run it.
8. In **Code**, check for a successful `Sync training data` commit and a current timestamp in `latest.json`.
9. Connect your AI to the private repository and check it can read `latest.json` and `section11/`. Without a connector, on your repository page, press the green **Code** button and choose **Download ZIP**. Upload that ZIP to your AI ([AI access](#usage-with-ai)).

From now on, GitHub syncs about every 30 minutes. For fresh data right away, tap **Sync Now** in your repository's README, then **Run workflow**, and then **Run workflow** again.

Set up your AI with [Section 11's project instructions](../../README.md#3-configure-your-ai-platform).

A private repository uses your GitHub Actions minutes. The default schedule needs about 1,500 a month, more if runs take longer than a minute; GitHub Free includes 2,000. See [GitHub Actions minutes](#github-actions-minutes).

## Sync timer (optional)

GitHub's built-in schedule is unreliable for many users: scheduled syncs can start hours late or not at all. A free sync timer from cron-job.org or Cloudflare requests a sync every 30 minutes. We recommend it if your data is often out of date.

Requires workflow v11.105 or later (the first line of your `.github/workflows/auto-sync.yml`). A file without this line is older; see [version compatibility](#sync-timer-version-compatibility). Also check that **Sync timer** appears under **Run workflow > Operation**. If you skip this section, your setup continues as before. Check the [Actions minutes and token risk](#sync-timer-costs-and-token-access) before starting.

### Let the Sync timer run your syncs

In your data repository, open **Settings > Secrets and variables > Actions > Variables > New repository variable**. For **Name**, use:

```text
SECTION11_SYNC_TIMER
```

For **Value**, use:

```text
on
```

Save the variable, then set up one timer below. With this switch on, GitHub's own scheduled sync job is skipped before a runner starts. The timer replaces that schedule; there is no GitHub backup. Manual **Sync Now** still works. If the timer stops, the timestamp and delivery deadline in `latest.json` show that the data is late; they do not start a replacement run.

Scheduled runs still appear as **Skipped** in Actions while the switch is on; this is expected.

### Create a token once, then choose one timer

Open [GitHub's fine-grained token page](https://github.com/settings/personal-access-tokens/new). For **Token name**, use:

```text
Sync timer
```

Set **Resource owner** to the account that owns your data repository. Under **Repository access**, choose **Only select repositories** and select just that repository. Under **Repository permissions**, set **Actions** to **Read and write**, nothing else; Metadata read is added automatically. Choose an **Expiration** date and set your own reminder to replace the token before then.

Create the token and copy it for your chosen timer below. It can start any workflow in that repository, so use it only for the timer.

### Choice 1: cron-job.org

One web form, no code to paste; the simpler choice for a phone, but your token is stored at cron-job.org.

1. In your [cron-job.org](https://cron-job.org/) account, choose **Create cronjob**. For **Title**, use:

   ```text
   Sync timer
   ```

   For **URL**, paste this, replacing `OWNER` and `REPO` with your own data repository's owner and name, the same repository you limited the token to:

   ```text
   https://api.github.com/repos/OWNER/REPO/actions/workflows/auto-sync.yml/dispatches
   ```

2. Set the execution schedule to **Every 30 minutes**. In the **Advanced** tab, select **Request method: POST** and add these three headers:

   | Key | Value |
   | --- | --- |
   | Authorization | `Bearer ` followed by your token |
   | Accept | `application/vnd.github+json` |
   | Content-Type | `application/json` |

   The Authorization value starts with `Bearer` and a space, then your token.

3. Further down on the **Advanced** tab, below **Request method: POST**, find **Request body** and paste:

   ```json
   {"ref":"main","inputs":{"operation":"Sync timer"}}
   ```

   If your default branch has another name, replace `main` with that name. Keep only the shown input; unknown inputs are rejected with HTTP 422.

4. **Save**, then use **Test run**. HTTP **204** means GitHub accepted the start, not that the sync published. Follow [Check it works](#check-the-sync-timer-works) below. Failure notifications are optional.

To pause, disable or delete this cron-job.org job. Enable it again, or recreate it, to resume. To have GitHub's own schedule sync instead, also turn the repository variable off or delete it, as described below.

### Choice 2: Cloudflare

More steps, but the token stays in your own Cloudflare account as a Worker secret.

1. In Cloudflare **Workers & Pages**, create a Worker you own. Paste all of [sync-timer.js](sync-timer/sync-timer.js) from the [sync-timer folder](sync-timer/) into its dashboard editor and deploy it.
2. Open **Workers & Pages > Overview > your Worker > Settings > Variables and Secrets**. Use **Add**, type **Secret**, with this name and your GitHub token as its value:

   ```text
   GITHUB_TOKEN
   ```

   Add a text variable with this name:

   ```text
   GITHUB_REPOSITORY
   ```

   For its value, replace this with your data repository's owner and name, without a URL:

   ```text
   owner/name
   ```

   Only if your default branch is not `main`, add another text variable with this name and your default branch name as its value:

   ```text
   GITHUB_REF
   ```

3. Make sure **Observability (Workers Logs)** is on, so you can see runs and failures.
4. Under **Settings > Triggers > Cron Triggers**, add:

   ```text
   22,52 * * * *
   ```

   This requests a sync at 22 and 52 minutes past each hour, UTC. Cron changes can take up to 15 minutes to take effect.

To pause, delete the Cron Trigger; there is no disable switch. Add it again to resume. Keep the Worker and its settings. To have GitHub's own schedule sync instead, also turn the repository variable off or delete it, as described below.

### Check the sync timer works

Open your data repository's **Actions** tab. Find **Sync timer run**, with event **workflow_dispatch**, and check it finishes successfully. In **Code**, check that `latest.json` has a new timestamp. A started run is not a finished sync.

For Cloudflare, check **Observability (Workers Logs)** for runs and errors. Do not rely on the **Cron Events** list: it stayed empty during testing even when the Worker ran.

Never use **Disable workflow** in GitHub to pause the timer: it also stops the timer's requests and **Sync Now** from starting runs. Pause your chosen timer instead. See [timer troubleshooting](#timer-runs-but-nothing-publishes) if data does not update.

### Use GitHub's own schedule instead

Do both: pause the timer at cron-job.org or delete its Cloudflare Cron Trigger, and change the repository variable `SECTION11_SYNC_TIMER` to this value (or delete the variable):

```text
off
```

GitHub's existing schedule then runs again. To return to the Sync timer, set the variable to `on` and resume that timer. Keep the existing `schedule:` block in the workflow so this switch can restore it.

## Updates

When a new version is out, your AI mentions it. To install it, tap **Sync Now** in your repository's README, then **Run workflow**, set **Operation** to **Update**, and tap **Run workflow** again.

For automatic updates, open your repository on github.com and go to **Settings > Secrets and variables > Actions > Variables**. Add a variable named `SECTION11_AUTO_UPDATE` with the value `true`.

Already have a repository? See [updating an existing repository](#updating-an-existing-repository).

[Full technical guide on GitHub](#technical-guide)

# Technical guide

This guide explains how to create an automated JSON data mirror of your Intervals.icu training data for use with AI coaching systems.

> **Already using GitHub sync?** Follow [Move to the final hosted workflow](../maintenance/UPDATING.md#move-to-the-final-hosted-workflow). Keep your repository, literal cron lines, settings, secrets and data. An existing compatible installation stays in place in half mode until you choose Update.

> **Prefer an interactive guide?** Paste [SETUP_ASSISTANT.md](../../SETUP_ASSISTANT.md) into any AI chat and it will walk you through this entire setup step by step.

> **Running an agentic platform locally?** If your AI coach runs on the same machine as your data (OpenClaw, Claude Code, Cowork, etc.), consider [local sync](../json-local-sync/SETUP.md) instead (simpler setup, and no GitHub repository in the path). Where your data goes still depends on what you configure and which AI you point at it; see [Privacy & Security](../../README.md#privacy--security).

---

## Overview

The data mirror syncs your Intervals.icu metrics to a GitHub repository on a schedule, every 30 minutes by default, producing JSON files that AI systems can read through a GitHub connector or other authenticated repository access, or by URL for a public repository. GitHub runs scheduled workflows on a best-effort basis, so a scheduled sync can be late or skipped. For fresh data right after a workout, use [Sync Now](#sync-now). See [Sync Schedule and GitHub Actions Usage](#sync-schedule-and-github-actions-usage) before choosing a different schedule.

With the updated workflow, GitHub sync can use **4 Intervals.icu requests on a quiet cache-hit run instead of about 31**. Slow-cache reuse and the hosted per-run request controller apply to every schedule, including hourly, three-hour and hybrid schedules, and to Sync Now. First runs, scheduled refreshes, changed activities and misses cost more. Hourly, three-hour and hybrid schedules still have no known export delivery deadline; that does not disable cache reuse.

### Private state and request limits

The managed publisher commits `archive/carry-forward.state` with each export when its recovery content changes. The next runner reads it from the repository checkout. This compact backup protects previously exported summaries if latest.json is damaged; it does not add Intervals.icu requests. The producer and controller arrive together through the normal release and Update path, without replacing your workflow. Update and rollback preserve the file. It is excluded from AI companions and the training-data download; AI tools must ignore it and read only `latest.json.carry_forward` for recovery notices. Repository-wide connectors can still expose it physically. It is separate from request state and the Actions cache below.

Each run creates private request accounting and source state in the runner's `<data folder>/state/`. The workflow retains only profile settings, aggregate curves and current-window messages in a separate plain Actions cache under runner temporary storage. It never commits the cache or includes it in the training-data download or published outputs. Raw activities, wellness, calendar and health responses, native payloads and request accounting are not cached remotely. The AI uses the training files and `latest.json.source_freshness`, never `state/` or Actions caches. See [state locations and SECTION11_STATE_DIR](../json-local-sync/SETUP.md#private-sync-state).

In a public repository, someone who deliberately opens a pull request can read the workflow cache: full power/HR curves, sport/zone settings, profile details (location, birth date, sex, height, weight and resting-HR fallbacks, and profile notes), and recent activity-note text. Most of this also appears in the published training files; the cache never holds keys, credentials, raw activities, wellness or health events.

GitHub deletes caches unused for 7 days, so rarely run On-demand gains little; a cache miss just means normal reads.

Intervals.icu allows 8,000 requests per key per UTC day and 2,500 per 15 minutes. Hosted runs keep per-run limits, pacing and provider holds, but have no daily balance, step-down or budget pause. The local `check_interval_minutes` setting does not change hosted runs. Counts cover this invocation, not earlier runners or other tools using the key. The local/manual daily controller is unchanged. These limits are separate from GitHub Actions minutes below.

We recommend one setup per user. Stop the old timer or workflow before changing the sync path or moving machines, to protect Intervals.icu. Counts are per data folder, API key and athlete, with no coordination across folders.

**Result:** these files in your repository, shown here as raw URL patterns. Plain raw URLs work without GitHub authentication only for a public repository; for a private repository, see [Step 6](#step-6-verify) and [Usage with AI](#usage-with-ai).
- `https://raw.githubusercontent.com/[you]/[repo]/main/latest.json`
- `https://raw.githubusercontent.com/[you]/[repo]/main/history.json`
- `https://raw.githubusercontent.com/[you]/[repo]/main/ftp_history.json`
- `https://raw.githubusercontent.com/[you]/[repo]/main/intervals.json`
- `https://raw.githubusercontent.com/[you]/[repo]/main/routes.json` (always written; route entries only for planned events with GPX/TCX attachments)
- `https://raw.githubusercontent.com/[you]/[repo]/main/saved_workouts.json`

---

## Prerequisites

**Existing repositories:** follow the [migration steps](#updating-an-existing-repository).
Keep every literal cron and optional environment setting in the replacement
workflow. The verified latest runtime checks the application before any installation;
the controller retains cache staging, restore and changed-only save after
confirmed publication. No new secret is needed.

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
3. Set to **Private**. See the [connector table](../../README.md#platform-setup) for platform support. A public repository runs free but publishes your training data; see [Public repositories](#public-repositories).
4. Leave **Add a README file** unchecked. The first Sync installs the standard README with your Sync Now link; successful syncs update its timestamp.
5. Click **Create repository**

Use the published [scheduled workflow](auto-sync.yml), or the exact
`section11-YYYY.MM.DD-auto-sync.yml` asset on the matching
[official release](https://github.com/CrankAddict/section-11/releases/latest).
The detached asset is verified byte-for-byte against the release manifest. Use a
release that supports the final workflow, with **Other** and the first-adoption
checkbox. Do not substitute raw-main code. **Old templates only:** `UNSEALED`
means the template is not ready to use; never invent its pins. An existing old
workflow continues unchanged until you replace it. You do not upload a release ZIP.

1. In GitHub, create or edit `.github/workflows/auto-sync.yml`.
2. Replace its contents with the published scheduled template. Existing users
   retain every literal cron and optional setting, including `SECTION11_DAYS`.
   Fresh users keep the supplied default.
3. If the repository already has Section 11 files, read this warning immediately
   before committing. Brand-new repositories can skip this warning:

   > Anything you added or changed inside section11/ will be deleted. Move what you want to keep to custom/ first.

   Any existing root `sync.py`, `push.py` and `pull.py` will be removed. Outside
   `section11/`, this applies to any file in any folder named exactly like a
   release or historical Section 11 file, except the [keep list](../maintenance/UPDATING.md#local-updates-and-automatic-toggle).
   Protection ignores case; removal requires exact spelling. Keep your own files
   in `custom/` or outside the data repository. Existing data, settings,
   custom files and the private dossier are preserved. Git history is the rollback
   record; restoring a pre-adoption layout also requires owner workflow recovery.
4. If you use hosted workout push, also replace `.github/workflows/push-workout.yml`
   with the [thin push stub](../agentic/push-workout.yml) before committing. Use
   GitHub's web editor (`github.dev`, opened with `.` from the repository), edit
   both files, then stage and commit both together through Source Control.
   Commit the workflow replacement through your repository's normal policy,
   **before the first Sync**.

That commit accepts first installation. The first Sync run writes the complete
verified `section11/`, its receipt and missing custom guidance in one direct
commit, then publishes training data separately. No manual folder creation or
additional updater/validator workflow is required. The standard README includes
your repository's Sync Now link.

The push stub keeps its filename, dispatch inputs and preview/confirm behavior;
it calls `section11/examples/agentic/push.py`. Update external root-tool imports
to the managed paths. Until the first Sync installs Section 11, push stops with:
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

### Optional route-weather variables

In your data repository, open **Settings > Secrets and variables > Actions > Variables**, then **New repository variable**. The supplied workflow passes these optional values to sync.py:

| Repository variable | Value and default |
|---|---|
| `SECTION11_ROUTE_WEATHER` | `0` disables route weather; absent/empty keeps it on |
| `SECTION11_ROUTE_WEATHER_DEFAULT_START` | Local HH:MM such as `09:30`; absent/empty uses `10:00` |

These are preferences, not credentials. No variables are required for the defaults. An invalid nonempty start leaves assumed-departure weather unavailable; it does not guess another time. Changes take effect on the next scheduled run or Sync Now. Local/Manual users can instead set the existing config or process environment. See [departure handling](../../README.md#route-weather-departure).

---

## Step 4: Enable Workflow Permissions

The workflow needs effective `contents: write` and read access to Actions run
metadata. If repository policy requires it, select **Read and write permissions**
under **Settings > Actions > General > Workflow permissions**, then save.
No PR-creation/approval setting or privileged personal token is needed.

A protected branch can prohibit direct commits even with those permissions.
A refusal stops without retry, force or policy bypass. Ask the repository owner
for a policy-compatible route; changing tokens is not an automatic workaround.

---

## Step 5: Enable GitHub Actions

1. Go to your repo → **Actions** tab
2. If prompted, enable workflows
3. Click on "Auto-Sync Intervals.icu Data" workflow
4. Click **Run workflow** → **Run workflow** (green button)

Confirm that **Auto-Sync Intervals.icu Data** appears in Actions. If it is missing,
check the YAML and registration on the default branch before requesting a run.
The presence of a workflow file alone is not proof that GitHub registered it.

Leave the branch selector on your default branch (normally `main`). A manual run started from any other branch stops at its first step without syncing.

Wait 30-60 seconds, then check if `latest.json` has been updated. This manual run is the same [Sync Now](#sync-now) you can use at any time.

If the run fails with a permission error, go back and check that workflow permissions are set to "Read and write" in Step 4.

---

## Step 6: Verify

Check the result in your repository's normal **Code** view on github.com:

1. Confirm that the latest commit is a new `Sync training data` commit
2. Open `latest.json` and check that `metadata.last_updated` changed to the time of this sync
3. Open `history.json`, `ftp_history.json`, `intervals.json`, `routes.json`, `saved_workouts.json` and `route_eta_history.json` to confirm they are there

On the first run, also inspect the preceding installation commit: complete
`section11/` and receipt, missing custom guidance created, and root `sync.py`,
`push.py`, `pull.py` and other unprotected exact-name copies removed in any folder.
The workflow confirms remote commit/tree readback.
No PR or merge is required. Use **Operation: Status** for an optional update plan.

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
- `latest.json.source_freshness`: source status (`fresh`, `stale`, `deferred`, `unavailable`), acquisition age and coverage, plus the hosted per-run request count, source schedule and warnings. Null age means unknown. A new export timestamp does not make a retained source fresh. See the [field reference](../json-examples/README.md#source-freshness).
- `latest.json.sleep_context`: uses a 35-date wellness window (D−34..D), while existing baselines/reports retain their original 28-date slice. This is low-confidence context only, never readiness. No separate sleep file or history refresh is needed. The existing workflow carries it inside latest.json, including the manual-run download artifact. The AI discovers it through `READ_THIS_FIRST.sleep_context_note`. Missing dates, unknown athlete timezone or current-date mismatch remain explicit unavailable states. Retained wellness keeps its acquisition time in `source_updated_at` and its refresh status in `source_freshness`; without a usable required snapshot, the previous export is preserved. Existing archive and Git-history retention still apply to the whole export.
- `history.json`: longitudinal data with tiered granularity: daily (90 days), weekly (180 days), and monthly (up to 3 years). Generated automatically on first run, regenerated when outdated.
- `intervals.json`: interval/DFA payloads and completed-session structure detail (14-day retention). Written on every successful sync. `has_structure` in latest.json identifies available detail; the compact `interval_data.plan_match` survives detail expiry through the 28-day recent-activity window. These committed JSON files retain the activity-detail cache needed by auto-sync; private request/source state is separate and is not persisted by the workflow. See [Which interval data to use](../../SECTION_11.md#which-interval-data-to-use).
- `routes.json`: route/terrain data for planned events with GPX/TCX attachments. Includes climb/descent detection, course character, and polyline. Written on every successful sync, with `"events": []` when no planned event has an applicable attachment. Parsed routes are cached by attachment ID.
- `route_eta_history.json`: rolling 180-day outdoor ride facts for personal route ETA calibration. The workflow validates it when present and commits it with the other generated data, so the next Actions checkout retains the record. Keep it across releases. It is not included in the downloadable training-data artifact; the current ETA result is already in the route brief. On-demand uses this same workflow with the schedule removed.
- `saved_workouts.json`: read-only mirror of your Intervals.icu saved workouts, with folders and complete workout definitions. Refreshed on its own 6-hour throttle rather than every sync, and the last good copy is kept when a refresh fails.

---

## Sync Schedule and GitHub Actions Usage

### Sync Now

**Sync Now is the way to get fresh data right after a workout.** Scheduled syncs are best-effort and can arrive up to a full interval later, or not at all.

1. Open your data repository and tap **🔄 Sync Now** in its README, or go to **Actions → Auto-Sync Intervals.icu Data**
2. Click **Run workflow**, keep your default branch selected, and confirm
3. When the run completes, the new data is committed to the repository

A manual run also uploads the generated JSON files as a **training-data** artifact on the run page, kept for seven days, for uploading to an AI chat. Sync Now requests a run; it does not guarantee that the run starts at once. All syncs share one queue, so if another sync is already running or waiting, your run waits its turn and can start later. GitHub does not guarantee the order of waiting runs. Each manual run counts toward your GitHub Actions minutes like any other run.

### Default schedule

```yaml
- cron: '7,37 * * * *'
```

- Checks every 30 minutes, at 7 and 37 minutes past each hour (UTC)
- The offsets avoid the start of the hour, which GitHub documents as its busiest time for scheduled workflows
- When GitHub runs the schedule on time, new data in Intervals.icu waits on average 15 minutes, and at most 30 minutes, for the next scheduled sync
- GitHub can still delay or drop scheduled runs, so Sync Now remains the way to request a sync when you need one

### GitHub Actions minutes

In a private repository, every run uses your account's GitHub Actions minutes. GitHub rounds each job up to a whole minute, so a sync that finishes in under a minute still counts as one billed minute. The monthly allowance for standard runners is 2,000 minutes on GitHub Free and 3,000 minutes on GitHub Pro and Team, shared by all private-repository workflows in your account. See [GitHub's billing documentation](https://docs.github.com/en/billing/concepts/product-billing/github-actions) for current figures. What happens after the allowance is used depends on your account's payment and budget settings.

Estimates below count scheduled jobs in a 31-day month with every scheduled run executed, assuming each job uses one billed minute. They are not a true worst case: a job that runs longer than a minute, such as a first sync that builds `history.json`, uses more, and Sync Now runs, failed runs, re-runs and other workflows come on top.

| Schedule | Jobs per day | Jobs in 31 days | GitHub Free (2,000) | Pro or Team (3,000) |
|----------|-------------:|----------------:|---------------------|---------------------|
| Default, every 30 minutes | 48 | 1,488 | 512 minutes left | 1,512 minutes left |
| Fast mode, every 15 minutes | 96 | 2,976 | Exceeds the allowance by 976 | 24 minutes left |

- The minutes left must also cover Sync Now runs, failed runs, re-runs and any other workflows in your account, such as `push-workout.yml`
- GitHub sometimes delays or skips scheduled runs, so real usage can be lower. Do not rely on that: budget for the full count
- If you do not know your plan, assume GitHub Free

### Sync timer costs and token access

The [optional Sync timer](#sync-timer-optional) calls the compatible `auto-sync.yml` workflow through `workflow_dispatch`, with `operation=Sync timer`. With `SECTION11_SYNC_TIMER=on`, a job-level condition skips native scheduled syncs before runner allocation, so those skipped jobs use no billed runner minutes. Manual runs and timer runs are unaffected by this switch. GitHub compares the value without case sensitivity; unset or values other than `on` keep native scheduled syncs enabled.

At one billed minute per run, a 30-minute timer uses about **1,488 Actions minutes per 31-day month** in a private repository, about the same as today's default 30-minute native schedule. There are no duplicate native syncs while the switch is on. Longer jobs, retries, manual starts and other workflows add more. Watch your account's Actions usage and budget. Standard GitHub-hosted runners are free in public repositories, including timer runs, but the [privacy costs](#public-repositories) remain.

The timer uses the existing hosted cache and per-run request controller. An outdated existing `history.json` is eligible for automatic refresh only on run numbers divisible by 16, with the same retry backoff as native scheduled syncs. Missing/unreadable history still takes the existing first-run path. Manual Sync Now remains exempt from the run-number limit, but still respects backoff. No timer state file is added.

The timer's export freshness uses a fixed 30-minute interval and the existing hosted grace of twice that interval plus one hour: normally `expected_update_by` is two hours after `generated_at`. A provider hold can extend it. If you change the external timer's cadence, this freshness expectation still assumes 30 minutes. With the switch on there is no native backup: a stopped timer leaves the last timestamp and deadline unchanged, making lateness visible to the AI. Its `export_freshness.mode` should be `hosted_scheduled`, with a populated `expected_update_by` deadline; manual **Sync Now** stays `on_demand`.

**The token is not start-only.** Actions read and write lets it start any workflow in the selected repository. That includes **Update** and **Rollback**, and, if installed, workout push with `confirm=true`, which can create, move or delete workouts and change thresholds using the repository's stored Intervals.icu credentials. The timer sends only Sync timer, but its token has that broader authority. Use a dedicated token for only the data repository; give neither timer your Intervals.icu API key.

Sync timer runs skip the **training-data** download artifact. Manual Sync Now still uploads it for **7 days** after successful data validation, even if publication later fails, preserving the On-demand download path. The token's Actions read access includes existing and manual-run artifacts. They stay behind repository access controls; in a public repository, any signed-in GitHub user can download them. The artifact is a separate copy from the committed training data.

cron-job.org stores the token at its service. Cloudflare stores it as a secret in your own Worker account. Choose an expiry and set your own reminder to replace the token in the chosen timer before it expires. GitHub's 2021-07-26 changelog says it emails before token expiry, but that announcement was written for classic tokens, not separately confirmed for fine-grained tokens. Treat any email as a possible extra reminder, not a guarantee.

### Sync timer version compatibility

Requires workflow v11.105 or later, with Section 11 v11.105 / sync.py v3.168 or later. **Update** replaces the managed source, not `.github/workflows/auto-sync.yml`.

For an existing repository, choose **Operation: Update** and verify it completes, then replace the owner-controlled wrapper using [Updating an Existing Repository](#updating-an-existing-repository), keeping every literal cron, optional setting and secret name. If the old workflow has no Operation menu, follow those installation steps first. Confirm **Sync timer** appears in the new menu before enabling the variable and timer. New repositories use the matching published workflow from initial setup. Only use it after the compatible release is available.

An old wrapper with new source keeps normal native and manual sync behavior, but cannot provide the timer switch, run name or artifact exclusion. A Sync timer request against an old choice list is expected to return HTTP 422. A new wrapper with old trusted source rejects the unknown operation before producing data; having the new menu alone is insufficient. New wrapper and new source provide all timer behavior. Local sync, GitHub sync without a timer, On-demand manual Sync Now and Manual export remain unchanged.

### Public repositories

We recommend a private repository, but a public one has real advantages:
- **No Actions minutes:** standard GitHub-hosted runners are free in public repositories. Default, Fast mode, hybrid schedules and Sync Now cost nothing and need no budgeting.
- **No connector needed:** plain raw URLs work in any AI chat that can fetch a URL, without authentication or file uploads. See [Usage with AI](#usage-with-ai).

The costs:
- **Everything committed is public:** activity names, date of birth, location, route coordinates, notes and your saved workouts in full. See [Privacy Notes](#privacy-notes). Someone who opens a pull request can also read the workflow cache; see [Private state and request limits](#private-state-and-request-limits).
- **Intervals.icu limits still apply:** free minutes do not raise them, and hosted runs have no daily allowance controller. Fast mode is the fastest schedule this guide covers.
- **Inactivity:** GitHub disables scheduled workflows in a public repository after 60 days without repository activity; see [Scheduled runs are late or missing](#scheduled-runs-are-late-or-missing).

### Fast mode

```yaml
- cron: '7,22,37,52 * * * *'
```

Fast mode checks every 15 minutes, all day. It is **not suitable for GitHub Free** unless you have intentionally set up paid usage beyond the allowance, and it uses almost all of a Pro or Team allowance before any manual runs or other workflows. In a public repository it uses no minutes; see [Public repositories](#public-repositories).

### Advanced hybrid schedules

A hybrid schedule checks more often during an active window that you set in UTC, and hourly otherwise. It uses two ordinary cron lines, which GitHub reads in UTC like the Default and Fast schedules. Do not add a `timezone:` line to either entry: Section 11 does not rely on it, because in testing an entry with `timezone:` ran as if its hours were in UTC. Sync Now remains the way to request fresh data when you need it.

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
monthly estimate = jobs/day × 31, at one billed minute per job
minutes left = allowance − monthly estimate
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

Date-only/exact-midnight workouts use labelled 10:00 local by default. Choose another default through the [optional repository variables](#optional-route-weather-variables); strict local HH:MM is required. No setting is needed for the default. The AI asks for the real time or asks you to set it on the workout. New points/hours for the changed departure can fetch on the next sync without waiting for the normal refresh gate, subject to request limits and failure/provider backoff. See [departure handling](../../README.md#route-weather-departure). `data_overview` is directly after READ_THIS_FIRST, or first when absent; outlook directions are compact labels.

The workflow file binds triggers, actions and secrets; verified managed code
implements the operation. In outline:

- **Runtime and application:** each run selects and verifies the latest official
  runtime. Half mode keeps the installed application until you choose Update.
  Verification failure stops the run; the next run selects again.
- **Operations:** Sync, Update, Status, Rollback and Sync timer, plus Other and its
  text field for operations added by later releases. Unknown operations stop safely.
  Use the first-adoption checkbox only for the first Sync after moving over.
- **Update allowance:** data sync still runs when automatic application maintenance
  is deferred because another run was active or finished within ten minutes.
  Both update modes share this allowance; completed skipped runs do not count.
- **Actions:** checkout, setup-python, cache and upload-artifact retain full commit pins.
- **Permissions:** effective `contents: write` and Actions-run read access are needed.
- **One writer at a time:** sync, update and rollback share a queue without cancelling
  active work. Other publishers can still race; an observed-tip change stops this run.
- **Time limit:** the wrapper allows 30 minutes, including first-run history creation.
  Queuing and provider delays mean this is not a freshness promise.
- **Default branch only:** another branch stops before athlete credentials or a producer run.
- **Credentials:** the producer receives masked athlete/key arguments as literal values,
  with no GitHub publication token or persisted checkout credentials.
- **Output checks:** rewritten `latest.json` and declared JSON/PNG outputs are checked for
  paths, type, size, JSON validity and PNG signature/IHDR. Invalid declarations use
  the fixed validated JSON fallback without deletion; invalid fallback data stops.
- **Download:** a manual run retains the six-JSON artifact after successful validation,
  even if later publication or maintenance fails. It excludes maps, ETA history and state.
- **Data commit:** generated files, UTC archive and normal README timestamp form one
  separately validated child of the observed default tip. Installations and changed
  update notices use separate commits; there is no check-only commit. This data commit preserves personal files and changes
  only the README timestamp.
- **Outcome:** one non-forced ref write is followed by commit/tree readback, even after
  a lost response. Confirmed presence is reported. An unknown outcome, denial or
  competing commit stops without retry or rebase. Confirmed history plus a later
  default advance reports both facts and requires inspection.

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

**Calendar naming:** To let the calendar support a deload week, name its sessions with "Deload" or "Recovery week", for example "Recovery week - easy ride". Single recovery rides inside normal weeks are not read as a deload week. Names support the phase assessment; they do not establish it on their own.

Once set up, configure your AI platform using the instructions in the [main README](../../README.md#web-chat-setup).

**Private repository with a GitHub connector or authenticated repository access (recommended):** Connect your own data repo and ask the AI to read the files by path: `latest.json`, `history.json`, `intervals.json`, `routes.json` and `saved_workouts.json`, plus `ftp_history.json` when needed. No raw URLs are needed. Refresh, sync or re-import when your platform requires it; see the [connector table](../../README.md#platform-setup). Check that the connection also exposes the installed `section11/` protocol and templates. Keep the optional dossier as `DOSSIER.md` in the repository root. Keep any repository containing it private; Git keeps old versions. Web-chat uploads are delivery copies.

A GitHub connector is normally read-only. Where its write access is unavailable or unverified, your AI cannot update `DOSSIER.md` in place: it returns the revised dossier as an artifact and says plainly that the source was not updated. You then commit that file over the official `DOSSIER.md`, or replace the official copy with it, as would a repository writer whose access you have verified separately. Nothing in the automated pipeline does this for you. The data publication commit contains only generated data and the repository README. Installation and maintenance control use separate commits for `section11/`, outside copies selected by the [shared name rule](../maintenance/UPDATING.md#local-updates-and-automatic-toggle), the standard README, missing custom guidance and `.section11-update.json`. None of these commits changes your dossier.

**Public repository with URL fetch:** Use this only if your data repository is public. Everything committed to it, including your training data, is then readable by anyone (see [Privacy Notes](#privacy-notes)). Provide these URLs to your AI coach:
```
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/latest.json
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/history.json
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/ftp_history.json
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/intervals.json
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/routes.json
https://raw.githubusercontent.com/[your-username]/[repo-name]/main/saved_workouts.json
```

**When connector or link access is unavailable:** Use a connector or a link to
your own repository first. If the chat can use neither, run [Sync Now](#sync-now),
open your repository's **Code > Download ZIP**, and give that ZIP to the chat or
project. It includes the installed `section11/` files and data. Plain raw URLs
will not work for a private repository. An uploaded ZIP is a snapshot; re-upload
for fresh data and after updates, replacing the previous upload.

`latest.json` has the current 7-day snapshot, `history.json` provides longitudinal context for trend analysis, `intervals.json` has interval/DFA and completed-session detail, `routes.json` has route/terrain data for planned events with GPX/TCX attachments (its `events` list is empty when there are none), and `saved_workouts.json` mirrors your Intervals.icu saved workouts.

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
- Check that the workflow uses its verified hosted controller and still binds `ATHLETE_ID` and `INTERVALS_KEY`. The controller selects local output before validated publication.

### Run stops because the default tip changed

Another data, code, custom or workflow commit arrived during this run. The
controller does not overwrite it, force or rebase. Start a fresh run only after
checking the log's publication outcome.

### Run stops with an unknown publication outcome

A request may have landed even if its response was lost. Inspect the exact
commit named in the log in default-branch history, including ancestors of later
commits. An unknown result is not proof of failure. Do not blindly retry.
A confirmed commit followed by later changes is reported separately.

### Scheduled runs are late or missing
- GitHub runs schedules best-effort and can delay or drop them; use [Sync Now](#sync-now) when you need fresh data
- If this happens often, we recommend the [optional sync timer](#sync-timer-optional)
- Check your Actions minutes (see [GitHub Actions minutes](#github-actions-minutes)); runs stop or incur charges once the allowance is used, depending on your settings
- In a public repository, GitHub disables scheduled workflows after 60 days without repository activity

### Timer runs but nothing publishes
- HTTP 204 confirms only that GitHub accepted the start. Open **Sync timer run** in GitHub Actions and check its logs and publication outcome, then check the timestamp in `latest.json`
- If no run appears, check the timer's failure details and that the workflow is enabled. For Cloudflare, use **Observability (Workers Logs)**, not Cron Events
- Pause the timer on repeated failures and resolve the cause before resuming

### Timer reports HTTP 422
- In cron-job.org, open the **Test run** result and read GitHub's response text for the reason
- An empty or wrong request body causes 422. Paste the body shown above into **Request body** on the **Advanced** tab, below **Request method: POST**, and use your default branch name
- The operation must be exactly `Sync timer`: it is case-sensitive, with a capital S, lowercase t and no trailing space
- A workflow older than v11.105 has no **Sync timer** choice and rejects it with 422; follow [version compatibility](#sync-timer-version-compatibility)
- Undeclared inputs or an invalid ref can also cause rejection

### Nothing syncs after pausing the timer
- To have GitHub's own schedule sync instead, do both: pause the external timer and set `SECTION11_SYNC_TIMER` to `off` or delete the variable. Leaving it on still skips native scheduled jobs
- Keep the workflow enabled and its existing `schedule:` block. Use **Sync Now** for an immediate manual request; native schedules can still be delayed

### Sync timer run fails with "unknown workflow operation"
- The new wrapper is using older trusted source. Check the [version requirement and release installation](#sync-timer-version-compatibility); the Operation menu alone does not prove the managed source is compatible

### Cloudflare shows "Sync timer: HTTP 404"
- Check `GITHUB_REPOSITORY` is the data repository's exact `owner/name`
- Check the token was created for this exact repository under **Only select repositories**; an expired, revoked or deleted token shows [HTTP 401](#timer-reports-http-401) instead

### Timer reports HTTP 401
- The token may be expired or revoked. Replace it in the chosen timer using the same repository access and permissions

### No data in latest.json
- Verify your Intervals.icu API key is valid
- Check you have activities in the last 7 days
- Look at workflow logs for specific errors

### Request allowance, provider holds or stale sources

Read the sync log and `latest.json.source_freshness` if an export was written. Check other runs, machines and tools using the same key before triggering more runs; the runner's local count is not a key-wide daily total. Wait out any provider hold. The [local troubleshooting guide](../json-local-sync/SETUP.md#request-allowance-and-pauses) gives the exact pause message and private-state error explanation. GitHub keeps its configured workflow schedule; it does not gain a persistent one-minute local scheduler.

### ftp_history.json not updating on GitHub
- The file only changes when your indoor or outdoor FTP changes
- Use the current `auto-sync.yml`, which commits it together with the other generated files
- Check workflow logs for git errors

### history.json not generated
- History generates automatically on first run, then regenerates when outdated
- Native scheduled runs and Sync timer runs refresh an outdated `history.json` only when the run's number is a multiple of 16. Other scheduled runs skip the refresh, sync everything else normally and say so in the log. The refresh can therefore arrive several hours after the file becomes outdated, and later if those runs are delayed, cancelled or fail
- **Sync Now** skips only that limit. It refreshes an outdated file unless an earlier failed refresh is still waiting out its retry delay, and it does nothing to a file that is not outdated
- Delete `history.json` from your repo and re-run to force regeneration. Do this while no sync is running; a run already in progress fails without publishing and the next run regenerates it
- Check workflow logs. History generation is non-critical and won't fail the sync

### 404 error on JSON URL
- Ensure `latest.json` exists in repo root; check it in the repository's **Code** view
- **Private repository:** a plain `raw.githubusercontent.com` URL normally returns 404 when the request carries no GitHub authentication. This is expected, and being signed in to github.com in your browser does not make such a URL a reliable check. Use the **Code** view to check files, and follow [Usage with AI](#usage-with-ai) for connector or repository ZIP delivery
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
In the **Run sync** step's `env:` block, change `SECTION11_DAYS` (integer 1 to
365). Keep the launcher command unchanged:
```yaml
          SECTION11_DAYS: '14'
```
The launcher writes `latest.json` for the validated data publisher.

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
| `route_eta_history.json` | Persistent 180-day outdoor ride facts for route ETA calibration; repository state, not download artifact | Every sync |
| `archive/` | Daily snapshots of `latest.json` (`archive/YYYY-MM/YYYY-MM-DD.json`, UTC date, overwritten during the day) | Yes |

## Update Notifications

Active workflows are owner-controlled copies outside `section11/`.
**`README.md`** is not comparable by template hash. See
[Owner-controlled workflow maintenance](#owner-controlled-workflow-maintenance)
and [workflow compatibility](../maintenance/UPDATING.md#workflow-compatibility).
For local setups, use [local update guidance](../json-local-sync/SETUP.md#staying-up-to-date);
its automatic toggle never enables automatic GitHub updates.

Half mode is the default: Actions reports a verified release, and the next data
export carries a fixed, privacy-safe `update_notice` until it is resolved. Choose
**Operation: Update** in this same workflow and dispatch once to install it.
**Status** only shows the plan; **Rollback** restores the previous installation.
There is no PR or merge step. For automatic installation set
`SECTION11_AUTO_UPDATE=true` under **Settings > Secrets and variables > Actions >
Variables**. Both modes check after data work, subject to the ten-minute run
allowance. Runtime verification still happens on each run; it does not install a
newer application. A later good official release fixes a broken runtime, which can
also block Rollback; Rollback is for a bad application release.

**Old workflow (v11.105 only):** daily hosted maintenance from 04:00 UTC remains
until you follow the [move-over instructions](../maintenance/UPDATING.md#move-to-the-final-hosted-workflow).

See [updates and recovery](../maintenance/UPDATING.md#github-installation-and-updates)
for full mode, conservative deferral, `.section11-update.json`, rollback and owner
recovery.

## Keeping Section 11 current

### Updating an existing repository

Follow [Move to the final hosted workflow](../maintenance/UPDATING.md#move-to-the-final-hosted-workflow)
once a supporting official release is available. It covers preserving your cron
and settings, the first Sync checkbox, log checks and going back. For older
root-tool setups, [Step 2](#step-2-set-up-github-repository) also covers replacing
both stubs in the same owner commit, before the first Sync.

### Owner-controlled workflow maintenance

The stable workflow contains triggers, action/runtime bindings, permissions,
secret/variable bindings and a fixed verification gate. The latest verified official
runtime supplies workflow logic on every run; `section11/` holds the installed
application. Routine releases do not require another workflow edit.
Future incompatible workflow/runtime changes remain owner-controlled. Preserve
the current cron and settings when applying a published replacement.

The publisher retains the sync-declared JSON/PNG list and stale-file deletion rules.
Publication rules allow up to 128 ordinary JSON/PNG files, 64 MiB each, with relative paths up to 240 characters, no hidden components, traversal or symlinks.
JSON must parse; PNG signature and IHDR fields/CRC must validate.
Paths that dropped from a valid prior declaration are the only deletion candidates; unrelated repository files remain.
All companions are relative to the folder holding latest.json. A missing/invalid
current declaration uses the fixed seven-JSON fallback and disables
declaration-based deletion. Invalid fallback data stops publication.

Maps and `route_eta_history.json` remain in the repository, outside the unchanged
six-JSON download artifact. Renderer pages retain the existing four-pages-per-ride
and six-rides bounds. Source timestamps, private request accounting and native
cache semantics are unchanged. Slow-cache saving requires changed allowed
projection bytes and confirmed data publication.

Install, update and rollback refresh the standard README while retaining its sync timestamp; Sync changes only that timestamp between updates.
See the [update guide](../maintenance/UPDATING.md). Secrets retain the names `ATHLETE_ID`,
`INTERVALS_KEY`, `WEEK_START` and `ZONE_PREFERENCE`.
**Keep your secrets.** Archive files written by either version can stay side by side.

For On-demand, use its [dispatch-only template](../json-on-demand/auto-sync.yml).
It contains no schedule.
