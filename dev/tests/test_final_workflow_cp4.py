"""Final workflow wiring, native acquisition and maintenance, entirely offline."""
import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
from unittest import mock
from urllib.parse import parse_qs, quote, urlsplit

from test_update_prototype import Offline, ROOT, manifest, inventory, write
from test_b2_hosted import Remote, release, DirectPublisher
import hosted
import hosted_update as H
import hosted_runtime as R
import seal_pins as S
import release_package as package
from test_b3_release import sealed_files


def workflows():
    return [(ROOT / name).read_text() for name in S.WORKFLOWS]


def steps(text):
    return dict((block.splitlines()[0], block) for block in text.split('      - name: ')[1:])


def deadline_guard(text):
    """The step guard exactly as a copied template writes it to the runner."""
    start = '          cat > "$RUNNER_TEMP/section11-deadline.py" <<\'SECTION11_DEADLINE\'\n'
    end = '          SECTION11_DEADLINE\n'
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError('missing or ambiguous step deadline guard')
    lines = text.split(start, 1)[1].split(end, 1)[0].splitlines(keepends=True)
    if any(line.strip() and not line.startswith('          ') for line in lines):
        raise ValueError('invalid embedded guard indentation')
    return ''.join(line[10:] if line.strip() else '\n' for line in lines)


class WorkflowTests(Offline):
    def test_verbatim_gate_and_legacy_fixture_hashes(self):
        gate = (ROOT / 'dev/hosted_gate.py').read_bytes()
        for name, text in zip(S.WORKFLOWS, workflows()):
            self.assertEqual(S.embedded_gate(text.encode()), gate)
            self.assertEqual(text.splitlines()[0], '# Section 11 workflow v11.111')
            old = ROOT / 'dev/fixtures/hosted' / (name.split('/')[1] + '-v11.105.yml')
            expected = ('11b4954442730b61c8b5fc7090f7553ab511c4593ab4ee939f619f2319f8c93f'
                        if 'json-auto-sync' in name else
                        '823116d6b09acf82983aa9fd68b1b04233c1664a0a49c9155dc5b4a5f717e2f2')
            self.assertEqual(S.sha256(old.read_bytes()), expected)

    def test_order_credential_compartments_and_every_phase_uses_gate(self):
        phases = {'Verify runtime dependencies': 'bootstrap', 'Prepare operation': 'prepare',
                  'Prepare slow cache staging': 'cache-prepare', 'Run sync': 'sync',
                  'Verify generated data': 'validate', 'Publish data and update README': 'publish',
                  'Prepare changed slow sources for saving': 'cache-promote',
                  'Eligible update maintenance': 'maintain'}
        for text in workflows():
            blocks = steps(text)
            names = ['Require default branch', 'Checkout default branch', 'Setup Python',
                     'Write step deadline guard',
                     'Select and fetch official runtime', 'Write fixed verification gate',
                     'Verify runtime dependencies', 'Install dependencies', 'Prepare operation',
                     'Prepare slow cache staging', 'Restore slow sources', 'Run sync',
                     'Verify generated data', 'Publish data and update README',
                     'Prepare changed slow sources for saving', 'Save changed slow sources',
                     'Eligible update maintenance', 'Upload data files for download']
            self.assertEqual(list(blocks), names)
            for name, block in blocks.items():
                expected_token = name in ('Prepare operation', 'Publish data and update README',
                                          'Eligible update maintenance')
                self.assertEqual('GITHUB_TOKEN:' in block, expected_token, name)
                self.assertEqual('GH_TOKEN:' in block, name == 'Select and fetch official runtime', name)
                self.assertEqual('secrets.' in block, name == 'Run sync', name)
                # The three exempt steps only test a variable or write one fixed local file.
                if name not in ('Require default branch', 'Write step deadline guard',
                                'Write fixed verification gate'):
                    self.assertRegex(block, r'(?m)^        timeout-minutes: [1-9][0-9]*$')
                if name in phases:
                    self.assertIn('python -I -B "$RUNNER_TEMP/section11-gate.py" ' + phases[name], block)
                    self.assertIn('RUNTIME_TAG: ${{ steps.select.outputs.tag }}', block)
                    self.assertIn('RUNTIME_COMMIT: ${{ steps.select.outputs.commit }}', block)
                    if phases[name] != 'bootstrap':
                        self.assertIn('--manifest-sha256 "$RUNTIME_DIGEST"', block)
                    if phases[name] not in ('bootstrap', 'prepare'):
                        self.assertIn('--application-sha256 "$APPLICATION_DIGEST"', block)
                        self.assertIn('APPLICATION_COMMIT: ${{ steps.prepare.outputs.application_commit }}', block)
            self.assertNotIn('section11-trusted-source/examples/maintenance/hosted.py', text)
            self.assertIn('persist-credentials: false', text)
            self.assertNotIn('actions: write', text)
            self.assertNotIn('issues:', text)

    def test_operations_first_adoption_cache_and_artifact_contracts(self):
        for text in workflows():
            blocks = steps(text)
            self.assertIn("options: [Sync, Update, Status, Rollback, 'Sync timer', Other]", text)
            self.assertIn("      other_operation:\n", text)
            self.assertIn("        type: boolean\n        default: false", text)
            self.assertIn('args+=(--force-release-download)', blocks['Prepare operation'])
            self.assertIn('"${args[@]}"', blocks['Prepare operation'])
            self.assertNotRegex(text, r'\$\{\{\s*(?:inputs|github.event.inputs)\.(?:other_)?operation\s*\}\}')
            save = blocks['Save changed slow sources']
            self.assertIn("steps.publish.outputs.published == 'true'", save)
            self.assertIn("steps.slow_cache_save_file.outputs.ready == 'true'", save)
            self.assertIn('path: ${{ runner.temp }}/section11-slow-cache/cache.json', save)
            self.assertNotIn('uses: actions/cache@', text)
            artifact = blocks['Upload data files for download']
            names = [line.strip() for line in artifact.split('          path: |\n')[1].split('          retention-days:')[0].splitlines()]
            self.assertEqual(names, ['latest.json', 'history.json', 'intervals.json', 'routes.json', 'saved_workouts.json', 'ftp_history.json'])
            self.assertIn("steps.prepare.outputs.operation != 'Sync timer'", artifact)
            self.assertNotIn('section11-runtime', save)

    def test_default_branch_timer_and_owner_envelope(self):
        auto, demand = workflows()
        self.assertEqual(auto.split('  workflow_dispatch:', 1)[1], demand.split('  workflow_dispatch:', 1)[1])
        self.assertEqual(hosted.data_crons(auto.encode()), ['7,37 * * * *'])
        self.assertEqual(hosted.data_crons(demand.encode()), [])
        for text in (auto, demand):
            self.assertIn("if: ${{ github.event_name != 'schedule' || vars.SECTION11_SYNC_TIMER != 'on' }}", text)
            self.assertIn("inputs.operation == 'Sync timer' && 'Sync timer run'", text)
            self.assertIn('group: section11-writer\n  cancel-in-progress: false\n  queue: max', text)
            guard = steps(text)['Require default branch'].split('        run: ', 1)[1].strip()
            for ref, code in [('refs/heads/main', 0), ('refs/heads/other', 1)]:
                result = subprocess.run(['/bin/sh', '-c', guard], env={'GITHUB_REF': ref, 'SECTION11_DEFAULT_BRANCH': 'main'}, capture_output=True)
                self.assertEqual(result.returncode, code)
        t1 = auto.replace("7,37 * * * *", "7 */3 * * *")
        self.assertEqual(hosted.data_crons(t1.encode()), ['7 */3 * * *'])


class SelectionTests(Offline):
    def execute(self, responses, *, template=0, seconds=30):
        block = steps(workflows()[template])['Select and fetch official runtime']
        source = '\n'.join(line[10:] for line in block.split('        run: |\n', 1)[1].splitlines())
        # Every official read runs under the template's own guard. Only a stall
        # test shortens the template's 30-second read deadline.
        bound = 'python -I -B "$RUNNER_TEMP/section11-deadline.py" 30 \\\n'
        self.assertEqual(source.count(bound), 1)
        source = source.replace(bound, bound.replace(' 30 ', ' ' + str(seconds) + ' '))
        guard = self.root / 'section11-deadline.py'
        guard.write_text(deadline_guard(workflows()[template]))
        output = self.root / 'outputs'
        binary = self.root / 'bin'
        binary.mkdir()
        statuses = []
        for index, value in enumerate(responses):
            status, body = (('stall', b'') if value == 'stall' else (1, b'') if isinstance(value, int)
                            else value if isinstance(value, tuple) else (0, value))
            statuses.append(status)
            (self.root / f'gh-{index}.out').write_bytes(body)
        (self.root / 'gh_status.json').write_text(json.dumps(statuses))
        stub = self.root / 'fake_gh.py'
        stub.write_text(f"""import json, os, sys
from pathlib import Path
root = Path({str(self.root)!r})
log = root / 'gh_calls.json'
calls = json.loads(log.read_text()) if log.exists() else []
index = len(calls)
calls.append({{'argv': sys.argv[1:], 'env': dict(os.environ), 'cwd': os.getcwd()}})
log.write_text(json.dumps(calls))
status = json.loads((root / 'gh_status.json').read_text())[index]
if status == 'stall':
    # A hung read with a child; both ignore every signal that can be ignored.
    import signal, subprocess, time
    for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(number, signal.SIG_IGN)
    child = subprocess.Popen([sys.executable, '-I', '-B', '-c', 'import time; time.sleep(300)'])
    (root / 'stall_pids').write_text(str(os.getpid()) + ' ' + str(child.pid))
    time.sleep(300)
sys.stdout.buffer.write((root / ('gh-' + str(index) + '.out')).read_bytes())
raise SystemExit(status)
""")
        self.addCleanup(self.stop_stalled)
        # The guard's interpreter is the same protected one; record its use.
        python = binary / 'python'
        python.write_text('#!/bin/sh\nprintf \'%s\\n\' "$*" >> ' + shlex.quote(str(self.root / 'python_calls'))
                          + '\nexec ' + shlex.quote(sys.executable) + ' "$@"\n')
        python.chmod(0o700)
        # Only this offline stand-in can satisfy gh on the test PATH. Its Python
        # is the same protected interpreter running unittest, with isolation.
        fake = binary / 'gh'
        fake.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' -I -B '
                        + shlex.quote(str(stub)) + ' "$@"\n')
        fake.chmod(0o700)
        for name, target in (('env', '/usr/bin/env'), ('mkdir', '/bin/mkdir')):
            wrapper = binary / name
            wrapper.write_text('#!/bin/sh\nexec ' + target + ' "$@"\n')
            wrapper.chmod(0o700)
        env = {'RUNNER_TEMP': str(self.root), 'PATH': str(binary),
               'GH_TOKEN': 'synthetic-token', 'GITHUB_OUTPUT': str(output),
               'GITHUB_TOKEN': 'must-not-inherit', 'GH_HOST': 'bad.invalid', 'GIT_CONFIG_COUNT': '1'}
        result = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-e', '-o', 'pipefail', '-c', source],
                                env=env, capture_output=True, timeout=120)
        calls = json.loads((self.root / 'gh_calls.json').read_text())
        guarded = (self.root / 'python_calls').read_text().splitlines()
        self.assertEqual(len(guarded), len(calls))
        for line in guarded:
            self.assertTrue(line.startswith('-I -B ' + str(guard) + ' ' + str(seconds) + ' env -i PATH='), line)
        for call in calls:
            self.assertEqual(call['argv'][:5], ['api', '--hostname', 'github.com', '--method', 'GET'])
            self.assertTrue(call['argv'][5].startswith('repos/CrankAddict/section-11/'))
            self.assertEqual(call['env']['GH_TOKEN'], 'synthetic-token')
            self.assertEqual(call['env']['GH_CONFIG_DIR'], str(self.root / 'section11-gh-config'))
            self.assertEqual(call['cwd'], str(self.root / 'section11-gh-config'))
            self.assertTrue({'GITHUB_TOKEN', 'GH_HOST', 'GIT_CONFIG_COUNT'}.isdisjoint(call['env']))
        self.assertFalse(list((self.root / 'section11-gh-config').iterdir()))
        self.assertEqual(calls[0]['argv'][6:],
                         ['--jq', '[.tag_name, ("refs/tags/" + .tag_name | @uri)] | @tsv'])
        for call in calls:
            if '/commits/' in call['argv'][5]:
                self.assertEqual(call['argv'][6:], ['--jq', '.sha'])
        return result, calls, output.read_text() if output.exists() else None

    def stalled(self):
        path = self.root / 'stall_pids'
        return [int(pid) for pid in path.read_text().split()] if path.exists() else []

    def stop_stalled(self):
        for pid in self.stalled():
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)

    def selected(self, tag='2026.11.09-2'):
        # Model native gh --jq @tsv/@uri output, not a live API or jq check.
        escaped = tag.replace('\\', '\\\\').replace('\t', '\\t').replace('\r', '\\r').replace('\n', '\\n')
        return (escaped + '\t' + quote('refs/tags/' + tag, safe='') + '\n').encode()

    def commit(self, sha='a' * 40):
        return (sha + '\n').encode()

    def test_exact_raw_data_at_one_commit_and_empty_config(self):
        payload = b'raise AssertionError("must remain inert")\r\n'
        result, calls, output = self.execute([self.selected('opaque/tag'), self.commit(), b'{"files":{}}\n', payload, self.commit()])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 5)
        self.assertTrue(calls[1]['argv'][5].endswith('/commits/refs%2Ftags%2Fopaque%2Ftag'))
        self.assertEqual(calls[1]['argv'], calls[4]['argv'])
        self.assertTrue(all('?ref=' + 'a' * 40 in calls[i]['argv'][5] for i in (2, 3)))
        self.assertTrue(all(calls[i]['argv'][6:] == ['-H', 'Accept: application/vnd.github.raw+json'] for i in (2, 3)))
        self.assertEqual((self.root / 'section11-entry/hosted_runtime.py').read_bytes(), payload)
        self.assertEqual((self.root / 'section11-entry').stat().st_mode & 0o777, 0o700)
        self.assertEqual(output, 'tag=opaque/tag\ncommit=' + 'a' * 40 + '\n')

    def test_on_demand_uses_native_peeled_commit_with_constant_reads(self):
        result, calls, _ = self.execute([self.selected(), self.commit(), b'{}', b'pass', self.commit()], template=1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 5)
        self.assertTrue(calls[1]['argv'][5].endswith('/commits/refs%2Ftags%2F2026.11.09-2'))
        self.assertFalse(any('/git/tags/' in call['argv'][5] for call in calls))

    def test_failed_read_has_no_retry_or_identity_output(self):
        result, calls, output = self.execute([self.selected(), self.commit(), 403])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 3)
        self.assertIsNone(output)
        self.assertFalse((self.root / 'section11-entry/hosted_runtime.py').exists())

    def stall_at(self, position):
        responses = [self.selected(), self.commit(), b'{}', b'pass', self.commit()][:position] + ['stall']
        result, calls, output = self.execute(responses, seconds=1)
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertIn(b'::error::Step deadline of 1 seconds reached', result.stderr)
        self.assertEqual(len(calls), position + 1)
        self.assertIsNone(output)
        self.assertEqual(len(self.stalled()), 2)
        for pid in self.stalled():
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    def test_stalled_read_in_a_command_substitution_fails_at_its_deadline_with_no_process_left(self):
        self.stall_at(0)

    def test_stalled_redirected_read_fails_at_its_deadline_with_no_process_left(self):
        self.stall_at(3)
        self.assertFalse((self.root / 'section11-entry/hosted_runtime.py').read_bytes())

    def test_moved_tag_refuses_handoff(self):
        result, calls, output = self.execute([self.selected(), self.commit(), b'{}', b'pass', self.commit('b' * 40)])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 5)
        self.assertIsNone(output)

    def test_failed_recheck_cannot_hide_behind_matching_stdout(self):
        result, calls, output = self.execute([self.selected(), self.commit(), b'{}', b'pass', (1, self.commit())])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 5)
        self.assertIsNone(output)

    def test_unresolvable_tag_refuses_handoff(self):
        result, calls, output = self.execute([self.selected(), 404])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 2)
        self.assertIsNone(output)

    def test_invalid_commit_refuses_fetch_and_output_injection(self):
        result, calls, output = self.execute([self.selected(), b'bad\ncommit=evil\n'])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 2)
        self.assertIsNone(output)

    def test_tsv_tag_cannot_inject_an_output_or_shell_command(self):
        tag = 'safe\ncommit=evil$(touch forbidden)'
        result, _, output = self.execute([self.selected(tag), self.commit(), b'{}', b'pass', self.commit()])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.splitlines(), ['tag=safe\\ncommit=evil$(touch forbidden)', 'commit=' + 'a' * 40])
        self.assertFalse((self.root / 'section11-gh-config/forbidden').exists())
        with self.assertRaisesRegex(ValueError, 'invalid release tag'):
            R.release_tag(output.splitlines()[0][4:])


class OperationTests(Offline):
    def test_other_only_when_selected_and_unknown_rejected(self):
        for operation in ('Sync', 'Update', 'Status', 'Rollback', 'Sync timer'):
            self.assertEqual(R.operation_input({'inputs': {'operation': operation, 'other_operation': 'unknown'}}), operation)
            self.assertEqual(R.operation_input({'inputs': {'operation': 'Other', 'other_operation': operation}}), operation)
        self.assertEqual(R.operation_input({}), 'Sync')
        for value in ('', 'Other', 'sync', 'future operation', '"; $(touch forbidden)', 'Sync\nUpdate'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'unknown'):
                R.operation_input({'inputs': {'operation': 'Other', 'other_operation': value}})

    def test_unknown_bootstrap_stops_before_runtime_staging_or_network(self):
        event = self.root / 'event.json'
        event.write_text('{"inputs":{"operation":"Other","other_operation":"unknown"}}')
        raw, entry = manifest({R.ENTRY: b'pass'}), b'pass'
        env = {'GITHUB_EVENT_PATH': str(event), 'RUNNER_TEMP': str(self.root), 'GITHUB_WORKSPACE': str(self.root / 'checkout')}
        before = inventory(self.root)
        args = ['gate', 'bootstrap', '--tag', '2026.11.09', '--commit', 'a' * 40, '--wrapper-api', '2']
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(sys, 'argv', args), \
                mock.patch.dict(R.__dict__, {'OFFICIAL_MANIFEST': raw, 'VERIFIED_ENTRY': entry}), \
                mock.patch.object(R, 'runtime_payload') as payload:
            with self.assertRaisesRegex(ValueError, 'unknown'): R.main()
            payload.assert_not_called()
        self.assertEqual(inventory(self.root), before)

    def test_controller_receives_mapped_operation_as_data(self):
        env = {'SECTION11_DEFAULT_BRANCH': 'main', 'GITHUB_REF': 'refs/heads/main',
               'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_RUN_ID': '42',
               'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_REPOSITORY': 'synthetic/data'}
        api = mock.Mock()
        api.get.return_value = {'id': 42, 'event': 'workflow_dispatch', 'head_branch': 'main',
                                'run_attempt': 1, 'head_repository': {'full_name': 'synthetic/data'},
                                'created_at': '2026-11-09T00:01:00Z'}
        self.assertEqual(hosted.trigger(api, {'inputs': {'operation': 'Other', 'other_operation': 'Sync timer'}}, env)['operation'], 'Sync timer')
        with self.assertRaisesRegex(ValueError, 'unknown'):
            hosted.trigger(api, {'inputs': {'operation': 'Other', 'other_operation': 'future'}}, env)


class CadenceTests(Offline):
    def setUp(self):
        super().setUp()
        self.now = datetime(2026, 11, 9, 0, 20, tzinfo=timezone.utc)
        self.env = {'GITHUB_RUN_ID': '42', 'GITHUB_RUN_ATTEMPT': '1',
                    'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_REPOSITORY': 'synthetic/data',
                    'SECTION11_DEFAULT_BRANCH': 'main'}
        self.current = {'id': 42, 'workflow_id': 9, 'run_attempt': 1, 'head_branch': 'main',
                        'head_repository': {'full_name': 'synthetic/data'}, 'event': 'workflow_dispatch',
                        'created_at': '2026-11-09T00:17:00Z', 'updated_at': '2026-11-09T00:17:00Z'}

    def due(self, others=(), **page_fields):
        api = mock.Mock()
        page = {'workflow_runs': [self.current, *others], 'total_count': 1 + len(others), **page_fields}
        api.get.side_effect = [self.current, page]
        result = hosted.maintenance_due(api, self.env, self.now)
        self.assertLessEqual(api.get.call_count, 2)
        if api.get.call_count == 2:
            query = parse_qs(urlsplit(api.get.call_args.args[0]).query)
            self.assertEqual(query, {'branch': ['main'], 'per_page': ['100'], 'created': ['>=2026-11-08T23:40:00Z']})
        self.assertFalse(api.write.called)
        return result

    def prior(self, seconds, **fields):
        return dict(self.current, id=41, updated_at=(self.now - timedelta(seconds=seconds)).isoformat(), **{'status': 'completed', **fields})

    def test_exact_boundary_and_failed_checks_count(self):
        self.assertTrue(self.due())
        for status in ('success', 'failure', 'cancelled'):
            self.assertFalse(self.due([self.prior(599, conclusion=status)]))
            self.assertTrue(self.due([self.prior(600, conclusion=status)]))
        self.assertFalse(self.due([self.prior(0, status='queued')]))

    def test_skipped_schedule_two_minutes_ago_does_not_suppress_maintenance(self):
        self.assertTrue(self.due([self.prior(120, event='schedule', conclusion='skipped')]))

    def test_failed_run_two_minutes_ago_still_suppresses_maintenance(self):
        for conclusion in ('failure', 'cancelled', 'success', None):
            with self.subTest(conclusion=conclusion):
                self.assertFalse(self.due([self.prior(120, conclusion=conclusion)]))
        self.assertFalse(self.due([self.prior(120, status='queued', conclusion='skipped')]))

    def test_bounded_saturation_and_missing_current_fail_closed(self):
        self.assertFalse(self.due(total_count=100))
        self.assertFalse(self.due(total_count=999999999))
        self.assertFalse(self.due(workflow_runs=[], total_count=0))

    def test_old_queue_and_rerun_defer_without_history_scan(self):
        self.current['created_at'] = '2026-11-08T23:49:59Z'
        self.assertFalse(self.due())
        self.current['created_at'] = '2026-11-08T23:50:00Z'
        self.assertTrue(self.due())
        self.current['run_attempt'] = 2
        self.env['GITHUB_RUN_ATTEMPT'] = '2'
        self.assertFalse(self.due())

    def test_clock_and_identity_conflicts_stop(self):
        with self.assertRaisesRegex(ValueError, 'timestamp'):
            self.due([self.prior(-1)])
        with self.assertRaisesRegex(ValueError, 'identity'):
            self.due([self.prior(600, head_branch='other')])

    def test_allowance_does_not_change_data_or_discover_target_when_not_due(self):
        info = {'published': False, 'base': 'a' * 40}
        runtime, pub = mock.Mock(), mock.Mock()
        with mock.patch.object(hosted, 'context', return_value=info), \
                mock.patch.object(hosted, 'publisher', return_value=pub), \
                mock.patch.object(hosted, 'maintenance_due', return_value=False), \
                contextlib.redirect_stdout(io.StringIO()):
            hosted.maintain(runtime=runtime)
        self.assertFalse(pub.snapshot.called)
        self.assertFalse(runtime.latest.called)

    def test_new_allowance_has_no_claim_commit_even_on_failed_fetch(self):
        remote = Remote()
        pub = DirectPublisher(remote, 'main')
        snapshot = pub.snapshot()
        updater = H.HostedUpdater(pub, mock.Mock(side_effect=ValueError('synthetic read failed')),
                                  {'SECTION11_AUTO_UPDATE': 'false'}, suffix_capable=True)
        initial = remote.tip
        with mock.patch.object(updater, 'claim', side_effect=AssertionError('no claim write')):
            with self.assertRaisesRegex(ValueError, 'synthetic read failed'):
                updater.maintain(snapshot, '2026.11.09', False, claim_attempt=False)
        self.assertEqual(remote.tip, initial)
        self.assertFalse(any(call[0] != 'GET' for call in remote.calls))

    def test_no_change_maintenance_does_not_write_and_legacy_still_claims(self):
        target = release()
        remote = Remote()
        pub = DirectPublisher(remote, 'main')
        updater = H.HostedUpdater(pub, lambda: target, {'SECTION11_AUTO_UPDATE': 'false'}, suffix_capable=True)
        with contextlib.redirect_stdout(io.StringIO()):
            updater.install(pub.snapshot(), accepted=True)
            before = remote.tip
            remote.calls.clear()
            updater.maintain(pub.snapshot(), '2026.11.09', True, claim_attempt=False)
            self.assertEqual(remote.tip, before)
            self.assertFalse(any(c[0] != 'GET' for c in remote.calls))
            updater.maintain(pub.snapshot(), '2026.11.09', True)
        self.assertNotEqual(remote.tip, before)
        self.assertEqual(H.control(remote.inventory()[H.CONTROL])['attempted_day'], '2026.11.09')


class ReleaseTests(Offline):
    def final_files(self):
        files = sealed_files()
        files.update({name: (ROOT / name).read_bytes() for name in (*S.WORKFLOWS, S.RUNTIME)})
        return files

    def test_dual_validation_and_exact_detached_assets(self):
        for files in (sealed_files(), self.final_files()):
            result = S.validate_payload(files)
            remote = mock.Mock()
            blobs = {S.blob_id(files[name]): files[name] for name in (S.VERIFIER, S.BOOTSTRAP)}
            remote.blob.side_effect = lambda sha, digest: blobs[sha]
            self.assertEqual(S.verify_files(files, remote)['bootstrap'], result[1])
            assets = package.delivery_assets(files, '2026.11.09')
            self.assertEqual(assets['section11-2026.11.09-auto-sync.yml'], files[S.WORKFLOWS[0]])
            self.assertEqual(assets['section11-2026.11.09-hosted-bootstrap.py'], files[S.BOOTSTRAP])
        files = self.final_files()
        all_assets = package.build(manifest(files), files, 'a' * 40, '2026.11.09')
        self.assertEqual(len(all_assets), 7)
        self.assertEqual(all_assets['section11-2026.11.09-on-demand.yml'], files[S.WORKFLOWS[1]])
        remote.tree.return_value = [
            {'path': n, 'mode': '100644', 'type': 'blob', 'sha': S.blob_id(files[n])}
            for n in (S.VERIFIER, S.BOOTSTRAP, *S.WORKFLOWS, S.RUNTIME)]
        self.assertEqual(S.verify_source(files, remote, 'a' * 40)['commit'], 'a' * 40)
        remote.tree.return_value.pop()
        with self.assertRaisesRegex(ValueError, 'published source path differs'):
            S.verify_source(files, remote, 'a' * 40)
        files[S.VERIFIER] += b'# newer application; historical verifier retained\n'
        S.check_local(files)
        write(self.root, files)
        before = inventory(self.root)
        self.assertEqual(S.seal(self.root)['files'], [])
        self.assertEqual(inventory(self.root), before)

    def test_final_payload_refuses_missing_runtime_corrupt_gate_and_mixed_templates(self):
        for defect in ('runtime', 'gate', 'mixed', 'legacy_seal'):
            files = self.final_files()
            if defect == 'runtime': del files[S.RUNTIME]
            if defect == 'gate': files[S.WORKFLOWS[0]] = files[S.WORKFLOWS[0]].replace(b'import hashlib', b'import malicious')
            if defect == 'mixed': files[S.WORKFLOWS[0]] = sealed_files()[S.WORKFLOWS[0]]
            if defect == 'legacy_seal': files[S.BOOTSTRAP] = files[S.BOOTSTRAP].replace(b'VERIFIER_BLOB =', b'WRONG_BLOB =')
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                package.delivery_assets(files, '2026.11.09')

    def test_demo_builder_accepts_current_sealed_template(self):
        from test_demo_kit import B
        with contextlib.redirect_stdout(io.StringIO()):
            B.build(ROOT, self.root / 'demo')
        auto = (self.root / 'demo/repo/.github/workflows/auto-sync.yml').read_bytes()
        self.assertEqual(S.embedded_gate(auto), (ROOT / 'dev/hosted_gate.py').read_bytes())
        self.assertIn(b"- cron: '7 5 * * *'", auto)
        self.assertIn(b'section11-gate.py" finalize-export ', auto)
        self.assertNotIn(b'BOOTSTRAP_BLOB', auto)
