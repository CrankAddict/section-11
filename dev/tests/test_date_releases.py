"""Daily UTC release contracts; all external transport is mocked."""
import contextlib
import io
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from test_update_prototype import (
    D, SYNC, ROOT, Offline, fixture, manifest, install, write, inventory,
    github_api, publish_release, release_package)


def catalog(*tags):
    return [{'id': i + 1, 'tag_name': tag, 'draft': False, 'prerelease': False,
             'published_at': '2026-10-23T12:00:00Z'} for i, tag in enumerate(tags)]


class DateIdentityTests(Offline):
    def test_calendar_day_format_has_no_suffix_and_release_accepts_sequence(self):
        for tag in ('2026.10.23', '2028.02.29', '2026.12.31'):
            self.assertEqual(D.release_date(tag).strftime('%Y.%m.%d'), tag)
        for tag in ('v2026.10.23', '2026.10.23.1', '2026.10.23-2', '2026.1.01',
                    '2026.02.29', '2026.13.01', '0000.01.01', '11.92'):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                D.calendar_day(tag)
        self.assertEqual(D.release_key('2026.10.23-2'), (D.calendar_day('2026.10.23'), 2))

    def test_utc_midnight_rolls_date_not_versions(self):
        before = datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        self.assertEqual(D.utc_tag(before), '2026.12.31')
        self.assertEqual(D.utc_tag(before + timedelta(seconds=1)), '2027.01.01')
        for instant in (datetime(2026, 1, 1), before.replace(tzinfo=timezone(timedelta(hours=1)))):
            with self.assertRaisesRegex(ValueError, 'UTC'):
                D.utc_tag(instant)

    def test_github_adapter_selects_latest_date_without_protocol_gate(self):
        raw, files = fixture('11.92')
        archive = release_package.build(raw, files, 'a' * 40, '2026.10.24')['section11-2026.10.24.zip']
        api = github_api.GitHub('example-owner/private', token='fake')
        release = dict(catalog('2026.10.24')[0], html_url='private',
                       assets=[{'name': 'section11-2026.10.24.zip', 'id': 4}])
        with mock.patch.object(api, 'pages', return_value=catalog('2026.10.23', '2026.10.24')), \
                mock.patch.object(api, 'get', return_value=release) as get, \
                mock.patch.object(api, 'resolve_tag', return_value='a' * 40), \
                mock.patch.object(api, 'asset', return_value=archive), \
                mock.patch.object(api, 'tree', return_value={'manifest.json': {'mode': '100644', 'sha': 'blob'}}), \
                mock.patch.object(api, 'blob', return_value=raw):
            self.assertEqual(api.release()[2]['tag'], '2026.10.24')
        get.assert_called_once_with('/releases/latest')

    def test_local_adapter_selects_date_not_api_list_order(self):
        raw, files = fixture()
        tag = '2026.10.24'
        archive = release_package.build(raw, files, 'a' * 40, tag)['section11-' + tag + '.zip']
        url = 'https://github.com/CrankAddict/section-11/releases/download/' + tag + '/section11-' + tag + '.zip'
        rows = catalog('2026.10.23', tag)
        rows[1].update(html_url='release', assets=[{'name': 'section11-' + tag + '.zip',
                                                 'size': len(archive), 'browser_download_url': url}])
        response = mock.Mock(content=raw)
        response.iter_content.return_value = [archive]
        with mock.patch.object(D, 'api_read', side_effect=[
                rows[1], {'object': {'type': 'commit', 'sha': 'a' * 40}},
                {'object': {'type': 'commit', 'sha': 'a' * 40}}]), \
                mock.patch.object(SYNC.requests, 'get', return_value=response):
            self.assertEqual(D.fetch()[2]['tag'], tag)


class DailyPublishingTests(Offline):
    def lookup(self, api, latest, today=None):
        releases = [latest] + ([today] if today and today['tag_name'] != latest['tag_name'] else [])
        api.resolve_tag.return_value = 'b' * 40
        def get(path, **kwargs):
            if path == '/releases/latest':
                return latest
            if path == '/releases?per_page=100&page=1':
                return releases
            if path.startswith('/git/matching-refs/tags/'):
                prefix = path.split('/tags/', 1)[1].split('?', 1)[0]
                return [{'ref': 'refs/tags/' + r['tag_name']} for r in releases if r['tag_name'].startswith(prefix)]
            if path.startswith('/releases/tags/'):
                if today is None:
                    raise github_api.APIError(404, 'synthetic missing date')
                return today
            raise AssertionError('unexpected metadata request: ' + path)
        api.get.side_effect = get

    def test_no_change_skips_all_mutations_even_if_manifest_format_changes(self):
        raw, files = fixture()
        api = mock.Mock()
        self.lookup(api, catalog('2026.10.23')[0])
        api.manifest_at.return_value = raw
        equivalent = json.dumps(json.loads(raw), indent=4).encode()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            publish_release.publish(api, 'a' * 40, equivalent, files, '2026.10.24')
        self.assertIn('unchanged; no release', output.getvalue())
        api.write.assert_not_called()
        api.release.assert_not_called()

    def test_same_date_published_allocates_suffix_but_foreign_draft_stops(self):
        from _release_fakes import ReleaseAPI
        raw, files = fixture()
        new = dict(files, LICENSE=b'new license')
        for draft, resume in ((False, False), (False, True), (True, False)):
            with self.subTest(draft=draft, resume=resume):
                api = ReleaseAPI()
                api.seed('2026.10.23', 'b' * 40, raw, files, draft=draft)
                if draft:
                    with self.assertRaisesRegex(ValueError, 'collision'):
                        publish_release.publish(api, 'a' * 40, manifest(new), new, '2026.10.23', resume=resume)
                else:
                    with mock.patch.object(publish_release, 'build', side_effect=RuntimeError('build boundary')) as build, \
                            self.assertRaisesRegex(RuntimeError, 'build boundary'):
                        publish_release.publish(api, 'a' * 40, manifest(new), new, '2026.10.23', resume=resume)
                    build.assert_called_once_with(manifest(new), new, 'a' * 40, '2026.10.23-2')
                self.assertEqual(api.writes, [])

    def test_unchanged_content_with_existing_same_date_release_is_quiet_noop(self):
        raw, files = fixture()
        api = mock.Mock()
        self.lookup(api, catalog('2026.10.23')[0], catalog('2026.10.23')[0])
        api.manifest_at.return_value = raw
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(publish_release.publish(api, 'a' * 40, raw, files, '2026.10.23'), 'unchanged')
        self.assertIn('unchanged; no release', output.getvalue())
        api.write.assert_not_called()
        api.release.assert_not_called()

    def test_changed_payload_with_same_protocol_reaches_package_build(self):
        raw, files = fixture()
        new = dict(files, LICENSE=b'new license')
        api = mock.Mock()
        self.lookup(api, catalog('2026.10.23')[0])
        api.manifest_at.return_value = raw
        with mock.patch.object(publish_release, 'build', side_effect=RuntimeError('build boundary')) as build, \
                self.assertRaisesRegex(RuntimeError, 'build boundary'):
            publish_release.publish(api, 'a' * 40, manifest(new), new, '2026.10.24')
        build.assert_called_once_with(manifest(new), new, 'a' * 40, '2026.10.24')

    def test_manifest_mismatch_precedes_existing_date_and_any_api_write(self):
        raw, files = fixture()
        api = mock.Mock()
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            publish_release.publish(api, 'a' * 40, raw, dict(files, LICENSE=b'bad'), '2026.10.23')
        self.assertEqual(api.mock_calls, [])

    def test_manifest_failure_deduplicates_issue_and_source_stays_broken(self):
        raw, files = fixture()
        install(self.root, raw, files)
        (self.root / 'LICENSE').write_bytes(b'bad')
        before = inventory(self.root)
        api = mock.Mock()
        issue = {'number': 7, 'state': 'open', 'body': '', 'html_url': 'private-issue',
                 'user': {'login': 'github-actions[bot]'}}
        issues = []
        api.pages.side_effect = lambda path: list(issues)
        def mutate(method, path, body):
            if path.endswith('/comments'):
                return {'id': 1}
            issue.update(body)
            if method == 'POST':
                issues.append(issue)
            return issue
        api.write.side_effect = mutate
        api.get.side_effect = lambda path: issue
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, 'hash mismatch'), contextlib.redirect_stdout(io.StringIO()):
                publish_release.release_source(api, self.root, 'a' * 40)
        self.assertEqual([c.args[:2] for c in api.write.call_args_list],
                         [('POST', '/issues'), ('POST', '/issues/7/comments')])
        self.assertEqual(len(issues), 1)
        self.assertEqual(inventory(self.root), before)

    def test_manifest_issue_unknown_response_never_retries(self):
        api = mock.Mock()
        api.pages.return_value = []
        api.write.side_effect = RuntimeError('synthetic lost response')
        with self.assertRaisesRegex(RuntimeError, 'unknown'):
            publish_release.manifest_failure(api, 'a' * 40, ValueError('bad manifest'))
        self.assertEqual(api.write.call_count, 1)

    def test_workflow_crons_are_utc_only_and_no_push_trigger(self):
        release = (ROOT / '.github/workflows/release.yml').read_text()
        update = (ROOT / 'examples/json-auto-sync/auto-sync.yml').read_text()
        self.assertNotIn('schedule:', release)
        self.assertIn('workflow_dispatch:', release)
        self.assertNotIn("cron: '17 4 * * *'", update)
        self.assertNotIn('  push:', release)
        self.assertNotIn('timezone:', release + update)
        self.assertIn('issues: write', release)


class DateUpdaterTests(Offline):
    def test_local_current_prints_date_status_and_informational_versions(self):
        raw, files = fixture('11.92')
        install(self.root / 'section11', raw, files)
        ident = {'tag': '2026.10.23', 'commit': 'a' * 40, 'catalog': catalog('2026.10.23')}
        write(self.root / 'section11', {D.RECEIPT: D.receipt(raw, ident)})
        output = io.StringIO()
        with mock.patch.object(Path, 'cwd', return_value=self.root), \
                mock.patch.object(SYNC, '__file__', str(self.root / 'section11/examples/sync.py')), \
                mock.patch.object(SYNC, '_fetch_verified_release', return_value=(raw, files, ident)), \
                mock.patch('builtins.input', return_value='y'), \
                contextlib.redirect_stdout(output):
            self.assertTrue(SYNC.do_update())
        for value in ('Installed release: 2026.10.23', 'up to date: yes', '11.92', '3.157'):
            self.assertIn(value, output.getvalue())

    def test_local_date_downgrade_preserves_all_bytes(self):
        raw, files = fixture()
        new = dict(files, LICENSE=b'new content')
        new_raw = manifest(new)
        install(self.root / 'section11', new_raw, new)
        write(self.root / 'section11', {D.RECEIPT: D.receipt(new_raw, {'tag': '2026.10.24', 'commit': 'b' * 40})})
        before = inventory(self.root)
        ident = {'tag': '2026.10.23', 'commit': 'a' * 40,
                 'catalog': catalog('2026.10.23', '2026.10.24')}
        output = io.StringIO()
        with mock.patch.object(Path, 'cwd', return_value=self.root), \
                mock.patch.object(SYNC, '_fetch_verified_release', return_value=(raw, files, ident)), \
                mock.patch.object(D, 'fetch', return_value=(new_raw, new, {})), \
                contextlib.redirect_stdout(output):
            self.assertFalse(SYNC.do_update())
        self.assertIn('date downgrade', output.getvalue())
        self.assertEqual(inventory(self.root), before)

    def test_github_current_status_has_no_installation_or_control_write(self):
        from test_b2_hosted import Remote, release
        from direct_commit import DirectPublisher
        from hosted_update import HostedUpdater
        remote = Remote()
        publisher = DirectPublisher(remote)
        updater = HostedUpdater(publisher, lambda: release(), {})
        updater.install(publisher.snapshot(), accepted=True)
        before = remote.tip
        remote.calls.clear()
        result = updater.status(publisher.snapshot())
        self.assertEqual(result['installed'], '2026.10.30')
        self.assertFalse(any(result['plan'].values()))
        self.assertEqual(remote.tip, before)
        self.assertFalse(any(call[0] != 'GET' for call in remote.calls))

    def test_github_date_downgrade_refuses_before_publication(self):
        from test_b2_hosted import Remote, release
        from direct_commit import DirectPublisher
        from hosted_update import HostedUpdater
        remote = Remote()
        publisher = DirectPublisher(remote)
        HostedUpdater(publisher, lambda: release(), {}).install(publisher.snapshot(), accepted=True)
        before = remote.tip
        with self.assertRaisesRegex(ValueError, 'date downgrade'):
            HostedUpdater(publisher, lambda: release('2026.10.29'), {}).install(publisher.snapshot(), accepted=True)
        self.assertEqual(remote.tip, before)
