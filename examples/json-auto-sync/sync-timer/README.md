# Sync timer

An optional Cloudflare Worker that requests the **Sync timer** operation
every 30 minutes. Paste all of [sync-timer.js](sync-timer.js) into a Worker you
own in the Cloudflare dashboard. No packages are needed. Requires workflow
v11.105 or later (the first line of your `.github/workflows/auto-sync.yml`).
A file without this line is older; see [version compatibility](../SETUP.md#sync-timer-version-compatibility).
Also check that **Sync timer** appears under **Run workflow > Operation**.

In the data repository's **Settings > Secrets and variables > Actions > Variables**,
add a repository variable named:

```text
SECTION11_SYNC_TIMER
```

With value:

```text
on
```

This skips GitHub's own scheduled sync job before a runner starts. There is no
native backup while it is on. Manual Sync Now and timer runs remain enabled.

Set these Worker settings in the dashboard:

| Setting | Type | Value |
| --- | --- | --- |
| `GITHUB_TOKEN` | Secret | A dedicated fine-grained GitHub token for your data repository only, with Actions read and write and an expiry |
| `GITHUB_REPOSITORY` | Text variable | `owner/name` of that repository |
| `GITHUB_REF` | Optional text variable | Your default branch name, if it is not `main` |

Add a Cron Trigger of **`22,52 * * * *`** (UTC). It runs every 30 minutes.
The exported freshness expectation assumes this interval even if you edit the
Cron Trigger. It normally marks data late two hours after generation, using
the existing hosted grace; a provider hold can extend the deadline.

Update by re-pasting the newer `sync-timer.js`. To pause, delete the Cron Trigger;
add it again to resume. There is no disable switch. Never use **Disable workflow**
in GitHub: that blocks both the timer and Sync Now. To have GitHub's own schedule
sync instead, do both: pause this timer and turn `SECTION11_SYNC_TIMER` off or
delete the variable. Keep the workflow's existing native schedule block. See the
[setup guide](../SETUP.md#sync-timer-optional).

The token is **not start-only**. Its authority extends to any workflow in that
repository, including Update, Rollback and, if installed, workout push, which
can delete workouts or change thresholds. Use a dedicated token with an expiry
and set your own reminder before it expires. Cloudflare stores it as your Worker
secret; give it no Intervals.icu credential.

Timer runs skip the `training-data` artifact. Manual Sync Now keeps its existing
**7-day** download artifact, including for On-demand users. Timer runs use the
scheduled history run budget; manual Sync Now stays on demand and budget-exempt.

In a private repository, budget about **1,488 billed Actions minutes** per
31-day month at one minute per timer run, about the same as the default native
30-minute schedule it replaces. The switch prevents duplicate native syncs.
Longer jobs, retries and other
workflows add more. Monitor your account's Actions usage and budget.

**A successful start is not a finished sync: check that Sync timer run published.**
If syncs stop, check Observability (Workers Logs) in the Cloudflare dashboard
and the run in GitHub Actions. The unchanged timestamp and deadline in `latest.json`
show lateness; they do not start a backup run. HTTP 422 can mean the old wrapper
lacks the Sync timer choice. Pause the timer on repeated failures and resolve
the cause before resuming.
