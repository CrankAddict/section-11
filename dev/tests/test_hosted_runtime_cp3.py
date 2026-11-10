"""CP3 trust and acquisition boundaries. All upstream responses are synthetic."""
import ast
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import urllib.error
import zipfile
from types import SimpleNamespace
from unittest import mock

from test_update_prototype import D, Offline, ROOT, fixture, manifest, write, inventory
from test_b2_hosted import Remote, DirectPublisher
import hosted
import hosted_update
import hosted_bootstrap
import hosted_runtime as R

spec = importlib.util.spec_from_file_location('cp3_gate', ROOT / 'dev/hosted_gate.py')
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


def zip_bytes(raw, files, *, extra=None, mode=stat.S_IFREG):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for p, data in dict(files, **{'manifest.json': raw}).items():
            info = zipfile.ZipInfo('section11/' + p)
            info.external_attr = (mode | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
        if extra:
            z.writestr(extra, b'extra')
    return out.getvalue()


class Upstream:
    """Serve through the real bounded transport, never a socket."""
    def __init__(self, releases):
        self.responses, self.calls, self.assets = {}, [], []
        for tag, commit, raw, files in releases:
            data = zip_bytes(raw, files)
            url = 'https://github.com/' + R.REPOSITORY + '/releases/download/' + tag + '/section11-' + tag + '.zip'
            self.responses[url] = data
            self.responses[R.API + R.PREFIX + '/releases/tags/' + tag] = json.dumps({
                'id': 1, 'tag_name': tag, 'draft': False, 'prerelease': False, 'published_at': '2026-11-09T12:00:00Z',
                'html_url': 'https://github.com/' + R.REPOSITORY + '/releases/tag/' + tag,
                'assets': [{'name': 'section11-' + tag + '.zip', 'size': len(data), 'browser_download_url': url}]}).encode()
            self.responses[R.API + R.PREFIX + '/git/ref/tags/' + tag] = json.dumps({'object': {'type': 'commit', 'sha': commit}}).encode()
            self.responses[R.RAW + commit + '/manifest.json'] = raw
            self.responses.update({R.RAW + commit + '/' + p: data for p, data in files.items()})
        self.transport = R.Transport('synthetic-job-token', opener=self)

    def open(self, request, timeout):
        self.calls.append((request.full_url, dict(request.header_items()), timeout))
        if '/releases/download/' in request.full_url:
            self.assets.append(request.full_url)
        body = self.responses[request.full_url]
        if callable(body):
            body = body()
        if isinstance(body, Exception):
            raise body
        return io.BytesIO(body)


class CP3(Offline):
    def setUp(self):
        super().setUp()
        self.addCleanup(mock.patch.stopall)
        mock.patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('unmatched network read')).start()
        self.checkout = self.root / 'checkout'
        self.temp = self.root / 'runner'
        self.checkout.mkdir()
        self.temp.mkdir()
        self.tag, self.commit = '2026.11.08', 'b' * 40
        self.selected = {'tag': '2026.11.09-2', 'commit': 'c' * 40}
        _, self.files = fixture('11.105')
        self.files['examples/maintenance/hosted.py'] = b'# old installed controller\n'
        self.raw = manifest(self.files)
        self.identity = {'tag': self.tag, 'commit': self.commit}
        self.upstream = Upstream([(self.tag, self.commit, self.raw, self.files)])
        self.install()

    def install(self):
        write(self.checkout / 'section11', dict(self.files, **{'manifest.json': self.raw,
                                                             R.RECEIPT: R.receipt(self.raw, self.identity)}))

    def acquire(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()) as log:
            result = R.acquire_application(self.upstream.transport, self.checkout, self.temp, self.selected, **kwargs)
        self.log = log.getvalue()
        return result

    def test_hit_exact_stage_and_unchanged_checkout(self):
        before = inventory(self.checkout)
        raw, files, identity = self.acquire()
        self.assertEqual((raw, files, identity['tag']), (self.raw, self.files, self.tag))
        self.assertEqual(self.upstream.assets, [])
        self.assertEqual(self.upstream.transport.requests, 4)
        self.assertEqual(inventory(self.checkout), before)
        self.assertEqual(inventory(self.temp / 'section11-trusted-source'), dict(self.files, **{
            'manifest.json': self.raw, R.RECEIPT: R.receipt(self.raw, self.identity)}))
        self.assertIn('acquisition hit', self.log)
        self.assertIn('requests=4; bytes=', self.log)

    def test_ordinary_miss_matrix_same_identity(self):
        for kind in ('edited', 'missing', 'crlf', 'extra', 'extra_directory', 'manifest', 'receipt', 'oversized'):
            with self.subTest(kind=kind):
                temp = self.root / ('runner-' + kind)
                temp.mkdir()
                checkout = self.root / ('data-' + kind)
                write(checkout / 'section11', inventory(self.checkout / 'section11'))
                managed = checkout / 'section11'
                target = managed / 'SECTION_11.md'
                if kind == 'edited': target.write_bytes(b'poisoned ordinary data')
                if kind == 'missing': target.unlink()
                if kind == 'crlf': target.write_bytes(target.read_bytes().replace(b'\n', b'\r\n'))
                if kind == 'extra': (managed / 'extra.py').write_bytes(b'raise AssertionError("do not execute")')
                if kind == 'extra_directory': (managed / 'unused').mkdir()
                if kind == 'manifest': (managed / 'manifest.json').write_bytes(b'{}')
                if kind == 'receipt': (managed / R.RECEIPT).write_bytes(R.receipt(self.raw, self.identity).strip())
                if kind == 'oversized':
                    with target.open('wb') as f: f.truncate(R.MAX_BYTES + 1)
                before = R.inventory(checkout)
                upstream = Upstream([(self.tag, self.commit, self.raw, self.files)])
                with contextlib.redirect_stdout(io.StringIO()):
                    result = R.acquire_application(upstream.transport, checkout, temp, self.selected)
                self.assertEqual(result[:2], (self.raw, self.files))
                self.assertEqual(result[2]['tag'], self.tag)
                self.assertEqual(len(upstream.assets), 1)
                self.assertIn(self.tag, upstream.assets[0])
                self.assertEqual(R.inventory(checkout), before)

    def test_missing_receipt_uses_known_control_identity(self):
        (self.checkout / 'section11' / R.RECEIPT).unlink()
        (self.checkout / '.section11-update.json').write_text(json.dumps({'installed_date': self.tag}))
        self.assertEqual(self.acquire()[2]['tag'], self.tag)
        self.assertEqual(len(self.upstream.assets), 1)

    def test_missing_identity_is_not_a_fresh_install(self):
        (self.checkout / 'section11' / R.RECEIPT).unlink()
        with self.assertRaisesRegex(ValueError, 'identity unavailable'):
            self.acquire()
        self.assertEqual(self.upstream.calls, [])

    def test_receipt_control_conflict_stops_before_fetch(self):
        (self.checkout / '.section11-update.json').write_text(json.dumps({'installed_date': '2026.11.07'}))
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            self.acquire()
        self.assertEqual(self.upstream.calls, [])

    def test_known_commit_and_manifest_conflicts_never_fall_back(self):
        for key, bad in (('commit', 'a' * 40), ('manifest_sha256', '0' * 64)):
            record = json.loads(R.receipt(self.raw, self.identity))
            record[key] = bad
            (self.checkout / 'section11' / R.RECEIPT).write_text(json.dumps(record))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'provenance changed'):
                self.acquire()
            self.assertEqual(self.upstream.assets, [])

    def test_moved_tag_after_copy_stops(self):
        endpoint = R.API + R.PREFIX + '/git/ref/tags/' + self.tag
        calls = 0
        def moving():
            nonlocal calls
            calls += 1
            return json.dumps({'object': {'type': 'commit', 'sha': self.commit if calls == 1 else 'd' * 40}}).encode()
        self.upstream.responses[endpoint] = moving
        with self.assertRaisesRegex(ValueError, 'tag moved'):
            self.acquire()
        self.assertEqual(self.upstream.assets, [])

    def test_bad_official_manifest_stops_without_asset(self):
        self.upstream.responses[R.RAW + self.commit + '/manifest.json'] = b'{"files":{},"files":{}}'
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.acquire()
        self.assertEqual(self.upstream.assets, [])

    def test_filesystem_hard_stops_even_on_forced_zip(self):
        for kind in ('symlink', 'hardlink', 'fifo', 'case', 'directory_case', 'path_alias'):
            with self.subTest(kind=kind):
                managed = self.root / ('unsafe-' + kind)
                write(managed / 'section11', inventory(self.checkout / 'section11'))
                target = managed / 'section11' / 'unsafe'
                if kind == 'symlink': target.symlink_to(managed / 'section11' / 'LICENSE')
                if kind == 'hardlink': os.link(managed / 'section11' / 'LICENSE', target)
                if kind == 'fifo': os.mkfifo(target)
                if kind == 'case': (managed / 'section11' / 'LICENSE').rename(managed / 'section11' / 'license')
                if kind == 'directory_case': (managed / 'section11' / 'examples').rename(managed / 'section11' / 'Examples')
                if kind == 'path_alias': (managed / 'section11' / 'trailing.').write_bytes(b'alias')
                with self.assertRaises(ValueError):
                    R.acquire_application(self.upstream.transport, managed, self.temp, self.selected, force=True)
                self.assertEqual(self.upstream.assets, [])

    def test_symlinked_root_stops(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.checkout, target_is_directory=True)
        with self.assertRaises(ValueError):
            R.acquire_application(self.upstream.transport, alias, self.temp, self.selected)

    def test_path_swap_during_read_stops(self):
        original = R.os.fstat
        target = self.checkout / 'section11' / 'LICENSE'
        changed = False
        def swapping(fd):
            nonlocal changed
            info = original(fd)
            if stat.S_ISREG(info.st_mode) and info.st_ino == target.stat().st_ino and not changed:
                changed = True
                target.rename(target.with_name('replaced'))
                target.write_bytes(b'replacement')
            return info
        with mock.patch.object(R.os, 'fstat', side_effect=swapping), self.assertRaisesRegex(ValueError, 'changed'):
            self.acquire()
        self.assertEqual(self.upstream.assets, [])

    def test_permission_and_storage_faults_are_hard_stops(self):
        # Simulate I/O failures without changing filesystem permissions.
        for function in ('read_file', 'write_file'):
            with self.subTest(function=function), mock.patch.object(R, function, side_effect=OSError('synthetic I/O refusal')):
                with self.assertRaises(OSError): self.acquire()
            self.assertEqual(self.upstream.assets, [])

    def test_unsafe_or_reused_stage_stops(self):
        target = self.temp / 'section11-trusted-source'
        target.symlink_to(self.checkout)
        with self.assertRaises(FileExistsError): self.acquire()
        target.unlink()
        target.mkdir(mode=0o755)
        os.chmod(target, 0o755)
        with self.assertRaisesRegex(ValueError, 'private'): R.check_stage(target)
        with self.assertRaises(FileExistsError): self.acquire()

    def test_stage_outside_checkout_is_required(self):
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            R.private_root(self.checkout, self.checkout)
        self.assertEqual(R.private_root(self.temp, self.checkout), self.temp)

    def test_intent_matrix(self):
        for operation, force, zip_required in [('Sync', False, False), ('Sync timer', False, False),
                                               ('Sync', True, True), ('Update', False, True),
                                               ('Status', False, True), ('Rollback', False, True)]:
            with self.subTest(operation=operation, force=force):
                temp = self.root / ('intent-' + operation + str(force))
                temp.mkdir()
                upstream = Upstream([(self.tag, self.commit, self.raw, self.files)])
                with contextlib.redirect_stdout(io.StringIO()):
                    value = R.acquire_application(upstream.transport, self.checkout, temp, self.selected, operation, force)
                self.assertEqual(bool(upstream.assets), zip_required)
                self.assertEqual(value[2]['tag'], self.tag)

    def test_fresh_install_full_zip(self):
        empty = self.root / 'empty'
        empty.mkdir()
        with contextlib.redirect_stdout(io.StringIO()):
            result = R.acquire_application(self.upstream.transport, empty, self.temp, self.identity)
        self.assertEqual(result[2]['tag'], self.tag)
        self.assertEqual(len(self.upstream.assets), 1)
        self.assertEqual(list(empty.iterdir()), [])

    def test_stage_phase_boundary_bytes_links_inventory_and_receipt(self):
        self.acquire()
        stage = self.temp / 'section11-trusted-source'
        original = (stage / 'LICENSE').read_bytes()
        (stage / 'LICENSE').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'hash'): R.read_stage(stage, self.raw, self.identity)
        (stage / 'LICENSE').write_bytes(original)
        (stage / 'extra.py').write_bytes(b'poison')
        with self.assertRaisesRegex(ValueError, 'inventory'): R.read_stage(stage, self.raw, self.identity)
        (stage / 'extra.py').unlink()
        (stage / 'LICENSE').unlink()
        (stage / 'LICENSE').symlink_to(self.checkout / 'section11' / 'LICENSE')
        with self.assertRaises(ValueError): R.read_stage(stage, self.raw, self.identity)
        (stage / 'LICENSE').unlink()
        (stage / 'LICENSE').write_bytes(original)
        (stage / R.RECEIPT).write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'identity'): R.read_stage(stage, self.raw, self.identity)

    def test_archive_integrity_inventory_types_and_raw_authority(self):
        good = zip_bytes(self.raw, self.files)
        self.assertEqual(R.archive(good, self.raw), self.files)
        for bad in (zip_bytes(self.raw, self.files, extra='section11/extra.py'),
                    zip_bytes(self.raw, self.files, mode=stat.S_IFLNK),
                    zip_bytes(self.raw, dict(self.files, LICENSE=b'poison')),
                    zip_bytes(b'{}', self.files)):
            with self.assertRaises(ValueError): R.archive(bad, self.raw)

    def test_unsupported_application_api_stops(self):
        bad = dict(self.files)
        bad['examples/maintenance/wrapper-api.json'] = b'{"auto-sync.yml":3}'
        with self.assertRaisesRegex(ValueError, 'API'): R.check_application_api(bad)

    def test_gate_poison_stops_before_execution_and_valid_neighbor_executes(self):
        entry = b'print("verified-canary")\n'
        raw = manifest({R.ENTRY: entry})
        with contextlib.redirect_stdout(io.StringIO()) as out:
            exec(compile(G.verify(raw, entry), '<synthetic>', 'exec'), {})
        self.assertEqual(out.getvalue(), 'verified-canary\n')
        for bad_raw, bad_entry in ((raw, b'print("poison")'), (manifest({R.ENTRY: b'other'}), entry),
                                   (b'{"files":{},"files":{}}', entry)):
            with contextlib.redirect_stdout(io.StringIO()) as out, self.assertRaises(ValueError):
                exec(compile(G.verify(bad_raw, bad_entry), '<synthetic>', 'exec'), {})
            self.assertEqual(out.getvalue(), '')

    def test_gate_path_schema_alias_and_hash_matrix(self):
        entry = b'pass\n'
        for path in ('../x', '/x', 'x\\y', 'C:x', '.github/x', 'dev/x', 'manifest.json',
                     'MANIFEST.JSON', 'examples/../x', 'x.', 'x ', 'x//y'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                G.verify(manifest({R.ENTRY: entry, path: b'x'}), entry)
        for pair in ({'A/x': b'a', 'a/y': b'b'}, {'x': b'a', 'x/y': b'b'}, {'A': b'a', 'a': b'b'},
                     {'caf\u00e9/x': b'a', 'cafe\u0301/y': b'b'}):
            with self.assertRaises(ValueError): G.verify(manifest(dict(pair, **{R.ENTRY: entry})), entry)
        for schema in (True, '1', 0, 3):
            value = json.loads(manifest({R.ENTRY: entry}))
            value['schema_version'] = schema
            with self.assertRaises(ValueError): G.verify(json.dumps(value).encode(), entry)
        value['schema_version'] = 2
        self.assertEqual(G.verify(json.dumps(value).encode(), entry), entry)
        value['files'][R.ENTRY]['hash'] = 'A' * 64
        with self.assertRaises(ValueError): G.verify(json.dumps(value).encode(), entry)

    def test_gate_static_no_network_or_writes(self):
        tree = ast.parse((ROOT / 'dev/hosted_gate.py').read_text())
        imports = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertEqual(imports, {'hashlib', 'json', 'os', 're', 'stat', 'sys', 'unicodedata'})
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        self.assertFalse(attrs & {'write', 'write_bytes', 'write_text', 'mkdir', 'unlink', 'rename', 'replace', 'O_WRONLY', 'O_RDWR', 'O_CREAT'})
        self.assertNotIn('open', names)

    def test_gate_ordinary_read_and_links(self):
        file = self.root / 'gate-input'
        file.write_bytes(b'bytes')
        self.assertEqual(G.read(file), b'bytes')
        alias = self.root / 'linked-input'
        os.link(file, alias)
        with self.assertRaises(ValueError): G.read(file)
        alias.unlink()
        alias.symlink_to(file)
        with self.assertRaises(OSError): G.read(alias)

    def test_initial_runtime_payload_all_verified_before_import(self):
        files = {p: (ROOT / p).read_bytes() for p in R.PAYLOAD + (R.ENTRY,)}
        raw = manifest(files)
        upstream = Upstream([(self.selected['tag'], self.selected['commit'], raw, files)])
        upstream.transport.token = ''
        checkout = self.root / 'fresh-checkout'
        checkout.mkdir()
        with mock.patch.object(R, 'load_controller', side_effect=AssertionError('early import')):
            with contextlib.redirect_stdout(io.StringIO()):
                stage = R.runtime_payload(self.temp, raw, files[R.ENTRY], self.selected,
                                          checkout=checkout, transport=upstream.transport)
        self.assertEqual(R.verify_runtime(self.temp, raw, files[R.ENTRY]), stage)
        self.assertEqual(len(upstream.calls), len(R.PAYLOAD))
        self.assertTrue(all('Authorization' not in h for _, h, _ in upstream.calls))
        for name in R.PAYLOAD:
            target = stage / name
            original = target.read_bytes()
            target.write_bytes(b'poison')
            with self.subTest(name=name), self.assertRaises(ValueError): R.verify_runtime(self.temp, raw, files[R.ENTRY])
            target.write_bytes(original)

    def test_bad_runtime_dependency_stops_without_import(self):
        files = {p: (ROOT / p).read_bytes() for p in R.PAYLOAD + (R.ENTRY,)}
        raw = manifest(files)
        upstream = Upstream([(self.selected['tag'], self.selected['commit'], raw, files)])
        upstream.responses[R.RAW + self.selected['commit'] + '/examples/maintenance/direct_commit.py'] = b'poison'
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            R.runtime_payload(self.temp, raw, files[R.ENTRY], self.selected,
                              checkout=self.checkout, transport=upstream.transport)

    def runtime_fixture(self):
        files = {p: ('# latest ' + p + '\n').encode() for p in R.PAYLOAD + (R.ENTRY,)}
        files['examples/maintenance/wrapper-api.json'] = b'{"auto-sync.yml":2}\n'
        raw = manifest(files)
        upstream = Upstream([(self.selected['tag'], self.selected['commit'], raw, files)])
        upstream.transport.token = ''
        return files, raw, upstream

    def test_runtime_steady_state_reuses_all_payload_without_raw_reads(self):
        files, raw, upstream = self.runtime_fixture()
        write(self.checkout / 'section11', dict(files, **{
            'manifest.json': raw, R.RECEIPT: R.receipt(raw, self.selected)}))
        before = inventory(self.checkout)
        with contextlib.redirect_stdout(io.StringIO()) as log, \
                mock.patch.object(R, 'load_controller', side_effect=AssertionError('early import')):
            stage = R.runtime_payload(self.temp, raw, files[R.ENTRY], self.selected,
                                      checkout=self.checkout, transport=upstream.transport)
        self.assertEqual(upstream.calls, [])
        self.assertEqual((upstream.transport.requests, upstream.transport.bytes), (0, 0))
        self.assertIn('reused=8; fetched=0; requests=0; bytes=0', log.getvalue())
        self.assertEqual(inventory(stage), files)
        self.assertEqual(inventory(self.checkout), before)

    def test_runtime_ordinary_miss_fetches_only_that_file(self):
        target_name = 'examples/sync.py'
        for kind in ('edited', 'missing', 'crlf', 'oversized'):
            with self.subTest(kind=kind):
                files, raw, upstream = self.runtime_fixture()
                checkout, temp = self.root / ('reuse-' + kind), self.root / ('runtime-' + kind)
                write(checkout / 'section11', files)
                temp.mkdir()
                target = checkout / 'section11' / target_name
                if kind == 'edited': target.write_bytes(b'edited')
                if kind == 'missing': target.unlink()
                if kind == 'crlf': target.write_bytes(files[target_name].replace(b'\n', b'\r\n'))
                if kind == 'oversized':
                    with target.open('wb') as handle: handle.truncate(R.MAX_BYTES + 1)
                with contextlib.redirect_stdout(io.StringIO()) as log:
                    stage = R.runtime_payload(temp, raw, files[R.ENTRY], self.selected,
                                              checkout=checkout, transport=upstream.transport)
                self.assertEqual([url for url, _, _ in upstream.calls],
                                 [R.RAW + self.selected['commit'] + '/' + target_name])
                self.assertEqual(upstream.transport.bytes, len(files[target_name]))
                self.assertIn('reused=7; fetched=1; requests=1; bytes=', log.getvalue())
                self.assertEqual(inventory(stage), files)

    def test_runtime_half_mode_fetches_only_changed_latest_files(self):
        files, raw, upstream = self.runtime_fixture()
        older = dict(files)
        changed = ('examples/maintenance/hosted.py', 'examples/maintenance/direct_commit.py')
        for name in changed:
            older[name] = b'# older release\n'
        older.pop(R.ENTRY)
        old_raw = manifest(older)
        write(self.checkout / 'section11', dict(older, **{
            'manifest.json': old_raw, R.RECEIPT: R.receipt(old_raw, self.identity)}))
        before = inventory(self.checkout)
        with contextlib.redirect_stdout(io.StringIO()) as log:
            stage = R.runtime_payload(self.temp, raw, files[R.ENTRY], self.selected,
                                      checkout=self.checkout, transport=upstream.transport)
        self.assertEqual([url for url, _, _ in upstream.calls],
                         [R.RAW + self.selected['commit'] + '/' + name for name in changed])
        self.assertEqual(upstream.transport.bytes, sum(len(files[name]) for name in changed))
        self.assertIn('reused=6; fetched=2; requests=2; bytes=', log.getvalue())
        self.assertEqual(inventory(stage), files)
        self.assertEqual(inventory(self.checkout), before)

    def test_runtime_unsafe_checkout_stops_without_raw_fallback(self):
        for kind in ('symlink', 'parent_symlink', 'root_symlink', 'hardlink', 'fifo', 'case', 'directory_case'):
            with self.subTest(kind=kind):
                files, raw, upstream = self.runtime_fixture()
                checkout = self.root / ('runtime-unsafe-' + kind)
                managed = checkout / 'section11'
                write(managed, files)
                target = managed / 'examples/sync.py'
                if kind in ('symlink', 'hardlink', 'fifo'):
                    target.unlink()
                    other = managed / 'examples/maintenance/hosted.py'
                    if kind == 'symlink': target.symlink_to(other)
                    if kind == 'hardlink': os.link(other, target)
                    if kind == 'fifo': os.mkfifo(target)
                if kind == 'parent_symlink':
                    (managed / 'examples').rename(checkout / 'parked')
                    (managed / 'examples').symlink_to(checkout / 'parked', target_is_directory=True)
                if kind == 'root_symlink':
                    managed.rename(checkout / 'parked')
                    managed.symlink_to(checkout / 'parked', target_is_directory=True)
                if kind == 'case': target.rename(target.with_name('Sync.py'))
                if kind == 'directory_case': (managed / 'examples').rename(managed / 'Examples')
                with self.assertRaises(ValueError):
                    R.runtime_payload(self.temp, raw, files[R.ENTRY], self.selected,
                                      checkout=checkout, transport=upstream.transport)
                self.assertEqual(upstream.calls, [])

    def test_runtime_active_file_swap_stops_without_raw_fallback(self):
        files, raw, upstream = self.runtime_fixture()
        write(self.checkout / 'section11', files)
        target = self.checkout / 'section11' / 'examples/sync.py'
        original = R.os.fstat
        changed = False
        def swapping(fd):
            nonlocal changed
            info = original(fd)
            if stat.S_ISREG(info.st_mode) and info.st_ino == target.stat().st_ino and not changed:
                changed = True
                target.rename(target.with_name('replaced'))
                target.write_bytes(files['examples/sync.py'])
            return info
        with mock.patch.object(R.os, 'fstat', side_effect=swapping), self.assertRaisesRegex(ValueError, 'changed'):
            R.runtime_payload(self.temp, raw, files[R.ENTRY], self.selected,
                              checkout=self.checkout, transport=upstream.transport)
        self.assertTrue(changed)
        self.assertEqual(upstream.calls, [])

    def test_runtime_active_tree_change_between_reads_stops(self):
        for kind in ('root_swap', 'missing_file', 'new_file'):
            with self.subTest(kind=kind):
                files, raw, upstream = self.runtime_fixture()
                checkout, temp = self.root / ('swap-' + kind), self.root / ('stage-' + kind)
                managed = checkout / 'section11'
                write(managed, files)
                temp.mkdir()
                original = R.read_file
                changed = False
                def changing(root, name, *args, **kwargs):
                    nonlocal changed
                    data = original(root, name, *args, **kwargs)
                    if Path(root) == managed and not changed:
                        changed = True
                        if kind == 'root_swap':
                            managed.rename(checkout / 'parked')
                            write(managed, files)
                        if kind == 'missing_file': (managed / R.PAYLOAD[1]).unlink()
                        if kind == 'new_file': (managed / 'new-file').write_bytes(b'new')
                    return data
                with mock.patch.object(R, 'read_file', side_effect=changing), self.assertRaises(ValueError):
                    R.runtime_payload(temp, raw, files[R.ENTRY], self.selected,
                                      checkout=checkout, transport=upstream.transport)
                self.assertTrue(changed)
                self.assertEqual(upstream.calls, [])

    def test_runtime_io_faults_stop_without_raw_fallback(self):
        files, raw, upstream = self.runtime_fixture()
        write(self.checkout / 'section11', files)
        for function in ('read_file', 'write_file'):
            with self.subTest(function=function):
                temp = self.root / ('io-' + function)
                temp.mkdir()
                with mock.patch.object(R, function, side_effect=OSError('synthetic I/O refusal')), \
                        self.assertRaises(OSError):
                    R.runtime_payload(temp, raw, files[R.ENTRY], self.selected,
                                      checkout=self.checkout, transport=upstream.transport)
                self.assertEqual(upstream.calls, [])

    def test_runtime_latest_is_selected_once_and_suffix_enabled_only_by_handoff(self):
        selected = self.identity
        runtime = R.Runtime(self.upstream.transport, selected, self.raw)
        self.assertEqual(runtime.latest()[2]['tag'], self.tag)
        count = len(self.upstream.calls)
        runtime.latest()
        self.assertEqual(len(self.upstream.calls), count)
        self.assertFalse(any('/latest' in url for url, _, _ in self.upstream.calls))
        old = hosted_update.HostedUpdater(mock.Mock(), mock.Mock(), {'SECTION11_SUFFIX_CAPABLE': 'true'})
        self.assertFalse(old.suffix_capable)
        with self.assertRaises(ValueError): old.require_capability('2026.11.09-2')

    def test_half_mode_real_controller_uses_older_application_and_latest_updater(self):
        source = self.temp / 'section11-trusted-source'
        app = self.acquire()
        write(self.checkout, {'.github/workflows/auto-sync.yml': b"on:\n  schedule:\n    - cron: '7 */3 * * *'\n"})
        remote_files = inventory(self.checkout)
        remote = Remote(remote_files)
        pub = DirectPublisher(remote)
        state = hosted_update.control(None)
        state['installed_date'] = self.tag
        before = pub.snapshot()
        info = {'event': 'workflow_dispatch', 'created_at': '2026-11-09T12:00:00Z', 'attempt': 1, 'operation': 'Sync', 'cron': ''}
        runtime = SimpleNamespace(latest=mock.Mock(side_effect=AssertionError('no upgrade during prepare')))
        env = {'GITHUB_WORKSPACE': str(self.checkout), 'GITHUB_EVENT_PATH': str(self.root / 'event.json'), 'SECTION11_AUTO_UPDATE': 'false'}
        (self.root / 'event.json').write_bytes(b'{}')
        with mock.patch.dict(os.environ, env), mock.patch.object(hosted, 'publisher', return_value=pub), \
                mock.patch.object(hosted, 'trigger', return_value=info), \
                mock.patch.object(hosted, 'context') as context, mock.patch.object(hosted, 'output'), \
                mock.patch.object(hosted.update, 'HostedUpdater', wraps=hosted_update.HostedUpdater) as constructor:
            hosted.prepare(source, app, SimpleNamespace(Distribution=D), runtime=runtime,
                           argv=['--wrapper-api', '2', '--accept-install'])
        self.assertIs(constructor.call_args.kwargs['suffix_capable'], True)
        self.assertEqual(context.call_args.args[0]['source_identity']['tag'], self.tag)
        self.assertEqual(context.call_args.args[0]['source'], str(source))
        self.assertEqual(pub.snapshot()['commit'], before['commit'])
        runtime.latest.assert_not_called()

    def test_real_producer_launch_strips_tokens_and_git_config(self):
        info = {'source': str(self.temp / 'section11-trusted-source'), 'run_sync': True,
                'operation': 'Sync', 'event': 'workflow_dispatch', 'cron': ''}
        env = {'GITHUB_TOKEN': 'synthetic-publication', 'GH_TOKEN': 'synthetic-cli',
               'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'x', 'GIT_CONFIG_VALUE_0': 'secret',
               'ATHLETE_ID': 'fixture-athlete', 'INTERVALS_KEY': 'fixture-key', 'GITHUB_WORKSPACE': str(self.checkout)}
        with mock.patch.dict(os.environ, env), mock.patch.object(hosted, 'context', return_value=info), \
                mock.patch.object(hosted.subprocess, 'run') as launch, mock.patch.object(hosted, 'finalize_export'), \
                contextlib.redirect_stdout(io.StringIO()):
            hosted.run_sync(isolated=True)
        child = launch.call_args.kwargs['env']
        self.assertFalse(any(k in ('GITHUB_TOKEN', 'GH_TOKEN') or k.startswith('GIT_CONFIG') for k in child))
        self.assertEqual(launch.call_args.args[0][1:4], ['-I', '-B', info['source'] + '/examples/sync.py'])
        self.assertEqual(child['INTERVALS_KEY'], 'fixture-key')

    def test_old_entry_with_new_controller_preserves_default_capability(self):
        source = self.temp / 'section11-trusted-source'
        source.mkdir()
        event = self.root / 'event.json'
        event.write_bytes(b'{}')
        pub = mock.Mock()
        pub.snapshot.return_value = {'entries': {}}
        updater = mock.Mock()
        updater.state.return_value = hosted_update.control(None)
        with mock.patch.dict(os.environ, {'GITHUB_WORKSPACE': str(self.checkout), 'GITHUB_EVENT_PATH': str(event)}), \
                mock.patch.object(hosted, 'publisher', return_value=pub), mock.patch.object(hosted, 'trigger', return_value={'operation': 'Status'}), \
                mock.patch.object(hosted, 'check_checkout'), mock.patch.object(hosted.update, 'installed_identity', return_value=None), \
                mock.patch.object(hosted.update, 'HostedUpdater', return_value=updater) as constructor, \
                mock.patch.object(hosted, 'output'), mock.patch.object(sys, 'argv', ['old-entry', '--wrapper-api', '2', '--accept-install']), \
                contextlib.redirect_stdout(io.StringIO()), mock.patch.object(hosted.json, 'dumps', return_value='{}'):
            hosted.prepare(source, (self.raw, self.files, self.identity), SimpleNamespace(Distribution=D))
        self.assertNotIn('suffix_capable', constructor.call_args.kwargs)
        updater.status.assert_called_once()

    def test_transport_token_only_official_api_and_body_bounds(self):
        self.acquire()
        for url, headers, timeout in self.upstream.calls:
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 30)
            self.assertEqual('Authorization' in headers, url.startswith(R.API + '/'))
        oversized = SimpleNamespace(open=mock.Mock(return_value=io.BytesIO(b'12345')))
        t = R.Transport('synthetic', opener=oversized)
        with self.assertRaisesRegex(ValueError, 'byte/time'): t.read(R.RAW + self.commit + '/x', 4, 'raw')
        self.assertEqual(oversized.open.call_count, 1)

    def test_transport_redirect_policy_and_one_attempt(self):
        url = R.API + R.PREFIX + '/git/ref/tags/' + self.tag
        same = R.API + R.PREFIX + '/git/refs/tags/' + self.tag
        def redirect(destination):
            return urllib.error.HTTPError(url, 302, 'synthetic', {'Location': destination}, io.BytesIO())
        opener = SimpleNamespace(open=mock.Mock(side_effect=[redirect(same), io.BytesIO(b'{}')]))
        t = R.Transport('synthetic', opener=opener)
        self.assertEqual(t.read(url, 100, 'api'), b'{}')
        self.assertTrue(all(c.args[0].get_header('Authorization') == 'Bearer synthetic' for c in opener.open.call_args_list))
        for destination in ('https://raw.githubusercontent.com/x', 'http://api.github.com/x', 'https://api.github.com.evil/x',
                            'https://api.github.com/repos/other/repo/x'):
            opener.open = mock.Mock(side_effect=redirect(destination))
            with self.assertRaises(ValueError): R.Transport('synthetic', opener=opener).read(url, 100, 'api')
            self.assertEqual(opener.open.call_count, 1)
        for code in (401, 403, 404, 429, 503):
            opener.open = mock.Mock(side_effect=urllib.error.HTTPError(url, code, 'refused', {}, io.BytesIO()))
            with self.assertRaisesRegex(ValueError, 'HTTP ' + str(code)):
                R.Transport('synthetic', opener=opener).read(url, 100, 'api')
            self.assertEqual(opener.open.call_count, 1)

    def test_transport_timeout_and_request_bound_have_no_retry(self):
        opener = SimpleNamespace(open=mock.Mock(side_effect=TimeoutError('synthetic timeout')))
        t = R.Transport('', opener=opener)
        with self.assertRaises(ValueError): t.read(R.RAW + self.commit + '/x', 10, 'raw')
        self.assertEqual(opener.open.call_count, 1)
        t.requests = 64
        with self.assertRaisesRegex(ValueError, 'bound'): t.read(R.RAW + self.commit + '/x', 10, 'raw')
        self.assertEqual(opener.open.call_count, 1)

    def test_history_size_does_not_increase_reads(self):
        counts = []
        for history in (5, 500):
            temp = self.root / ('history-' + str(history))
            temp.mkdir()
            upstream = Upstream([(self.tag, self.commit, self.raw, self.files)])
            upstream.responses[R.API + R.PREFIX + '/releases'] = json.dumps([{'id': i} for i in range(history)]).encode()
            with contextlib.redirect_stdout(io.StringIO()):
                R.acquire_application(upstream.transport, self.checkout, temp, self.selected)
            counts.append((upstream.transport.requests, upstream.transport.bytes))
        self.assertEqual(counts[0], counts[1])
        self.assertEqual(counts[0][0], 4)

    def test_manifest_generator_and_packager_include_runtime_exclude_gate(self):
        import release_package
        import distribution
        self.assertIn('dev', distribution._sync._MANIFEST_EXCLUDE_ROOT_DIRS)
        self.assertNotIn('examples', distribution._sync._MANIFEST_EXCLUDE_ROOT_DIRS)
        files = dict(self.files)
        files[R.ENTRY] = (ROOT / R.ENTRY).read_bytes()
        raw = manifest(files)
        assets = release_package.build(raw, files, self.commit, self.tag)
        actual = R.archive(assets['section11-' + self.tag + '.zip'], raw)
        self.assertEqual(actual[R.ENTRY], files[R.ENTRY])
        self.assertNotIn('dev/hosted_gate.py', actual)

    def test_isolated_import_uses_verified_payload_not_checkout_poison(self):
        files = {p: (ROOT / p).read_bytes() for p in R.PAYLOAD + (R.ENTRY,)}
        raw = manifest(files)
        upstream = Upstream([(self.selected['tag'], self.selected['commit'], raw, files)])
        with contextlib.redirect_stdout(io.StringIO()):
            R.runtime_payload(self.temp, raw, files[R.ENTRY], self.selected,
                              checkout=self.checkout, transport=upstream.transport)
        write(self.checkout, {name: b'raise AssertionError("checkout import executed")\n'
                              for name in ('requests.py', 'distribution.py', 'hosted.py', 'json.py', 'sitecustomize.py')})
        program = ('import importlib.util, pathlib; '
                   'p=pathlib.Path(' + repr(str(ROOT / R.ENTRY)) + '); '
                   's=importlib.util.spec_from_file_location("runtime",p); '
                   'r=importlib.util.module_from_spec(s); s.loader.exec_module(r); '
                   'c=r.load_controller(pathlib.Path(' + repr(str(self.temp / 'section11-runtime')) + ')); '
                   'assert c.WRAPPER_API==2; '
                   'assert str(c._sync.__file__).startswith(' + repr(str(self.temp / 'section11-runtime')) + '); '
                   'print("verified imports only")')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', program], cwd=self.checkout,
                                env=dict(os.environ, PYTHONPATH=str(self.checkout)), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'verified imports only')

    def test_main_phase_recheck_precedes_import_and_strips_environment(self):
        entry = b'pass\n'
        raw = manifest({R.ENTRY: entry})
        args = ['gate', 'sync', '--wrapper-api', '2', '--tag', self.selected['tag'], '--commit', self.selected['commit'],
                '--manifest-sha256', R.digest(raw)]
        def refused(*args):
            self.assertFalse(any(k in ('GH_TOKEN', 'GITHUB_TOKEN') or k.startswith('GIT_CONFIG') for k in os.environ))
            raise ValueError('synthetic changed runtime')
        env = {'RUNNER_TEMP': str(self.temp), 'GITHUB_WORKSPACE': str(self.checkout),
               'GH_TOKEN': 'synthetic-cli', 'GITHUB_TOKEN': 'synthetic-job', 'GIT_CONFIG_COUNT': '1'}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(sys, 'argv', args), \
                mock.patch.dict(R.__dict__, {'OFFICIAL_MANIFEST': raw, 'VERIFIED_ENTRY': entry}), \
                mock.patch.object(R, 'verify_runtime', side_effect=refused), mock.patch.object(R, 'load_controller') as load:
            with self.assertRaisesRegex(ValueError, 'changed runtime'): R.main()
            load.assert_not_called()

    def test_main_unsupported_api_and_bootstrap_credentials_stop_before_payload(self):
        raw, entry = manifest({R.ENTRY: b'pass'}), b'pass'
        args = ['gate', 'bootstrap', '--wrapper-api', '3', '--tag', self.tag, '--commit', self.commit]
        env = {'RUNNER_TEMP': str(self.temp), 'GITHUB_WORKSPACE': str(self.checkout), 'GH_TOKEN': 'synthetic'}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(sys, 'argv', args), \
                mock.patch.dict(R.__dict__, {'OFFICIAL_MANIFEST': raw, 'VERIFIED_ENTRY': entry}), \
                mock.patch.object(R, 'runtime_payload') as payload:
            with self.assertRaisesRegex(ValueError, 'API'): R.main()
            args[3] = '2'
            with self.assertRaisesRegex(ValueError, 'token-free'): R.main()
            payload.assert_not_called()

    def test_annotation_cycles_depth_and_valid_chain(self):
        url = R.API + R.PREFIX + '/git/ref/tags/' + self.tag
        sha = 'a' * 40
        self.upstream.responses[url] = json.dumps({'object': {'type': 'tag', 'sha': sha}}).encode()
        tag_url = R.API + R.PREFIX + '/git/tags/' + sha
        self.upstream.responses[tag_url] = json.dumps({'object': {'type': 'commit', 'sha': self.commit}}).encode()
        self.assertEqual(self.upstream.transport.resolve(self.tag), self.commit)
        self.upstream.responses[tag_url] = self.upstream.responses[url]
        with self.assertRaisesRegex(ValueError, 'unresolved'): self.upstream.transport.resolve(self.tag)
        for i, next_sha in enumerate(('d' * 40, 'e' * 40, 'f' * 40, self.commit)):
            current = ('a' * 40, 'd' * 40, 'e' * 40, 'f' * 40)[i]
            self.upstream.responses[R.API + R.PREFIX + '/git/tags/' + current] = json.dumps({
                'object': {'type': 'tag' if i < 3 else 'commit', 'sha': next_sha}}).encode()
        self.assertEqual(self.upstream.transport.resolve(self.tag), self.commit)
        fifth = '9' * 40
        self.upstream.responses[R.API + R.PREFIX + '/git/tags/' + 'f' * 40] = json.dumps({
            'object': {'type': 'tag', 'sha': fifth}}).encode()
        with self.assertRaisesRegex(ValueError, 'unresolved'): self.upstream.transport.resolve(self.tag)
        self.assertFalse(any('/git/tags/' + fifth in call[0] for call in self.upstream.calls))

    def test_asset_redirect_never_receives_token_raw_redirect_refused(self):
        url = 'https://github.com/' + R.REPOSITORY + '/releases/download/' + self.tag + '/section11-' + self.tag + '.zip'
        redirect = urllib.error.HTTPError(url, 302, 'synthetic', {'Location': 'https://release-assets.githubusercontent.com/fixed'}, io.BytesIO())
        opener = SimpleNamespace(open=mock.Mock(side_effect=[redirect, io.BytesIO(b'asset')]))
        self.assertEqual(R.Transport('synthetic', opener=opener).read(url, 100, 'asset'), b'asset')
        self.assertTrue(all(c.args[0].get_header('Authorization') is None for c in opener.open.call_args_list))
        raw_url = R.RAW + self.commit + '/manifest.json'
        opener.open = mock.Mock(side_effect=urllib.error.HTTPError(raw_url, 302, 'synthetic', {'Location': raw_url + '?x=1'}, io.BytesIO()))
        with self.assertRaisesRegex(ValueError, 'redirect'): R.Transport('synthetic', opener=opener).read(raw_url, 100, 'raw')
        self.assertEqual(opener.open.call_count, 1)

    def test_bounded_metadata_missing_asset_and_invalid_release_stop(self):
        url = R.API + R.PREFIX + '/releases/tags/' + self.tag
        original = json.loads(self.upstream.responses[url])
        for field, value in (('assets', []), ('draft', True), ('prerelease', True), ('tag_name', '2026.11.07'),
                             ('html_url', 'https://example.invalid/release')):
            bad = dict(original, **{field: value})
            self.upstream.responses[url] = json.dumps(bad).encode()
            with self.subTest(field=field), self.assertRaises(ValueError): self.acquire()
            self.assertEqual(self.upstream.assets, [])

    def test_all_later_phases_refuse_changed_application_before_dispatch(self):
        self.acquire()
        (self.temp / 'section11-trusted-source' / 'LICENSE').write_bytes(b'changed after prepare')
        raw, entry = manifest({R.ENTRY: b'pass'}), b'pass'
        controller = mock.Mock()
        transport = mock.Mock()
        transport.resolve.return_value = self.selected['commit']
        env = {'RUNNER_TEMP': str(self.temp), 'GITHUB_WORKSPACE': str(self.checkout), 'GITHUB_TOKEN': 'synthetic'}
        for phase in R.PHASES[2:]:
            args = ['gate', phase, '--wrapper-api', '2', '--tag', self.selected['tag'], '--commit', self.selected['commit'],
                    '--manifest-sha256', R.digest(raw), '--application-tag', self.tag, '--application-commit', self.commit,
                    '--application-sha256', R.digest(self.raw)]
            with self.subTest(phase=phase), mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch.object(sys, 'argv', args), mock.patch.dict(R.__dict__, {'OFFICIAL_MANIFEST': raw, 'VERIFIED_ENTRY': entry}), \
                    mock.patch.object(R, 'verify_runtime', return_value=self.temp), mock.patch.object(R, 'load_controller', return_value=controller), \
                    mock.patch.object(R, 'Transport', return_value=transport):
                with self.assertRaisesRegex(ValueError, 'hash mismatch'): R.main()
                self.assertEqual(controller.mock_calls, [])

    def test_gate_executes_already_read_bytes_despite_path_swap(self):
        base = self.temp / 'section11-entry'
        base.mkdir(mode=0o700)
        entry = b'print("exact verified bytes")\n'
        (base / 'manifest.json').write_bytes(manifest({R.ENTRY: entry}))
        (base / 'hosted_runtime.py').write_bytes(entry)
        verify = G.verify
        def swap(raw, data):
            result = verify(raw, data)
            (base / 'hosted_runtime.py').write_bytes(b'raise AssertionError("reopened entry")')
            return result
        with mock.patch.dict(os.environ, {'RUNNER_TEMP': str(self.temp), 'GITHUB_WORKSPACE': str(self.checkout)}), \
                mock.patch.object(sys, 'argv', ['gate', 'bootstrap']), mock.patch.object(G, 'verify', side_effect=swap), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            G.main()
        self.assertEqual(output.getvalue(), 'exact verified bytes\n')

    def test_old_v11105_bootstrap_reaches_new_controller(self):
        # Run the staged legacy entry itself. Its historical verifier transport
        # is replaced by the supplied offline verifier, not fetched from GitHub.
        import distribution
        files = dict(self.files, **{p: (ROOT / p).read_bytes() for p in R.PAYLOAD + (R.ENTRY,)})
        raw = manifest(files)
        empty = self.root / 'legacy-checkout'
        empty.mkdir()
        event = self.root / 'legacy-event.json'
        event.write_bytes(b'{}')
        env = {'RUNNER_TEMP': str(self.temp), 'GITHUB_WORKSPACE': str(empty), 'GITHUB_EVENT_PATH': str(event),
               'GITHUB_TOKEN': 'synthetic', 'SECTION11_DEFAULT_BRANCH': 'main'}
        real_spec = importlib.util.spec_from_file_location
        reached = []
        def controller_spec(name, path):
            result = real_spec(name, path)
            execute = result.loader.exec_module
            def run(module):
                execute(module)
                if name == 'section11_verified_hosted':
                    original = module.prepare
                    def prepare(*args, **kwargs):
                        reached.append((args[1], kwargs))
                        return original(*args, **kwargs)
                    module.prepare = prepare
                    pub = mock.Mock()
                    pub.api.repo = 'synthetic/data'
                    pub.default = 'main'
                    pub.snapshot.return_value = {'entries': {}}
                    pub.read.return_value = None
                    module.publisher = lambda: pub
                    module.trigger = lambda *args: {'operation': 'Status'}
                    module.check_checkout = lambda *args: None
                    module.output = lambda **kwargs: None
            result.loader.exec_module = run
            return result
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(sys, 'path', list(sys.path)), \
                mock.patch.object(sys, 'argv', ['old-entry', '--wrapper-api', '2', '--accept-install']), \
                mock.patch.object(hosted_bootstrap, 'pinned_verifier', return_value=distribution._sync), \
                mock.patch.object(D, 'fetch', return_value=(raw, files, self.identity)), \
                mock.patch.object(importlib.util, 'spec_from_file_location', side_effect=controller_spec), \
                contextlib.redirect_stdout(io.StringIO()):
            hosted_bootstrap.main()
        self.assertEqual(len(reached), 1)
        self.assertEqual(reached[0][0][0], raw)
        self.assertEqual(reached[0][1], {})
        self.assertEqual((self.temp / 'section11-trusted-source' / R.ENTRY).read_bytes(), files[R.ENTRY])

    def test_maintenance_handoff_uses_native_allowance_and_retains_capability(self):
        snapshot = {'commit': 'd' * 40, 'entries': {}}
        pub = mock.Mock()
        pub.snapshot.return_value = snapshot
        updater = mock.Mock()
        updater.maintain.return_value = (snapshot, None)
        info = {'published': True, 'base': 'd' * 40, 'created_at': '2026-11-09T12:00:00Z',
                'event': 'workflow_dispatch', 'attempt': 1, 'scheduled': False, 'source_is_latest': False}
        runtime = SimpleNamespace(latest=mock.Mock())
        with mock.patch.object(hosted, 'context', side_effect=[info, None]), mock.patch.object(hosted, 'publisher', return_value=pub), \
                mock.patch.object(hosted, 'maintenance_due', return_value=True), \
                mock.patch.object(hosted.update, 'HostedUpdater', return_value=updater) as constructor:
            hosted.maintain(runtime=runtime)
        self.assertEqual(constructor.call_args.args[1], runtime.latest)
        self.assertIs(constructor.call_args.kwargs['suffix_capable'], True)
        self.assertEqual(updater.maintain.call_args.args[::2], (snapshot, True))
        self.assertIs(updater.maintain.call_args.kwargs['claim_attempt'], False)

    def test_transport_elapsed_and_total_byte_caps_stop_without_restart(self):
        opener = SimpleNamespace(open=mock.Mock(return_value=io.BytesIO(b'x')))
        transport = R.Transport(opener=opener)
        transport.deadline = 0
        with self.assertRaisesRegex(ValueError, 'bound'): transport.read(R.RAW + self.commit + '/x', 5, 'raw')
        opener.open.assert_not_called()
        transport = R.Transport(opener=opener)
        transport.bytes = 3 * R.MAX_BYTES
        with self.assertRaisesRegex(ValueError, 'bound'): transport.read(R.RAW + self.commit + '/x', 5, 'raw')
        self.assertEqual(opener.open.call_count, 1)

    def test_later_gate_rejects_co_tampered_manifest_and_entry_before_execution(self):
        base = self.temp / 'section11-entry'
        base.mkdir(mode=0o700)
        good = b'print("good")\n'
        official = manifest({R.ENTRY: good})
        forged = b'print("co-tampered code executed")\n'
        (base / 'manifest.json').write_bytes(manifest({R.ENTRY: forged}))
        (base / 'hosted_runtime.py').write_bytes(forged)
        env = {'RUNNER_TEMP': str(self.temp), 'GITHUB_WORKSPACE': str(self.checkout)}
        args = ['gate', 'sync', '--manifest-sha256', R.digest(official)]
        with mock.patch.dict(os.environ, env), mock.patch.object(sys, 'argv', args), contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(ValueError, 'before runtime execution'): G.main()
            self.assertEqual(output.getvalue(), '')
            (base / 'manifest.json').write_bytes(official)
            (base / 'hosted_runtime.py').write_bytes(good)
            G.main()
            self.assertEqual(output.getvalue(), 'good\n')

    def test_half_mode_executes_verified_older_producer_in_isolated_child(self):
        old = (b'import json, os\nfrom pathlib import Path\n'
               b'assert not any(k in ("GH_TOKEN", "GITHUB_TOKEN") or k.startswith("GIT_CONFIG") for k in os.environ)\n'
               b'Path("latest.json").write_text(json.dumps({"fixture_producer":"older-installed-release"}))\n')
        self.files['examples/sync.py'] = old
        self.raw = manifest(self.files)
        self.upstream = Upstream([(self.tag, self.commit, self.raw, self.files)])
        self.install()
        self.acquire()
        info = {'source': str(self.temp / 'section11-trusted-source'), 'run_sync': True, 'operation': 'Sync',
                'event': 'workflow_dispatch', 'cron': '', 'available_date': None}
        env = {'GITHUB_WORKSPACE': str(self.checkout), 'GITHUB_TOKEN': 'synthetic', 'GH_TOKEN': 'synthetic',
               'GIT_CONFIG_COUNT': '1', 'ATHLETE_ID': 'fixture-athlete', 'INTERVALS_KEY': 'fixture-key'}
        with mock.patch.dict(os.environ, env), mock.patch.object(hosted, 'context', return_value=info), \
                contextlib.redirect_stdout(io.StringIO()):
            hosted.run_sync(isolated=True)
        self.assertEqual(json.loads((self.checkout / 'latest.json').read_bytes())['fixture_producer'], 'older-installed-release')
        self.assertEqual(self.upstream.assets, [])
