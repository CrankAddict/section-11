"""B3 T00: real pin files, authenticated transport, assets and promotion gates.

All HTTP and Git subprocess boundaries are mocked; no remote or Git writes.
"""
import base64
import contextlib
import hashlib
import io
import json
import os
import re
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

from test_update_prototype import Offline, ROOT, D, fixture, manifest, write, inventory
import seal_pins as S
import prepare_first_release as P
import publish_release as R
import release_package as package
import hosted_bootstrap as bootstrap


def source_files():
    _, files = fixture()
    for name in (S.BOOTSTRAP, *S.WORKFLOWS):
        data = (ROOT / name).read_bytes()
        if name == S.BOOTSTRAP:
            data = re.sub(rb"(?m)^VERIFIER_(BLOB|SHA256) = '[^']+'$", rb"VERIFIER_\1 = 'UNSEALED'", data)
        else:
            data = re.sub(rb'(?m)^(      BOOTSTRAP_(?:BLOB|SHA256):) [^\s]+$', rb'\1 UNSEALED', data)
        files[name] = data
    return files


def sealed_files():
    files = source_files()
    files[S.BOOTSTRAP] = files[S.BOOTSTRAP].replace(b"VERIFIER_BLOB = 'UNSEALED'", b"VERIFIER_BLOB = '" + S.blob_id(files[S.VERIFIER]).encode() + b"'")
    files[S.BOOTSTRAP] = files[S.BOOTSTRAP].replace(b"VERIFIER_SHA256 = 'UNSEALED'", b"VERIFIER_SHA256 = '" + S.sha256(files[S.VERIFIER]).encode() + b"'")
    for name in S.WORKFLOWS:
        files[name] = files[name].replace(b'BOOTSTRAP_BLOB: UNSEALED', b'BOOTSTRAP_BLOB: ' + S.blob_id(files[S.BOOTSTRAP]).encode())
        files[name] = files[name].replace(b'BOOTSTRAP_SHA256: UNSEALED', b'BOOTSTRAP_SHA256: ' + S.sha256(files[S.BOOTSTRAP]).encode())
    return files


class B3Offline(Offline):
    def setUp(self):
        super().setUp()
        guard = mock.patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('unmatched urllib request'))
        guard.start()
        self.addCleanup(guard.stop)


class SealTests(B3Offline):
    def test_all_six_pins_seal_offline_with_exact_readback_and_idempotence(self):
        original = source_files()
        write(self.root, original)
        with mock.patch.object(S, 'PublishedSource', side_effect=AssertionError('offline seal used transport')):
            first = S.seal(self.root)
        self.assertEqual(first['files'], [S.BOOTSTRAP, *S.WORKFLOWS])
        self.assertFalse(first['published'])
        self.assertEqual(S.pins((self.root / S.BOOTSTRAP).read_bytes(), 'VERIFIER'),
                         (S.blob_id(original[S.VERIFIER]), S.sha256(original[S.VERIFIER])))
        self.assertEqual(inventory(self.root), sealed_files())
        S.check_local(inventory(self.root))
        before = inventory(self.root)
        S.seal(self.root)
        self.assertEqual(inventory(self.root), before)
        self.assertEqual(before[S.WORKFLOWS[0]].split(b'  workflow_dispatch:', 1)[1],
                         before[S.WORKFLOWS[1]].split(b'  workflow_dispatch:', 1)[1])

    def test_unsealed_wrong_digest_and_changed_local_source_preserve_preimages(self):
        files = source_files()
        write(self.root, files)
        with self.assertRaisesRegex(ValueError, 'unsealed'):
            S.check_local(files)
        self.assertEqual(inventory(self.root), files)
        sealed = sealed_files()
        write(self.root, sealed)
        remote = mock.Mock()
        remote.blob.return_value = b'wrong digest'
        with self.assertRaisesRegex(ValueError, 'published pin target differs'):
            S.verify_files(sealed, remote)
        self.assertEqual(inventory(self.root), sealed)
        changed = dict(sealed, **{S.VERIFIER: b'unreviewed bytes'})
        write(self.root, changed)
        with self.assertRaisesRegex(ValueError, 'existing pins differ'):
            S.seal(self.root)
        self.assertEqual(inventory(self.root), changed)

    def test_changed_pin_or_missing_second_block_stops_before_any_write(self):
        files = source_files()
        files[S.WORKFLOWS[1]] = files[S.WORKFLOWS[1]].replace(b'BOOTSTRAP_SHA256:', b'NOT_A_PIN:')
        # A malformed second workflow must not partially seal bootstrap or first workflow.
        write(self.root, files)
        with self.assertRaisesRegex(ValueError, 'pin block'):
            S.seal(self.root)
        self.assertEqual(inventory(self.root), files)
        write(self.root, sealed_files())
        before = inventory(self.root)
        name = S.WORKFLOWS[1]
        before[name] = before[name].replace(S.sha256(before[S.BOOTSTRAP]).encode(), b'0' * 64)
        write(self.root, before)
        with self.assertRaisesRegex(ValueError, 'existing pins differ'):
            S.seal(self.root)
        self.assertEqual(inventory(self.root), before)

    def test_old_trusted_verifier_can_verify_a_newer_producer_without_stub_change(self):
        old = sealed_files()
        new = dict(old, **{S.VERIFIER: old[S.VERIFIER] + b'# later producer\n'})
        remote = mock.Mock()
        blobs = {S.blob_id(old[name]): old[name] for name in (S.VERIFIER, S.BOOTSTRAP)}
        remote.blob.side_effect = lambda identity, digest: blobs[identity]
        S.verify_files(new, remote)
        self.assertEqual(new[S.WORKFLOWS[0]], old[S.WORKFLOWS[0]])
        with self.assertRaisesRegex(ValueError, 'first-release verifier differs'):
            S.check_local(new)
        remote.blob.side_effect = lambda identity, digest: b'corrupt'
        with self.assertRaisesRegex(ValueError, 'published pin target differs'):
            S.verify_files(new, remote)

    def test_independent_raw_and_json_blob_readback_reject_disagreement(self):
        data = b'exact bytes\r\n'
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        body = {'sha': blob, 'size': len(data), 'encoding': 'base64', 'content': base64.b64encode(data).decode()}
        source = S.PublishedSource('synthetic-only')
        with mock.patch.object(source, 'read', side_effect=[data, body]) as read:
            self.assertEqual(source.blob(blob, S.sha256(data)), data)
        self.assertEqual(read.call_args_list, [mock.call('/git/blobs/' + blob, raw=True), mock.call('/git/blobs/' + blob)])
        for identity, digest in ((blob, '0' * 64), ('a' * 40, S.sha256(data))):
            with mock.patch.object(source, 'read', return_value=data):
                with self.assertRaisesRegex(ValueError, 'identity or digest differs'):
                    source.blob(identity, digest)
        with mock.patch.object(source, 'read', side_effect=[data, dict(body, content=base64.b64encode(b'wrong').decode())]):
            with self.assertRaisesRegex(ValueError, 'readback differs'):
                source.blob(blob, S.sha256(data))
        with mock.patch.object(source, 'read', side_effect=[data, dict(body, sha='b' * 40)]):
            with self.assertRaisesRegex(ValueError, 'invalid source blob'):
                source.blob(blob, S.sha256(data))

    def test_post_push_readback_binds_both_blob_targets_and_templates_to_W(self):
        files = sealed_files()
        remote = mock.Mock()
        blobs = {S.blob_id(files[name]): files[name] for name in (S.VERIFIER, S.BOOTSTRAP)}
        remote.blob.side_effect = lambda identity, digest: blobs[identity]
        tree = [{'path': n, 'mode': '100644', 'type': 'blob', 'sha': S.blob_id(files[n])}
                for n in (S.VERIFIER, S.BOOTSTRAP, *S.WORKFLOWS)]
        remote.tree.return_value = tree
        self.assertEqual(S.verify_source(files, remote, 'a' * 40)['commit'], 'a' * 40)
        for entries in (tree[1:], tree + [tree[0]], [dict(tree[0], mode='120000'), *tree[1:]],
                        [dict(tree[0], sha='b' * 40), *tree[1:]]):
            remote.tree.return_value = entries
            with self.assertRaisesRegex(ValueError, 'published source path differs'):
                S.verify_source(files, remote, 'a' * 40)
        source = S.PublishedSource('synthetic-only')
        with mock.patch.object(source, 'read', return_value={'tree': tree, 'truncated': True}):
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                source.tree('a' * 40)

    def test_source_transport_token_timeout_redirect_and_no_retry(self):
        source = S.PublishedSource('synthetic-only')
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'bytes'
        opener = mock.Mock()
        opener.open.return_value = response
        with mock.patch.object(S.urllib.request, 'build_opener', return_value=opener) as build:
            self.assertEqual(source.read('/git/blobs/' + 'a' * 40, raw=True), b'bytes')
            request = opener.open.call_args.args[0]
            self.assertEqual(request.get_header('Authorization'), 'Bearer synthetic-only')
            self.assertEqual(request.host, 'api.github.com')
            self.assertEqual(request.get_header('Accept'), 'application/vnd.github.raw+json')
            self.assertLessEqual(opener.open.call_args.kwargs['timeout'], 10)
            with self.assertRaisesRegex(ValueError, 'redirect refused'):
                build.call_args.args[0].redirect_request(None, None, 302, '', {}, 'https://elsewhere.invalid/')
            opener.open.reset_mock()
            opener.open.side_effect = HTTPError(request.full_url, 429, 'synthetic rate limit', {}, None)
            with self.assertRaises(HTTPError):
                source.read('/git/blobs/' + 'a' * 40, raw=True)
            self.assertEqual(opener.open.call_count, 1)
            source.count = 40
            with self.assertRaisesRegex(ValueError, 'admission bound'):
                source.read('/git/blobs/' + 'a' * 40, raw=True)
            self.assertEqual(opener.open.call_count, 1)


class BootstrapTransportTests(B3Offline):
    def test_authenticated_verifier_digest_precedes_import_and_no_retry(self):
        data = b'SYNTHETIC = True\n'
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = data
        opener = mock.Mock()
        opener.open.return_value = response
        with mock.patch.object(bootstrap.urllib.request, 'build_opener', return_value=opener):
            module = bootstrap.pinned_verifier(self.root / 'good', S.blob_id(data), S.sha256(data), token='synthetic-only')
            self.assertTrue(module.SYNTHETIC)
            request = opener.open.call_args.args[0]
            self.assertEqual(request.get_header('Authorization'), 'Bearer synthetic-only')
            self.assertEqual(request.full_url, S.UPSTREAM + '/git/blobs/' + S.blob_id(data))
            self.assertEqual(opener.open.call_count, 1)
            with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                bootstrap.pinned_verifier(self.root / 'bad', 'a' * 40, '0' * 64, token='synthetic-only')
            self.assertFalse((self.root / 'bad').exists())
            with self.assertRaisesRegex(ValueError, 'blob identity mismatch'):
                bootstrap.pinned_verifier(self.root / 'wrong-blob', 'a' * 40, S.sha256(data), token='synthetic-only')
            self.assertFalse((self.root / 'wrong-blob').exists())
            opener.open.reset_mock()
            opener.open.side_effect = HTTPError(request.full_url, 403, 'synthetic refusal', {}, None)
            with self.assertRaises(HTTPError):
                bootstrap.pinned_verifier(self.root / 'refused', 'a' * 40, S.sha256(data), token='synthetic-only')
            self.assertEqual(opener.open.call_count, 1)
            self.assertFalse((self.root / 'refused').exists())

    def test_actual_workflow_download_authenticates_and_checks_before_subprocess(self):
        for name in S.WORKFLOWS:
            text = (ROOT / name).read_text()
            block = text.split("python - <<'PY'\n", 1)[1].split('\n          PY', 1)[0]
            code = '\n'.join(line[10:] for line in block.splitlines())
            stage = self.root / name.split('/')[1]
            stage.mkdir()
            env = {'BOOTSTRAP_BLOB': S.blob_id(b'synthetic'), 'BOOTSTRAP_SHA256': S.sha256(b'synthetic'),
                   'GITHUB_TOKEN': 'synthetic-only', 'RUNNER_TEMP': str(stage)}
            response = mock.MagicMock()
            response.__enter__.return_value.read.return_value = b'wrong'
            opener = mock.Mock()
            opener.open.return_value = response
            with mock.patch.dict(os.environ, env), mock.patch('urllib.request.build_opener', return_value=opener), \
                    mock.patch('subprocess.run') as run:
                with self.assertRaisesRegex(SystemExit, 'digest mismatch'):
                    exec(compile(code, name, 'exec'), {})
                run.assert_not_called()
                request = opener.open.call_args.args[0]
                self.assertEqual(request.get_header('Authorization'), 'Bearer synthetic-only')
                self.assertEqual(request.full_url, S.UPSTREAM + '/git/blobs/' + S.blob_id(b'synthetic'))
                self.assertEqual(opener.open.call_count, 1)
                response.__enter__.return_value.read.return_value = b'synthetic'
                exec(compile(code, name, 'exec'), {})
                run.assert_called_once()
                self.assertEqual((stage / 'section11-bootstrap.py').read_bytes(), b'synthetic')
                run.reset_mock()
                with mock.patch.dict(os.environ, {'BOOTSTRAP_BLOB': 'a' * 40}):
                    with self.assertRaisesRegex(SystemExit, 'blob identity mismatch'):
                        exec(compile(code, name, 'exec'), {})
                run.assert_not_called()


class ReleaseGates(B3Offline):
    def test_T00_infrastructure_overlay_cannot_promote_legacy_entry(self):
        output = self.root / 'infrastructure'
        names = P.build(ROOT, output)
        self.assertEqual(len(names), 7)
        self.assertEqual(set(names), set(inventory(output)))
        self.assertNotIn('examples/sync.py', names)
        self.assertNotIn('manifest.json', names)
        for name in P.FILES:
            self.assertEqual((output / '.github/release-runtime' / name).read_bytes(), (ROOT / name).read_bytes())
        self.assertEqual((output / '.github/workflows/release.yml').read_bytes(), (ROOT / '.github/workflows/release.yml').read_bytes())
        workflow = (ROOT / '.github/workflows/release.yml').read_text()
        self.assertIn('refs/heads/{0}', workflow)
        self.assertIn('needs: verify', workflow)
        self.assertIn('working-directory: release-source', workflow)
        self.assertIn('ready = bool(requested) or not', workflow)
        self.assertNotIn('python release-source/examples/maintenance/publish_release.py', workflow)
        verify_job = workflow.split('  verify:', 1)[1].split('  publish:', 1)[0]
        self.assertNotIn('contents: write', verify_job)
        self.assertIn('issues: write', workflow.split('  publish:', 1)[1])

    def test_T00_selected_source_exact_commit_tree_and_workflow_gate(self):
        files = sealed_files()
        raw = manifest(files)
        write(self.root, dict(files, **{'manifest.json': raw}))
        remote_tree = {name: {'mode': '100644', 'type': 'blob',
                       'sha': hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()}
                       for name, data in dict(files, **{'manifest.json': raw}).items()}
        api = mock.Mock(token='synthetic-only')
        api.tree.return_value = remote_tree
        with mock.patch.object(R.subprocess, 'check_output', side_effect=['c' * 40, '']), \
                mock.patch.object(R, 'workflow_gate') as gate, mock.patch.object(R, 'verify_files') as verify:
            self.assertEqual(R.pinned_source(api, self.root, 'c' * 40), (raw, files))
            gate.assert_called_once_with(api, 'c' * 40)
            verify.assert_called_once()
        api.write.assert_not_called()
        remote_tree[S.VERIFIER]['sha'] = 'd' * 40
        with mock.patch.object(R.subprocess, 'check_output', side_effect=['c' * 40, '']), \
                mock.patch.object(R, 'workflow_gate'), mock.patch.object(R, 'verify_files') as verify:
            with self.assertRaisesRegex(ValueError, 'source tree differs'):
                R.pinned_source(api, self.root, 'c' * 40)
            verify.assert_not_called()
        with mock.patch.object(R.subprocess, 'check_output', return_value='d' * 40):
            with self.assertRaisesRegex(ValueError, 'checkout differs'):
                R.pinned_source(api, self.root, 'c' * 40)

    def promotion(self):
        files = sealed_files()
        raw = manifest(files)
        commit, tag = 'c' * 40, '2026.10.30'
        assets = package.build(raw, files, commit, tag)
        api = mock.Mock()
        api.release_metadata.return_value = {'id': 7, 'tag_name': tag}
        api.release.return_value = raw, files, {'commit': commit, 'tag': tag}
        api.resolve_tag.return_value = commit
        api.pages.return_value = [{'id': index, 'name': name, 'size': len(data)}
                                  for index, (name, data) in enumerate(assets.items())]
        content = list(assets.values())
        api.asset.side_effect = lambda index: content[index]
        return api, raw, files, assets

    def test_T00_all_seven_assets_exact_and_promotion_gate_read_only(self):
        api, raw, files, assets = self.promotion()
        self.assertEqual(len(assets), 7)
        for suffix, name in (('hosted-bootstrap.py', S.BOOTSTRAP), ('auto-sync.yml', S.WORKFLOWS[0]),
                             ('on-demand.yml', S.WORKFLOWS[1])):
            self.assertEqual(assets['section11-2026.10.30-' + suffix], files[name])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(R.verify_published(api, 'c' * 40, raw, files), '2026.10.30')
        api.write.assert_not_called()

    def test_T00_missing_release_incomplete_each_asset_wrong_manifest_and_moved_tag_stop(self):
        api, raw, files, assets = self.promotion()
        api.release_metadata.side_effect = R.APIError(404, 'no published release')
        with self.assertRaises(R.APIError):
            R.verify_published(api, 'c' * 40, raw, files)
        api.write.assert_not_called()
        for missing in assets:
            api, raw, files, _ = self.promotion()
            api.pages.return_value = [a for a in api.pages.return_value if a['name'] != missing]
            with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, 'incomplete'):
                R.verify_published(api, 'c' * 40, raw, files)
            api.write.assert_not_called()
        api, raw, files, _ = self.promotion()
        api.release.return_value = b'wrong manifest', files, {'commit': 'c' * 40}
        with self.assertRaisesRegex(ValueError, 'do not promote main'):
            R.verify_published(api, 'c' * 40, raw, files)
        api, raw, files, _ = self.promotion()
        api.resolve_tag.return_value = 'd' * 40
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            R.verify_published(api, 'c' * 40, raw, files)
        api.write.assert_not_called()

    def test_unsealed_or_wrong_bootstrap_digest_cannot_be_packaged(self):
        files = source_files()
        with self.assertRaisesRegex(ValueError, 'unsealed'):
            package.build(manifest(files), files, 'c' * 40, '2026.10.30')
        files = sealed_files()
        files[S.BOOTSTRAP] += b'# modified after sealing\n'
        with self.assertRaisesRegex(ValueError, 'bootstrap identity or digest differs'):
            package.build(manifest(files), files, 'c' * 40, '2026.10.30')

    def test_T00_normal_merge_or_squash_with_identical_complete_tree_is_accepted(self):
        for tip in ('c' * 40, 'd' * 40):
            api = mock.Mock()
            api.metadata.return_value = {'default_branch': 'main'}
            api.get.side_effect = lambda path: ({'object': {'sha': tip}} if path == '/git/ref/heads/main'
                                               else {'tree': {'sha': 'e' * 40}})
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(R.verify_promotion(api, 'c' * 40), tip)
            api.write.assert_not_called()

    def test_T00_merge_extra_file_and_concurrent_main_change_are_refused(self):
        api = mock.Mock()
        api.metadata.return_value = {'default_branch': 'main'}
        # One extra/conflicted file changes the complete root tree, even when
        # manifest-covered files and active workflows might still match.
        api.get.side_effect = [{'object': {'sha': 'd' * 40}}, {'tree': {'sha': 'e' * 40}},
                               {'tree': {'sha': 'f' * 40}}]
        with self.assertRaisesRegex(ValueError, 'main tree differs'):
            R.verify_promotion(api, 'c' * 40)
        api.get.side_effect = [{'object': {'sha': 'd' * 40}}, {'tree': {'sha': 'e' * 40}},
                               {'tree': {'sha': 'e' * 40}}, {'object': {'sha': 'a' * 40}}]
        with self.assertRaisesRegex(ValueError, 'main changed'):
            R.verify_promotion(api, 'c' * 40)
        api.write.assert_not_called()
