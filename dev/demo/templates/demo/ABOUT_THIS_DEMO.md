# About this demo

> [!IMPORTANT]
> **This demo shows how a Section 11 data repository works, not what your data will look like.**
> Everything here is fictional, and the JSON files are deliberately small stand-ins.
> A real `latest.json` is much larger and covers more days; see
> [Demo vs. real setup](#demo-vs-real-setup). Never use these values as training advice.

[![Daily synthetic sync](https://github.com/CrankAddict/section-11-demo/actions/workflows/auto-sync.yml/badge.svg)](https://github.com/CrankAddict/section-11-demo/actions/workflows/auto-sync.yml)

## What this demo shows

- **Installation from an official release.** The first Sync installed
  [`section11/`](https://github.com/CrankAddict/section-11-demo/tree/main/section11) from the verified official Section 11
  release, exactly as it does for a new user.
- **Daily automatic data commits.** A scheduled run at 05:07 UTC writes the data
  files, a copy in [`archive/`](https://github.com/CrankAddict/section-11-demo/tree/main/archive) and the sync time in
  [README.md](https://github.com/CrankAddict/section-11-demo/blob/main/README.md). GitHub may delay or skip a scheduled run.
- **Automatic, verified updates.** When a new official release is published, the demo
  installs it on its own. [Actions](https://github.com/CrankAddict/section-11-demo/actions) and the
  [commit history](https://github.com/CrankAddict/section-11-demo/commits/main) show each installation and its release.
- **The layout of a real GitHub data repository.** Apart from this `demo/` folder,
  the repository looks exactly like a user's: the standard README, the same seven JSON
  files, `archive/`, `section11/`, [`custom/`](https://github.com/CrankAddict/section-11-demo/tree/main/custom) for your own
  files and a `DOSSIER.md` in the root, where a real user keeps theirs.

## What it does not show

- **Real training data or analysis.** A small fictional generator
  ([demo/generate.py](https://github.com/CrankAddict/section-11-demo/blob/main/demo/generate.py)) replaces Intervals.icu:
  one indoor rider, five rides and two rest days a week. No account, key or personal
  data is involved.
- **The full contents of the real files.** The demo files only demonstrate publication
  and updates. Reports and AI analysis need the real files described below.

## Demo vs. real setup

| File | This demo | Real setup |
|---|---|---|
| [latest.json](https://github.com/CrankAddict/section-11-demo/blob/main/latest.json) | 8 sections: 7 days of rides and wellness, no planned workouts | About 25 sections, including readiness, alerts, derived metrics, weekly summary and race calendar. Wellness and summaries cover the last 7 days, activities with interval data the last 28 days, plus a 28-day wellness series. Planned workouts up to 42 days ahead |
| [history.json](https://github.com/CrankAddict/section-11-demo/blob/main/history.json) | 28 fictional days | Long-term history: 90 days daily, 180 days weekly, summaries up to 3 years |
| [intervals.json](https://github.com/CrankAddict/section-11-demo/blob/main/intervals.json) | empty | Interval, structure and DFA detail for completed sessions, kept 14 days |
| [routes.json](https://github.com/CrankAddict/section-11-demo/blob/main/routes.json) | empty (indoor demo) | Planned routes with terrain and weather |
| [route_eta_history.json](https://github.com/CrankAddict/section-11-demo/blob/main/route_eta_history.json) | empty | Rolling 180-day record for route time estimates |
| [ftp_history.json](https://github.com/CrankAddict/section-11-demo/blob/main/ftp_history.json) | one sample entry | FTP progression |
| [saved_workouts.json](https://github.com/CrankAddict/section-11-demo/blob/main/saved_workouts.json) | empty | Your saved workout library (read-only) |

For a fuller fictional example of the real format, see
[`section11/examples/json-examples/`](https://github.com/CrankAddict/section-11-demo/tree/main/section11/examples/json-examples).
Those examples come from an older sync version, so the newest sections are missing.

## Use Section 11 for real

- **GitHub:** follow the [GitHub setup guide](https://github.com/CrankAddict/section-11-demo/blob/main/section11/examples/json-auto-sync/SETUP.md)
  with your own **private** repository and your own Intervals.icu key.
  Do not copy this public demo as a data repository.
- **Your own computer:** follow the [local sync guide](https://github.com/CrankAddict/section-11-demo/blob/main/section11/examples/json-local-sync/SETUP.md).
- **Updates and rollback:** see [UPDATING.md](https://github.com/CrankAddict/section-11-demo/blob/main/section11/examples/maintenance/UPDATING.md).
- Keep your real dossier private. The [DOSSIER.md](https://github.com/CrankAddict/section-11-demo/blob/main/DOSSIER.md) here is an invented sample.

Everything demo-specific lives in this `demo/` folder: the fictional generator and this page.

Section 11 is distributed under its [LICENSE](https://github.com/CrankAddict/section-11-demo/blob/main/section11/LICENSE).
