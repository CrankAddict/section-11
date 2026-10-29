<!-- 
  DATA REPO README TEMPLATE
  
  Replace these placeholders:
    YOUR_GITHUB_USER  → your GitHub username
    YOUR_REPO_NAME    → your repository name
  
  Then delete this comment block.
-->

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

# Training Data Pipeline

`interval_data.plan_match` supplies timeline labels; `interval_data.compliance` summarizes gated Section 11 evidence from session_structure; `interval_data.icu_detected` is descriptive only. See [Which interval data to use](https://github.com/CrankAddict/section-11/blob/main/SECTION_11.md#which-interval-data-to-use).

![Sync Status](https://github.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/actions/workflows/auto-sync.yml/badge.svg)

**Last successful sync:** _updated automatically_

Automated training data pipeline from [Intervals.icu](https://intervals.icu) for AI coaching analysis.
Built on the [Section 11 Protocol](https://github.com/CrankAddict/section-11).

## Sync Now

[🔄 Sync Now](../../actions/workflows/auto-sync.yml): tap **Run workflow** (keep the default branch selected) to request a fresh sync, for example after a workout. If another sync is already running or queued, your run waits its turn. When the run completes, the new data is committed here, and the **training-data** artifact ZIP on the run page can be downloaded for seven days.

## Data URLs

| File | Description | Link |
|------|-------------|------|
| `latest.json` | Current 7-day snapshot + derived metrics + 28-day structure summaries + terrain & weather summaries | [View](https://github.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/blob/main/latest.json) |
| `history.json` | Longitudinal data (daily/weekly/monthly) | [View](https://github.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/blob/main/history.json) |
| `intervals.json` | Interval/DFA and completed-session structure detail (14 days) | [View](https://github.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/blob/main/intervals.json) |
| `routes.json` | Route/terrain data, route weather, forecast bands and map metadata for planned events with GPX/TCX attachments (`events` is empty when there are none) | [View](https://github.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/blob/main/routes.json) |
| `maps/weather/` | Private route weather PNG pages, bound to the matching brief in routes.json | [View](https://github.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/tree/main/maps/weather) |
| `route_eta_history.json` | Rolling 180-day riding-time calibration | [View](https://github.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/blob/main/route_eta_history.json) |
| `saved_workouts.json` | Read-only mirror of your Intervals.icu saved workouts | [View](https://github.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/blob/main/saved_workouts.json) |

`latest.json.data_overview` lists these companions and their availability. It includes routed rides of any route status from the 90-day event fetch, but unrouted rides only within 120 h. Later routed rides retain route/climb details with weather status and map reason `beyond_horizon`. `rides_without_route_beyond_horizon` counts later unrouted rides excluded from the list; `rides_total` counts eligible rides before the 64-ride cap, and `rides_omitted` counts only cap overflow.

## Auto-Sync

The GitHub Actions workflow in `.github/workflows/auto-sync.yml` keeps this data current. How often it runs on its own depends on the installed workflow: the standard auto-sync workflow checks every 30 minutes by default, and GitHub may delay or skip scheduled runs; the on-demand workflow syncs only when you use Sync Now. For Default, Fast and hybrid schedules, see the [setup guide](https://github.com/CrankAddict/section-11/blob/main/examples/json-auto-sync/SETUP.md#sync-schedule-and-github-actions-usage). A hybrid schedule checks more often during an active window fixed in UTC, so its local-clock hours can shift when daylight saving time starts or ends. The pipeline pulls activities, wellness, and planned workouts from the Intervals.icu API, calculates derived metrics (ACWR, monotony, polarization, phase detection), and generates graduated alerts.

## AI Analysis

With the updated workflow, GitHub sync and On-demand can use 4 Intervals.icu requests on a quiet slow-cache hit instead of about 31; first runs, refreshes and misses cost more. Only profile settings, aggregate curves and current-window messages persist in a plain Actions cache outside this repository. Raw core responses and accounting stay runner-only. Neither `state/` nor the cache is committed or included in the download, and AI tools must ignore both. `latest.json.source_freshness` carries source status, acquisition age, invocation counts and warnings. Hosted runs have no daily allowance controller or step-down. Restoring never resets source age; null age means unknown. See the [field reference](https://github.com/CrankAddict/section-11/blob/main/examples/json-examples/README.md#source-freshness) and [cache disclosure](https://github.com/CrankAddict/section-11/blob/main/examples/json-auto-sync/SETUP.md#private-state-and-request-limits).

**GitHub connector or authenticated repository access (private repository):** connect this repository to your AI, then ask:

```
Analyze my training using these files from the YOUR_GITHUB_USER/YOUR_REPO_NAME repository: latest.json, history.json, intervals.json, routes.json and saved_workouts.json.
```

**Public repository with URL fetch:** use this only if this repository is public. Everything committed here, including the training data, is then readable by anyone.

```
Analyze my training using these data files:
- Current: https://raw.githubusercontent.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/main/latest.json
- History: https://raw.githubusercontent.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/main/history.json
- Intervals: https://raw.githubusercontent.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/main/intervals.json
- Routes: https://raw.githubusercontent.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/main/routes.json
- Saved workouts: https://raw.githubusercontent.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/main/saved_workouts.json
```

**Private repository without a connector:** use [Sync Now](#sync-now), then upload the JSON files from the **training-data** artifact. Plain raw URLs do not work for a private repository.

For best results, pair with the [Section 11 instruction set](https://github.com/CrankAddict/section-11).

## License

[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/): Free for personal and non-commercial use. Attribution required.
