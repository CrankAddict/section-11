"""R1-R4 regression evidence. HTTP is intercepted; all repository state is synthetic."""
import base64
import contextlib
import copy
import io
import json
import os
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from urllib.parse import parse_qs, unquote, urlparse

from test_update_prototype import (
    D, SYNC, ROOT, Offline, fixture, manifest, install, write, inventory,
    github_api, release_package)


class Response:
    def __init__(self, value=None, content=None, status=200):
        self.value = value
        self.content = content if content is not None else json.dumps(value).encode()
        self.status_code = status
        self.text = 'synthetic HTTP ' + str(status)

    def json(self):
        return self.value

    def raise_for_status(self):
        if self.status_code >= 400:
            raise SYNC.requests.HTTPError(self.text, response=self)

    def iter_content(self, size):
        yield self.content


class ReleaseHTTP:
    """An upstream with distinct releases, lightweight refs and no real transport."""
    def __init__(self, missed, missing_history=False, failure=None):
        self.calls = []
        self.missing_history = missing_history
        self.failure = failure
        self.tags = [(date(2026, 1, 1) + timedelta(days=i)).strftime('%Y.%m.%d') for i in range(missed + 1)]
        self.files = []
        self.raw = []
        self.commits = [format(i + 1, '040x') for i in range(missed + 1)]
        for i in range(missed + 1):
            files = dict(fixture()[1], LICENSE=('release ' + str(i)).encode())
            self.files.append(files)
            self.raw.append(manifest(files))

    def identity(self, i):
        return {'tag': self.tags[i], 'commit': self.commits[i], 'repository': D.UPSTREAM,
                'url': 'https://github.com/' + D.UPSTREAM + '/releases/tag/' + self.tags[i]}

    def archive(self, i):
        name = 'section11-' + self.tags[i] + '.zip'
        return release_package.build(self.raw[i], self.files[i], self.commits[i], self.tags[i])[name]

    def metadata(self, i):
        i %= len(self.tags)
        tag = self.tags[i]
        name = 'section11-' + tag + '.zip'
        return {'tag_name': tag, 'draft': False, 'prerelease': False, 'html_url': self.identity(i)['url'],
                'assets': [] if self.missing_history and i != len(self.tags) - 1 else [
                    {'name': name, 'id': i + 1, 'size': len(self.archive(i)),
                     'browser_download_url': 'https://github.com/' + D.UPSTREAM + '/releases/download/' + tag + '/' + name}]}

    def request(self, method, url, **kwargs):
        assert method == 'GET', 'unexpected mutation: ' + method
        assert 'Authorization' not in kwargs.get('headers', {}), 'upstream credential leak'
        self.calls.append(url)
        if self.failure:
            return Response(status=self.failure)
        parsed = urlparse(url)
        path = unquote(parsed.path)
        prefix = '/repos/' + D.UPSTREAM
        if parsed.netloc == 'api.github.com':
            assert path.startswith(prefix), url
            suffix = path[len(prefix):]
            if suffix == '/releases/latest':
                return Response(self.metadata(-1))
            if suffix == '/releases':
                page = int(parse_qs(parsed.query).get('page', ['1'])[0])
                rows = [self.metadata(i) for i in reversed(range(len(self.tags)))]
                return Response(rows[(page - 1) * 100:page * 100])
            if suffix.startswith('/releases/tags/'):
                return Response(self.metadata(self.tags.index(suffix.split('/')[-1])))
            if suffix.startswith('/git/ref/tags/'):
                i = self.tags.index(suffix.split('/')[-1])
                return Response({'object': {'type': 'commit', 'sha': self.commits[i]}})
            if suffix.startswith('/git/trees/'):
                i = self.commits.index(suffix.split('/')[-1])
                return Response({'truncated': False, 'tree': [
                    {'type': 'blob', 'path': 'manifest.json', 'mode': '100644', 'sha': 'blob-' + str(i)}]})
            if suffix.startswith('/git/blobs/blob-'):
                raw = self.raw[int(suffix.rsplit('-', 1)[1])]
                return Response({'encoding': 'base64', 'size': len(raw), 'content': base64.b64encode(raw).decode()})
            if suffix.startswith('/releases/assets/'):
                i = int(suffix.split('/')[-1]) - 1
                assert not (self.missing_history and i != len(self.tags) - 1), 'historical ZIP requested'
                return Response(content=self.archive(i))
        if parsed.netloc == 'raw.githubusercontent.com':
            assert path.endswith('/manifest.json'), url
            return Response(content=self.raw[self.commits.index(path.split('/')[-2])])
        if parsed.netloc == 'github.com' and '/releases/download/' in path:
            i = self.tags.index(path.split('/')[-2])
            assert not (self.missing_history and i != len(self.tags) - 1), 'historical ZIP requested'
            return Response(content=self.archive(i))
        raise AssertionError('unmatched HTTP: ' + url)

    @contextlib.contextmanager
    def intercepted(self):
        with mock.patch.object(SYNC.requests, 'get', lambda url, **kw: self.request('GET', url, **kw)), \
                mock.patch.object(SYNC.requests, 'request', self.request):
            yield self


def wrappers(root, files):
    write(root, {'.github/workflows/' + p: ('run: script --wrapper-api ' + str(v) + '\n').encode()
                 for p, v in json.loads(files['examples/maintenance/wrapper-api.json']).items()})


class RequestBudgetTests(Offline):
    def check_age(self, client, missed, missing=False):
        wire = ReleaseHTTP(missed, missing_history=missing)
        root = self.root / (client + str(missed) + str(missing))
        install(root / 'section11', wire.raw[0], wire.files[0])
        write(root / 'section11', {D.RECEIPT: D.receipt(wire.raw[0], wire.identity(0))})
        wrappers(root, wire.files[-1])
        before = inventory(root)
        with wire.intercepted(), contextlib.redirect_stdout(io.StringIO()), \
                mock.patch.dict(os.environ, {'GITHUB_REF': 'refs/heads/main'}), \
                mock.patch('builtins.input', side_effect=AssertionError('status prompted')):
            if client == 'local':
                with mock.patch.object(Path, 'cwd', return_value=root):
                    self.assertTrue(SYNC.do_update(status_only=True))
            else:
                from test_b2_hosted import Remote
                from direct_commit import DirectPublisher
                from hosted_update import HostedUpdater
                remote = Remote(inventory(root))
                publisher = DirectPublisher(remote)
                HostedUpdater(publisher, SYNC._fetch_verified_release, {}).status(publisher.snapshot())
                self.assertFalse(any(call[0] != 'GET' for call in remote.calls))
        self.assertEqual(inventory(root), before)
        count = len(wire.calls)
        expected = {'local': 5, 'github': 5}[client]
        self.assertEqual(count, expected, wire.calls)
        self.assertEqual(sum('/releases/download/' in u or '/releases/assets/' in u for u in wire.calls), 1)
        self.assertFalse(any('/releases?' in u for u in wire.calls))
        return count

    def test_0_1_10_100_missed_releases_have_fixed_request_budget(self):
        for missed in (0, 1, 10, 100):
            counts = []
            for client in ('local', 'github'):
                with self.subTest(client=client, missed=missed):
                    counts.append(self.check_age(client, missed))
            print('R1 measured missed=' + str(missed) + ' local=' + str(counts[0]) + ' github=' + str(counts[1]))

    def test_receipt_works_with_missing_historical_assets(self):
        for client in ('local', 'github'):
            with self.subTest(client=client):
                self.check_age(client, 100, missing=True)

    def test_403_429_stop_without_install_proposal_or_retry(self):
        for status in (403, 429):
            for client in ('local', 'github'):
                with self.subTest(status=status, client=client):
                    wire = ReleaseHTTP(1, failure=status)
                    root = self.root / (client + str(status))
                    install(root / 'section11', wire.raw[0], wire.files[0])
                    before = inventory(root)
                    output = io.StringIO()
                    api = mock.Mock(repo='owner/data')
                    api.metadata.return_value = {'default_branch': 'main'}
                    with wire.intercepted(), contextlib.redirect_stdout(output), \
                            mock.patch.dict(os.environ, {'GITHUB_REF': 'refs/heads/main'}):
                        if client == 'local':
                            with mock.patch.object(Path, 'cwd', return_value=root):
                                self.assertFalse(SYNC.do_update())
                            self.assertIn(str(status), output.getvalue())
                        else:
                            from test_b2_hosted import Remote
                            from direct_commit import DirectPublisher
                            from hosted_update import HostedUpdater
                            remote = Remote(inventory(root))
                            publisher = DirectPublisher(remote)
                            with self.assertRaisesRegex(SYNC.requests.HTTPError, str(status)):
                                HostedUpdater(publisher, SYNC._fetch_verified_release, {}).status(publisher.snapshot())
                            self.assertFalse(any(call[0] != 'GET' for call in remote.calls))
                    api.write.assert_not_called()
                    self.assertEqual(inventory(root), before)
                    self.assertEqual(len(wire.calls), 1)


class ProvenanceReceiptTests(Offline):
    def test_init_records_exact_verified_provenance(self):
        wire = ReleaseHTTP(0)
        with wire.intercepted(), mock.patch.object(Path, 'cwd', return_value=self.root), \
                mock.patch('builtins.input', return_value='y'), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(SYNC.do_init())
        self.assertEqual((self.root / 'section11' / D.RECEIPT).read_bytes(), D.receipt(wire.raw[0], wire.identity(0)))
        self.assertEqual(set(inventory(self.root / 'section11')), set(wire.files[0]) | {'manifest.json', D.RECEIPT})

    def test_unidentified_local_content_is_offered_for_explicit_acceptance(self):
        wire = ReleaseHTTP(2)
        install(self.root / 'section11', wire.raw[0], wire.files[0])
        before = inventory(self.root)
        with wire.intercepted(), mock.patch.object(Path, 'cwd', return_value=self.root), \
                mock.patch.object(SYNC, '__file__', str(self.root / 'section11/examples/sync.py')), \
                mock.patch('builtins.input', return_value='n') as confirm, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertFalse(SYNC.do_update())
        confirm.assert_called_once()
        self.assertIn('Installed release: unknown', output.getvalue())
        self.assertIn(SYNC.CONVERSION_WARNING, output.getvalue())
        self.assertEqual(inventory(self.root), before)

    def test_receipt_rejects_drift_foreign_source_and_malformed_collision(self):
        wire = ReleaseHTTP(1)
        install(self.root / 'section11', wire.raw[0], wire.files[0])
        for data in (b'{}', b'owner custom file', D.receipt(wire.raw[1], wire.identity(0)),
                     D.receipt(wire.raw[0], dict(wire.identity(0), repository='foreign/repo'))):
            with self.subTest(data=data):
                write(self.root / 'section11', {D.RECEIPT: data})
                with self.assertRaises(ValueError):
                    D.read_receipt(self.root / 'section11', wire.raw[0])

    def test_installation_changed_during_confirmation_is_preserved(self):
        wire = ReleaseHTTP(1)
        install(self.root / 'section11', wire.raw[0], wire.files[0])
        write(self.root / 'section11', {D.RECEIPT: D.receipt(wire.raw[0], wire.identity(0))})
        newer = dict(wire.files[1], LICENSE=b'newer concurrent update')
        newer_raw = manifest(newer)
        def confirm(prompt):
            install(self.root / 'section11', newer_raw, newer)
            write(self.root / 'section11', {D.RECEIPT: D.receipt(newer_raw, {'tag': '2026.01.03', 'commit': 'f' * 40})})
            return 'yes'
        with wire.intercepted(), mock.patch.object(Path, 'cwd', return_value=self.root), \
                mock.patch('builtins.input', confirm), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertFalse(SYNC.do_update())
        self.assertIn('installation changed after review', output.getvalue())
        self.assertEqual(D.tree(self.root / 'section11'), (newer_raw, newer))
        self.assertEqual(D.read_receipt(self.root / 'section11', newer_raw)['tag'], '2026.01.03')

    def test_date_downgrade_same_date_mutation_and_tag_move_refuse(self):
        wire = ReleaseHTTP(1)
        target = self.root / 'section11'
        install(target, wire.raw[1], wire.files[1])
        (target / D.RECEIPT).write_bytes(D.receipt(wire.raw[1], wire.identity(1)))
        with self.assertRaisesRegex(ValueError, 'date downgrade'):
            SYNC._local_release_status(target, wire.raw[0], wire.files[0], wire.identity(0))
        install(target, wire.raw[0], wire.files[0])
        (target / D.RECEIPT).write_bytes(D.receipt(wire.raw[0], wire.identity(0)))
        with self.assertRaisesRegex(ValueError, 'same-date'):
            SYNC._local_release_status(target, wire.raw[1], wire.files[1], wire.identity(0))
        with self.assertRaisesRegex(ValueError, 'same-date'):
            SYNC._local_release_status(target, wire.raw[0], wire.files[0],
                                       dict(wire.identity(0), commit='f' * 40))


# OfficialProposalValidationTests PR contracts are replaced by direct-commit acceptance in test_b2_hosted.py.


# WindowEligibilityTests PR contracts are replaced by direct-commit acceptance in test_b2_hosted.py.


# LifecycleTests PR contracts are replaced by direct-commit acceptance in test_b2_hosted.py.
