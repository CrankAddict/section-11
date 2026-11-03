"""Fixes from the first live rehearsal: pycache inventory, issue resolution, clean refusals."""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'examples/maintenance'))
import distribution
import github_api
import publish_release


def bot_issue(number, body, state='open'):
    return {'number': number, 'state': state, 'body': body, 'html_url': 'issue-' + str(number),
            'user': {'login': 'github-actions[bot]'}}


class InventoryTests(unittest.TestCase):
    def test_active_templates_disable_bytecode_and_retired_templates_cannot_run_code(self):
        for path in ('examples/json-auto-sync/auto-sync.yml', 'examples/json-on-demand/auto-sync.yml',
                     '.github/workflows/release.yml'):
            self.assertIn("PYTHONDONTWRITEBYTECODE: '1'", (ROOT / path).read_text())
    def test_scheduled_backup_is_in_same_sync_workflow_only(self):
        text = (ROOT / 'examples/json-auto-sync/auto-sync.yml').read_text()
        self.assertNotIn("cron: '17 4 * * *'", text)
        self.assertIn('Eligible update maintenance', text)
        self.assertNotIn('workflow_run:', text)
        self.assertNotIn('schedule:', (ROOT / 'examples/json-on-demand/auto-sync.yml').read_text())


class ManifestIssueResolutionTests(unittest.TestCase):
    MARKER = '<!-- section11-release-manifest-failure -->'

    def test_open_bot_issue_is_commented_and_closed(self):
        api = mock.Mock()
        human = dict(bot_issue(3, self.MARKER), user={'login': 'someone'})
        api.pages.return_value = [bot_issue(1, self.MARKER + ' old'), human, bot_issue(2, 'unrelated')]
        with contextlib.redirect_stdout(io.StringIO()):
            publish_release.resolve_manifest_failure(api, 'a' * 40)
        self.assertEqual([c.args[:2] for c in api.write.call_args_list],
                         [('POST', '/issues/1/comments'), ('PATCH', '/issues/1')])
        self.assertEqual(api.write.call_args_list[1].args[2], {'state': 'closed', 'state_reason': 'completed'})

    def test_resolution_failure_is_only_a_warning(self):
        api = mock.Mock()
        api.pages.return_value = [bot_issue(1, self.MARKER)]
        api.write.side_effect = RuntimeError('lost response')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            publish_release.resolve_manifest_failure(api, 'a' * 40)
        self.assertIn('::warning::', output.getvalue())
        self.assertEqual(api.write.call_count, 1)


# Direct publication and recorded rollback replace merged-PR provenance; see test_b2_hosted.

class CleanRefusalTests(unittest.TestCase):
    def run_cli(self, exc):
        def main():
            raise exc
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as stop:
            distribution.run_cli(main)
        return stop.exception.code, output.getvalue()

    def test_handled_refusals_exit_1_with_one_error_line_and_next_step(self):
        cases = (
            (ValueError('unmanaged installation files; preserve and reconcile before automation'), 'custom/'),
            (ValueError('release 2026.10.24 already exists; second same-date release refused, no changes'),
             'next nightly release'),
            (distribution.DistributionError('hash mismatch for LICENSE'), 'Regenerate the manifest'),
            (ValueError('owner wrapper update required: auto-sync.yml API 2'), 'replaced by hand'),
            (ValueError('something new'), 'Nothing further was changed'),
        )
        for exc, step in cases:
            with self.subTest(exc=str(exc)):
                code, out = self.run_cli(exc)
                self.assertEqual(code, 1)
                self.assertNotIn('Traceback', out)
                self.assertEqual(out.count('::error::'), 1)
                self.assertIn(step, out)

    def test_direct_write_refusal_has_no_permission_bypass_hint(self):
        code, out = self.run_cli(RuntimeError('publication not on observed default history; no retry'))
        self.assertEqual(code, 1)
        self.assertIn('repository policy with the owner', out)
        self.assertIn('No retry or alternate credential', out)
        self.assertNotIn('pull requests', out)

    def test_unexpected_errors_keep_their_traceback(self):
        for exc in (github_api.APIError(500, 'server error'), KeyError('x'), OSError('disk')):
            with self.subTest(exc=type(exc).__name__):
                def main():
                    raise exc
                with self.assertRaises(type(exc)):
                    distribution.run_cli(main)

    def test_update_context_hint_overrides_publisher_hint(self):
        def main():
            raise distribution.DistributionError('hash mismatch for LICENSE')
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            distribution.run_cli(main, (('hash mismatch', 'Nothing was installed; inspect the verified source.'),))
        self.assertIn('Nothing was installed', output.getvalue())

    def test_success_returns_value(self):
        self.assertEqual(distribution.run_cli(lambda: 'published'), 'published')


if __name__ == '__main__':
    unittest.main()
