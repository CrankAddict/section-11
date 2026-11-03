<!--
  DATA REPO README TEMPLATE
  YOUR_GITHUB_USER and YOUR_REPO_NAME are filled when this page is generated.
-->

# Your Section 11 training data

Your training-data repository, synced from [Intervals.icu](https://intervals.icu)
for Section 11 coaching.

![Sync Status](https://github.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/actions/workflows/auto-sync.yml/badge.svg)

**Last successful sync:** _updated automatically_

## Sync Now

[🔄 Sync Now](../../actions/workflows/auto-sync.yml): choose **Run workflow** on the
default branch to refresh your data, for example after a workout. The files here
are updated when the sync succeeds.

## What is here

- `latest.json`: your current training snapshot.
- `history.json`: longer-term training trends.
- `intervals.json`: interval and completed-session details.
- `routes.json`: planned routes, terrain and route weather.
- `saved_workouts.json`: your saved Intervals.icu workouts.
- `ftp_history.json`: FTP change history.
- `route_eta_history.json`: riding-time calibration history.
- `maps/weather/`: route-weather PNG pages.
- `archive/`: daily copies of latest.json.
- `section11/`: the installed protocol (`SECTION_11.md`), report templates
  (`examples/reports/`) and Workout Reference Library.
- `custom/`: your own files and notes.
- `DOSSIER.md`: your private athlete dossier, if you use one, kept here in the root. It can contain sensitive personal and health details, so keep this repository private; Git keeps old versions, so deleting it later does not erase it.

See the installed
[field reference](section11/examples/json-examples/README.md) for file details.

## Use with your AI

Connect your AI to this repository with a connector or link first. Otherwise,
choose **Code > Download ZIP** and give the ZIP to your chat or project. It is a
snapshot: re-upload for fresh data and after updates.

For example:

> Analyze my training using latest.json, history.json, intervals.json, routes.json,
> saved_workouts.json and ftp_history.json, with
> section11/SECTION_11.md and the report templates in section11/examples/reports/ and DOSSIER.md if present.

Raw links work only if this repository is public; then everything here is public, so never make a repository with your dossier public.

## Updates

By default, a notice tells you when an update is available. Choose **Update** in
the sync workflow to install it, **Status** to review the plan, or **Rollback** to
restore the previous installation. Set repository variable
`SECTION11_AUTO_UPDATE=true` to opt into automatic updates.

This page is refreshed at every install, update and rollback; keep personal notes
in `custom/`. See the installed [update guide](section11/examples/maintenance/UPDATING.md).

Outside `section11/`, updates remove exact release or historical Section 11 filenames
in any folder, except the guide's keep list. Protection ignores case. Keep personal
files in `custom/` or outside this repository; Git retains removed files.

## License

The Section 11 files in `section11/` are [MIT licensed](section11/LICENSE).
