<!-- 
  DATA REPO README TEMPLATE
  
  Replace these placeholders:
    YOUR_GITHUB_USER  → your GitHub username
    YOUR_REPO_NAME    → your repository name
  
  Then delete this comment block.
-->

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

# Training Data Pipeline

![Sync Status](https://github.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/actions/workflows/auto-sync.yml/badge.svg)

**Last successful sync:** _updated automatically_

Automated training data pipeline from [Intervals.icu](https://intervals.icu) for AI coaching analysis.
Built on the [Section 11 Protocol](https://github.com/CrankAddict/section-11).

## Data URLs

| File | Description | Link |
|------|-------------|------|
| `latest.json` | Current 7-day snapshot + derived metrics | [View](https://raw.githubusercontent.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/main/latest.json) |
| `history.json` | Longitudinal data (daily/weekly/monthly) | [View](https://raw.githubusercontent.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/main/history.json) |

## Auto-Sync

Data syncs every 15 minutes via GitHub Actions. The pipeline pulls activities, wellness, and planned workouts from the Intervals.icu API, calculates derived metrics (ACWR, monotony, polarization, phase detection), and generates graduated alerts.

## AI Analysis

```
Analyze my training using these data files:
- Current: https://raw.githubusercontent.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/main/latest.json
- History: https://raw.githubusercontent.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/main/history.json
```

For best results, pair with the [Section 11 instruction set](https://github.com/CrankAddict/section-11).

## License

[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) — Free for personal and non-commercial use. Attribution required.
