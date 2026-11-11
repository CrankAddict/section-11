# Owner setup: CrankAddict/section-11-demo

The owner creates and operates this one public repository after the updater is
published and verified. It contains fictional data only. This kit does not create
the repository or install a release for you. The first Sync does the installation.

The kit uses the current published workflow with runtime verification on every
run and the standard ten-minute application-maintenance allowance. Its fictional
data schedule remains once daily at 05:07 UTC.

The kit separates these owner instructions from the repository files in `repo/`.
Only the contents of `repo/` belong in the repository. The demo explanation lives
in `demo/ABOUT_THIS_DEMO.md`; the root README is the normal user README. The kit
ships no root README: the first Sync's installation creates it from the official
release template, and successful data publication updates its sync timestamp.
There is no root LICENSE or .gitignore to add. The installed Section 11 license
lives at `section11/LICENSE`.

1. Wait for the first official date release supporting this kit's guarded workflow
   (workflow v11.111 or later). If no official date release exists,
   stop here. Use the matching published, sealed source to build this kit.
   Do not use a test kit or development files. A workflow containing UNSEALED
   is refused by the builder; never invent a seal or edit the release manifest.
2. Create **CrankAddict/section-11-demo**, **Public**, default branch `main`.
   Add the contents of `repo/` at the repository root, including its single
   `.github/workflows/auto-sync.yml`. Keep `SETUP_DEMO.md` outside the repository.
   No managed tree needs to be uploaded.
   There is no Intervals account, `ATHLETE_ID` or `INTERVALS_KEY` to configure.
   GitHub supplies the job token; no personal token is needed.

   Set the repository description to:
   `Fictional-data demo of a Section 11 data repository. Start with demo/ABOUT_THIS_DEMO.md.`
   Set its homepage to
   `https://github.com/CrankAddict/section-11-demo/blob/main/demo/ABOUT_THIS_DEMO.md`.
3. Immediately before the owner-file commit, accept the installation terms:

   > Anything you added or changed inside section11/ will be deleted. Move what you want to keep to custom/ first.

   Root sync.py, push.py and pull.py will be removed if present. Outside
   `section11/`, any file in any folder named exactly like a release or historical
   Section 11 file is removed, except the update guide's keep list.
   Protection ignores case; removal requires exact spelling. Keep your own files
   in `custom/` or outside the repository. Existing data,
   custom files and the fictional dossier stay. Commit through the repository's
   normal policy. This action authorizes the first installation.
4. Enable Actions and effective **contents: write** and **actions: read** access.
   No PR-creation or merge setting is required. A protected-branch refusal stops
   without retry or alternate credentials; resolve repository policy explicitly.
   Confirm **Auto-Sync Intervals.icu Data** appears in Actions on the default branch.
   A committed file alone does not prove workflow registration.
5. Initially leave `SECTION11_AUTO_UPDATE` absent or false for half mode.
   No athlete secrets are needed.
6. Select **Sync** in the same workflow. It verifies the latest official runtime
   and reads back one installation commit before generating fictional
   files. Inspect the complete `section11/` inventory, manifest, receipt tag,
   full commit SHA and manifest digest, missing custom guidance and all outside removals.
   Then inspect the separate data commit: seven labelled JSON files, today's UTC
   archive and README timestamp. The data timestamp is synthetic midnight UTC.
   A manual Sync also offers the standard six-file training-data artifact.
7. Select **Status** in that workflow. It shows the verified target without an
   installation or training export. Select **Update** to accept a newer verified
   replacement when available; there is no adoption PR or merge.
8. Read the installed [update contract](https://github.com/CrankAddict/section-11-demo/blob/main/section11/examples/maintenance/UPDATING.md).
   Set **SECTION11_AUTO_UPDATE=true** only after verifying the first installation
   and data readback. Automatic application maintenance follows data work even
   if it failed. It defers while another default-branch run is active or finished
   less than ten minutes ago, including failures and no-ops. Reruns, old runs and
   incomplete run history also defer it; unknown publication needs reconciliation.
   This allowance does not skip the daily data sync or runtime verification.
   A later official release installs directly after trusted validation.
   Do not manufacture official releases for the demo.
9. Verify the next scheduled data run and the next genuine update's exact
   parent/tree readback in Actions and repository history. A dispatch acceptance
   or green badge alone is not proof of installation.

For an existing demo, replace only `.github/workflows/auto-sync.yml` with
`repo/.github/workflows/auto-sync.yml`. Save its current file and let any run finish
first. Never replace the root README of a running demo or copy the whole kit over
it. The other existing repository files stay in place. This kit's workflow keeps
the fictional producer and daily schedule intact.
On the first **Sync** after replacement, tick **Use for the first
Sync after adopting this workflow**; leave it unticked later. This forces a
verified application download without selecting Update in half mode. Keep
`SECTION11_SYNC_TIMER` absent or off to retain the daily GitHub schedule.

The generator is deterministic per UTC date. A repeat Sync on the same UTC date
shows as a failed run with no data commit when `latest.json` is unchanged. The
publisher's unchanged-latest guard reports the generic message
"Hosted acquisition or phase verification failed". A newly recorded update notice
can change the exported notice. Use Status or Update for maintenance
without a needless data run. No slow-source cache is used by the fictional producer.

Set `SECTION11_AUTO_UPDATE=false` to disable future automatic installations.
Cancel an in-flight run separately and inspect its readback. **Rollback** restores
only a compatible previous managed installation and records its rejected date;
newer data/custom remain. A pre-adoption or missing-history recovery requires the
owner to restore the matching old workflows and installation paths from history.
Never revert the whole repository. An unknown publication result needs remote
inspection before another run.

The generator and fictional dossier remain outside `section11/`. Updates cannot
replace them or the active workflow. Review future workflow changes separately,
preserving the fictional producer, its data-run condition and daily data schedule.
This repository publishes every committed file to everyone.
