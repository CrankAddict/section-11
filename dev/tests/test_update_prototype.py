"""Offline release, verification and publication contracts; no live services."""
import contextlib
import importlib.util
import io
import json
import os
import runpy
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from datetime import datetime, timezone
from unittest import mock
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
MAINT = ROOT / 'examples/maintenance'
sys.path.insert(0, str(MAINT))
import distribution
import github_api
import publish_release
import release_package
import validate_data
from test_data_overview import tiny_png

D = distribution.Distribution
SYNC = distribution._sync
from _local_timer_fakes import fake_timers
REAL_TIMERS = SYNC.LocalTimers


def manifest(files):
    return (json.dumps({'files': {p: {'hash': D.digest(b)} for p, b in files.items()}}, sort_keys=True) + '\n').encode()


def fixture(version='9000.0'):
    files = {'SECTION_11.md': ('# Synthetic\n**Protocol Version:** ' + version +
                              '\n### Changelog\n**v' + version + ' - Synthetic:**\nFixture only.\n').encode(),
             'examples/sync.py': b'class IntervalsSync:\n    VERSION = "3.157"\n',
             'changelog.json': b'{"notification_id":"fixture","changes":["Synthetic notice"]}',
             'LICENSE': b'license\r\nno final newline',
             'examples/reports/example-route-weather-map.png': tiny_png(),
             'examples/maintenance/wrapper-api.json': (MAINT / 'wrapper-api.json').read_bytes(),
             'examples/maintenance/CUSTOM_README.md': (MAINT / 'CUSTOM_README.md').read_bytes(),
             'examples/json-auto-sync/DATA_REPO_README_TEMPLATE.md': (
                 ROOT / 'examples/json-auto-sync/DATA_REPO_README_TEMPLATE.md').read_bytes(),
             'examples/json-auto-sync/auto-sync.yml': (ROOT / 'examples/json-auto-sync/auto-sync.yml').read_bytes()}
    return manifest(files), files


def write(root, files):
    root.mkdir(parents=True, exist_ok=True)
    for path, data in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def install(root, raw, files):
    write(root, dict(files, **{'manifest.json': raw}))


def inventory(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


class FixedNoon(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls.fromisoformat(os.environ.get('S11_TEST_BUDGET_START', '2026-10-28T12:00:00+00:00'))
        return value.astimezone(tz) if tz is not None else value.replace(tzinfo=None)


class Offline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        clock = mock.patch.object(SYNC, 'datetime', FixedNoon)
        clock.start()
        self.addCleanup(clock.stop)
        self.network = mock.patch('requests.sessions.Session.request',
                                  side_effect=AssertionError('unmatched network request'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.timers = fake_timers(REAL_TIMERS)
        timer_patch = mock.patch.object(SYNC, 'LocalTimers', self.timers)
        timer_patch.start()
        self.addCleanup(timer_patch.stop)


class DistributionTests(Offline):
    def test_duplicate_keys_case_prefix_hidden_and_reserved(self):
        for path in ('../x', '/x', 'x\\y', 'C:x', '.github/a.yml', 'dev/a.py',
                     'custom/x.json', 'latest.json', 'examples/../x'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                D.manifest(manifest({path: b'x'}))
        for files in ({'A.txt': b'a', 'a.txt': b'b'}, {'a': b'a', 'a/b': b'b'}):
            with self.assertRaises(ValueError):
                D.manifest(manifest(files))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            D.manifest(b'{"files":{},"files":{}}')

    def test_archive_special_duplicate_extra_and_partial(self):
        raw, files = fixture()
        assets = release_package.build(raw, files, 'a' * 40, '2026.10.23')
        good = assets['section11-2026.10.23.zip']
        self.assertEqual(D.archive(good), (raw, files))
        with self.assertRaises((ValueError, zipfile.BadZipFile)):
            D.archive(good[:100])
        for kind in ('symlink', 'duplicate', 'extra', 'missing'):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as z:
                for p, b in dict(files, **{'manifest.json': raw}).items():
                    if kind == 'missing' and p == 'LICENSE':
                        continue
                    info = zipfile.ZipInfo('section11/' + p)
                    info.external_attr = ((stat.S_IFLNK if kind == 'symlink' and p == 'LICENSE' else stat.S_IFREG) | 0o644) << 16
                    z.writestr(info, b)
                if kind in ('extra', 'duplicate'):
                    z.writestr('section11/' + ('extra.txt' if kind == 'extra' else 'LICENSE'), b'x')
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                D.archive(buffer.getvalue())

    def test_local_declined_orphan_preserves_entire_old_install(self):
        raw, old = fixture()
        old['old.txt'] = b'old'
        raw = manifest(old)
        install(self.root / 'section11', raw, old)
        write(self.root / 'section11', {D.RECEIPT: D.receipt(raw, {'tag': '2026.10.23', 'commit': 'b' * 40})})
        new_raw, new = fixture('9000.1')
        before = inventory(self.root)
        with mock.patch.object(Path, 'cwd', return_value=self.root), \
                mock.patch.object(SYNC, '__file__', str(self.root / 'section11/examples/sync.py')), \
                mock.patch.object(SYNC, '_fetch_verified_release', return_value=(new_raw, new, {
                    'commit': 'a' * 40, 'tag': '2026.10.24', 'catalog': [{'tag_name': '2026.10.24'}]})), \
                mock.patch('builtins.input', side_effect=['n']), contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(SYNC.do_update())
        self.assertEqual(inventory(self.root), before)

    def test_actions_notice_never_reads_network_or_config(self):
        with mock.patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}), \
                mock.patch.object(SYNC, '_fetch_verified_release', side_effect=AssertionError('notice called')):
            SYNC.notify_if_updates_available()

    def test_pin_manifest_and_tag_race(self):
        raw, files = fixture()
        canonical = release_package.build(raw, files, 'a' * 40, '2026.10.23')['section11-2026.10.23.zip']
        release = {'draft': False, 'prerelease': False, 'tag_name': '2026.10.23', 'html_url': 'release',
                   'assets': [{'name': 'section11-2026.10.23.zip', 'size': len(canonical),
                               'browser_download_url': 'https://github.com/CrankAddict/section-11/releases/download/2026.10.23/section11-2026.10.23.zip'}]}
        response = mock.Mock(content=raw)
        response.iter_content.return_value = [canonical]
        for last_sha in ('a' * 40, 'b' * 40):
            with self.subTest(last_sha=last_sha), \
                    mock.patch.object(D, 'api_read', side_effect=[release,
                         {'object': {'type': 'commit', 'sha': 'a' * 40}},
                         {'object': {'type': 'commit', 'sha': last_sha}}]), \
                    mock.patch.object(SYNC.requests, 'get', return_value=response) as get:
                if last_sha.startswith('b'):
                    with self.assertRaisesRegex(ValueError, 'changed'):
                        D.fetch()
                else:
                    self.assertEqual(D.fetch()[:2], (raw, files))
                self.assertIn('/' + 'a' * 40 + '/manifest.json', get.call_args_list[-1].args[0])
                self.assertFalse(any('/main' in c.args[0] for c in get.call_args_list))


class PublicationTests(Offline):
    def legacy(self):
        namespace = {'__name__': 'legacy'}
        source = ROOT / 'dev/fixtures/publication_rules_0727063.py'
        exec(compile(source.read_text(), str(source), 'exec'), namespace)
        return namespace

    def test_existing_validator_decisions_match_frozen_oracle(self):
        legacy = self.legacy()
        cases = [
            ({'data_overview': {'version': 1, 'managed_files': ['latest.json', 'maps/weather/x.png']}}, tiny_png()),
            ({'data_overview': {'version': 1, 'managed_files': ['latest.json', '../x.json']}}, b'bad'),
            ({'data_overview': {'version': 2, 'managed_files': ['latest.json']}}, b'bad'),
            ({'data_overview': {'version': 1, 'managed_files': ['latest.json', 'latest.json']}}, b'bad'),
            ({}, b'bad'),
        ]
        for doc, image in cases:
            with self.subTest(doc=doc):
                write(self.root, {'latest.json': json.dumps(doc).encode(), 'history.json': b'{}',
                                  'maps/weather/x.png': image})
                previous = {'data_overview': {'version': 1, 'managed_files': ['latest.json', 'old.json']}}
                self.assertEqual(validate_data.plan(self.root, previous), legacy['plan'](self.root, previous))
        for payload in (b'{', b'{"x":NaN}', b'{"x":Infinity}'):
            (self.root / 'latest.json').write_bytes(payload)
            for func in (validate_data.plan, legacy['plan']):
                with self.assertRaises(ValueError):
                    func(self.root)

    def test_current_and_prior_reserved_paths_never_publish_or_delete(self):
        for path in ('section11/x.json', 'custom/preferences.json', 'Section11/x.png'):
            write(self.root, {'latest.json': json.dumps({'data_overview': {'version': 1, 'managed_files': ['latest.json', path]}}).encode(),
                              path: b'{}'})
            self.assertEqual(validate_data.plan(self.root)['mode'], 'legacy_fallback')
            (self.root / 'latest.json').write_text('{"data_overview":{"version":1,"managed_files":["latest.json"]}}')
            previous = {'data_overview': {'version': 1, 'managed_files': ['latest.json', path]}}
            self.assertEqual(validate_data.plan(self.root, previous)['removed'], [])

class PackagingTests(Offline):
    def test_zip_books_png_reconstruct_complete_manifest(self):
        raw, files = fixture()
        assets = release_package.build(raw, files, 'a' * 40, '2026.10.23')
        reconstructed = {release_package.IMAGE: assets['section11-2026.10.23-example-route-weather-map.png']}
        for kind in ('reference', 'tools'):
            header, decoded = release_package.decode_book(assets['section11-2026.10.23-' + kind + '.txt'])
            self.assertEqual(header['commit'], 'a' * 40)
            reconstructed.update(decoded)
        self.assertEqual(reconstructed, dict(files, **{'manifest.json': raw}))
        self.assertEqual(D.archive(assets['section11-2026.10.23.zip']), (raw, files))
        self.assertEqual(assets, release_package.build(raw, files, 'a' * 40, '2026.10.23'))

    def test_frame_truncation_and_unknown_binary_fail(self):
        raw, files = fixture()
        book = release_package.build(raw, files, 'a' * 40, '2026.10.23')['section11-2026.10.23-reference.txt']
        with self.assertRaises(ValueError):
            release_package.decode_book(book[:-10])
        bad = dict(files, **{'image.bin': b'\x00\xff'})
        with self.assertRaisesRegex(ValueError, 'unclassified'):
            release_package.build(manifest(bad), bad, 'a' * 40, '2026.10.23')

    def test_notes_include_protocol_and_old_digest_without_relabelling(self):
        _, files = fixture()
        notes = release_package.notes(files)
        self.assertIn('Fixture only.', notes)
        self.assertIn('Synthetic notice', notes)
        self.assertIn('may cover older releases', notes)

    def test_real_baseline_package_is_62_members(self):
        # Manifest bytes stay owner-controlled. Unchanged frozen file copies in
        # this candidate can only verify before modifications; the job-level
        # packaging check separately uses the supplied frozen baseline.
        frozen = ROOT / 'dev' / 'fixtures' / 'b1-legacy' / '7db221d8' / 'manifest.json'
        self.assertEqual(len(D.manifest(frozen.read_bytes())['files']) + 1, 62)


class ReleasePublishingTests(Offline):
    def test_complete_draft_upload_readback_publish_and_refused_second_release(self):
        from _release_fakes import ReleaseAPI
        raw, files = fixture()
        api = ReleaseAPI()
        api.manifests['a' * 40] = raw
        with mock.patch.object(publish_release, 'workflow_gate'), \
                mock.patch.object(publish_release, 'upload', api.upload), contextlib.redirect_stdout(io.StringIO()):
            publish_release.publish(api, 'a' * 40, raw, files, '2026.10.23')
            self.assertFalse(api.releases['2026.10.23']['draft'])
            self.assertEqual(len(api.assets), 4)
            self.assertEqual([w[:2] for w in api.writes if w[0] != 'UPLOAD'],
                             [('POST', '/git/refs'), ('POST', '/releases'), ('PATCH', '/releases/1')])
            # Same date, unchanged content: quiet no-op, never a second release.
            before = list(api.writes)
            self.assertEqual(publish_release.publish(api, 'a' * 40, raw, files, '2026.10.23'), 'unchanged')
            self.assertEqual(api.writes, before)

    def test_missing_upload_keeps_draft_and_never_publishes(self):
        from _release_fakes import ReleaseAPI
        raw, files = fixture()
        api = ReleaseAPI()
        api.seed('2026.10.23', 'a' * 40, raw, files, draft=True)
        with mock.patch.object(publish_release, 'workflow_gate'), \
                mock.patch.object(publish_release, 'ensure_tag'), \
                mock.patch.object(publish_release, 'upload', side_effect=RuntimeError('synthetic 502')), \
                self.assertRaisesRegex(RuntimeError, 'draft retained'):
            publish_release.publish(api, 'a' * 40, raw, files, '2026.10.23', resume=True)
        self.assertEqual(api.writes, [])

    def test_workflow_gate_matching_and_changed_default(self):
        api = mock.Mock()
        api.metadata.return_value = {'default_branch': 'main'}
        api.get.return_value = {'object': {'sha': 'b' * 40}}
        common = {'.github/workflows/release.yml': {'mode': '100644', 'sha': 'same'}}
        api.tree.return_value = common
        self.assertEqual(publish_release.workflow_gate(api, 'a' * 40), 'b' * 40)
        api.tree.side_effect = [common, {'.github/workflows/release.yml': {'mode': '100644', 'sha': 'changed'}}]
        with self.assertRaisesRegex(ValueError, 'differ'):
            publish_release.workflow_gate(api, 'a' * 40)

    def test_wrong_tag_never_moved(self):
        api = mock.Mock()
        api.resolve_tag.return_value = 'b' * 40
        with self.assertRaisesRegex(ValueError, 'never move'):
            publish_release.ensure_tag(api, 'v9000.0', 'a' * 40)
        api.write.assert_not_called()

    def test_incomplete_or_wrong_assets_fail_readback(self):
        api = mock.Mock()
        api.pages.return_value = []
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            publish_release.assets_readback(api, 1, {'a.txt': b'a'})
        api.pages.return_value = [{'name': 'a.txt', 'id': 1, 'size': 1, 'state': 'uploaded'}]
        api.asset.return_value = b'b'
        with self.assertRaisesRegex(ValueError, 'never overwrite'):
            publish_release.assets_readback(api, 1, {'a.txt': b'a'})
        api.asset.return_value = b'a'
        self.assertEqual(publish_release.assets_readback(api, 1, {'a.txt': b'a'})[1], {'a.txt'})




if __name__ == '__main__':
    unittest.main()
