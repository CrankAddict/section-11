"""H3: a step deadline or cancellation stops the step's processes. Offline.

The guard is taken from the template text, so these tests run what an owner
copies. Process tests start real process trees that ignore every signal they
can; nothing here uses a network, a token or a live runner.
"""
import contextlib
import io
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
import unittest
from unittest import mock

from test_update_prototype import Offline, MAINT
from test_final_workflow_cp4 import deadline_guard, steps, workflows
import hosted
import hosted_runtime as R

EXEC = re.compile(r'exec python -I -B "\$RUNNER_TEMP/section11-deadline\.py" ([1-9][0-9]*) python -I -B ')
SELECT = 'Select and fetch official runtime'
GUARDED = ['Select and fetch official runtime', 'Verify runtime dependencies', 'Install dependencies',
           'Prepare operation', 'Prepare slow cache staging', 'Run sync', 'Verify generated data',
           'Publish data and update README', 'Prepare changed slow sources for saving',
           'Eligible update maintenance']
ACTIONS = ['Checkout default branch', 'Setup Python', 'Restore slow sources',
           'Save changed slow sources', 'Upload data files for download']
LOCAL = ['Require default branch', 'Write step deadline guard', 'Write fixed verification gate']

# Stand-in for a step's command. `stall` hangs with a child, `leave` exits and
# leaves that child behind, `exit` records its arguments and returns a status.
COMMAND = '''import json, os, signal, subprocess, sys, time
mode, record = os.environ['H3_MODE'], os.environ['H3_RECORD']
if mode == 'exit':
    with open(record, 'w') as handle:
        json.dump(sys.argv[1:], handle)
    sys.exit(int(os.environ.get('H3_STATUS', '0')))
if mode == 'killed':
    os.kill(os.getpid(), signal.SIGKILL)
for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
    signal.signal(number, signal.SIG_IGN)
child = subprocess.Popen([sys.executable, '-I', '-B', '-c', 'import time; time.sleep(300)'])
with open(record + '.new', 'w') as handle:
    json.dump([os.getpid(), child.pid], handle)
os.replace(record + '.new', record)
if mode == 'leave':
    sys.exit(0)
time.sleep(300)
'''

# A publisher that hangs inside publication, driven by the real phase runner.
PUBLISHER = '''import json, os, sys, time
sys.path.insert(0, os.environ['H3_MAINT'])
import hosted_runtime
path = os.environ['H3_CONTEXT']
class Controller:
    cache_prepare = run_sync = finalize_export = validate_generated = cache_promote = None
    def context(self, value=None):
        if value is None:
            with open(path) as handle:
                return json.load(handle)
        with open(path, 'w') as handle:
            json.dump(value, handle)
    def publish_data(self):
        with open(os.environ['H3_RECORD'], 'w') as handle:
            json.dump([os.getpid()], handle)
        time.sleep(300)
hosted_runtime.run_phase(Controller(), 'publish')
'''


def script(block):
    """One step's run script, as the runner writes it to a file."""
    if '        run: |\n' in block:
        return '\n'.join(line[10:] for line in block.split('        run: |\n', 1)[1].splitlines()) + '\n'
    return block.split('        run: ', 1)[1].splitlines()[0] + '\n'


def condition(block):
    return block.split('\n        if: ', 1)[1].splitlines()[0] if '\n        if: ' in block else ''


def drain(stream):
    """Read what is there and report whether every writer has gone."""
    os.set_blocking(stream.fileno(), False)
    data = b''
    while True:
        try:
            chunk = os.read(stream.fileno(), 65536)
        except BlockingIOError:
            return data, False
        if not chunk:
            return data, True
        data += chunk


class TemplateTests(Offline):
    def test_same_fixed_guard_is_written_once_and_privately(self):
        auto, demand = workflows()
        guard = deadline_guard(auto)
        self.assertEqual(deadline_guard(demand), guard)
        compile(guard, 'section11-deadline.py', 'exec')
        block = steps(auto)['Write step deadline guard']
        self.assertIn('        shell: bash\n', block)
        self.assertNotIn('${{', block)
        command = ['/bin/bash', '--noprofile', '--norc', '-e', '-o', 'pipefail', '-c', script(block)]
        env = {'RUNNER_TEMP': str(self.root), 'PATH': '/bin:/usr/bin'}
        self.assertEqual(subprocess.run(command, env=env, capture_output=True).returncode, 0)
        written = self.root / 'section11-deadline.py'
        self.assertEqual(written.read_text(), guard)
        self.assertEqual(written.stat().st_mode & 0o777, 0o600)
        # A second write cannot replace the guard that later steps execute.
        self.assertNotEqual(subprocess.run(command, env=env, capture_output=True).returncode, 0)
        self.assertEqual(written.read_text(), guard)

    def test_every_long_run_step_has_a_deadline_inside_its_limit(self):
        for text in workflows():
            guarded, actions, local = [], [], []
            for name, block in steps(text).items():
                limit = re.search(r'(?m)^        timeout-minutes: ([1-9][0-9]*)$', block)
                if '        run: ' not in block:
                    # An action's process cannot be wrapped; the report names this limit.
                    self.assertIn('        uses: ', block)
                    actions.append(name)
                    continue
                if limit is None:
                    local.append(name)
                    continue
                source = script(block)
                if name == SELECT:
                    # Five sequential reads, each under its own deadline.
                    self.assertEqual(source.count('gh_api '), 5)
                    bound = re.findall(r'  python -I -B "\$RUNNER_TEMP/section11-deadline\.py" ([1-9][0-9]*) \\\n'
                                       r'    env -i PATH="\$PATH" ', source)
                    self.assertEqual(len(bound), 1)
                    self.assertEqual(source.count('section11-deadline.py'), 1)
                    total = 5 * int(bound[0])
                else:
                    # The guard replaces the shell as the step's final and only
                    # long command, so nothing can follow or mask its status.
                    last = source.splitlines()[-1]
                    match = EXEC.match(last)
                    self.assertIsNotNone(match, name)
                    self.assertEqual(source.count('section11-deadline.py'), 1)
                    self.assertNotRegex(last, r'\|\||&&|;|&\s*$|\|')
                    total = int(match.group(1))
                # Room for the runner to see the failure before its own limit,
                # without shortening the step by more than a minute.
                margin = int(limit.group(1)) * 60 - total
                self.assertGreaterEqual(margin, 30, name)
                self.assertLessEqual(margin, 60, name)
                guarded.append(name)
            self.assertEqual(guarded, GUARDED)
            self.assertEqual(actions, ACTIONS)
            self.assertEqual(local, LOCAL)

    def test_later_steps_see_a_stopped_step_as_a_failure(self):
        for text in workflows():
            blocks = steps(text)
            # Only these steps may run after an earlier failure or cancellation.
            overrides = {name: re.findall(r'always\(\)|cancelled\(\)|failure\(\)|success\(\)', condition(block))
                         for name, block in blocks.items()}
            self.assertEqual({name: found for name, found in overrides.items() if found}, {
                'Prepare changed slow sources for saving': ['success()'],
                'Save changed slow sources': ['success()'],
                'Eligible update maintenance': ['cancelled()'],
                'Upload data files for download': ['always()']})
            # A stopped sync, validation or publication fails the job outright.
            for name in ('Run sync', 'Verify generated data', 'Publish data and update README'):
                self.assertNotIn('continue-on-error', blocks[name])
                self.assertEqual(condition(blocks[name]), "steps.prepare.outputs.run_sync == 'true'")
            self.assertEqual(condition(blocks['Eligible update maintenance']),
                             "${{ !cancelled() && steps.prepare.outputs.maintenance == 'true' }}")

    def test_upload_requires_a_finished_validation_of_a_finished_sync(self):
        for text in workflows():
            blocks = steps(text)
            order = list(blocks)
            self.assertIn('        id: validate\n', blocks['Verify generated data'])
            self.assertIn("steps.validate.outcome == 'success'", condition(blocks['Upload data files for download']))
            self.assertLess(order.index('Run sync'), order.index('Verify generated data'))
            self.assertLess(order.index('Verify generated data'), order.index('Publish data and update README'))
            self.assertEqual(order[-1], 'Upload data files for download')
            # Validation runs only after every earlier step succeeded, and the
            # guard has by then stopped whatever the sync step started.
            self.assertNotRegex(condition(blocks['Verify generated data']), r'\(\)')
            self.assertIsNotNone(EXEC.match(script(blocks['Run sync'])))


@unittest.skipUnless(os.name == 'posix', 'process groups and signals need a POSIX host')
class ProcessCase(Offline):
    def setUp(self):
        super().setUp()
        self.guard = self.root / 'section11-deadline.py'
        self.guard.write_text(deadline_guard(workflows()[0]))
        self.command = self.root / 'command.py'
        self.command.write_text(COMMAND)
        self.record = self.root / 'record.json'
        self.processes = []
        self.addCleanup(self.reap)

    def reap(self):
        pids = [pid for pid in self.recorded() if type(pid) is int]
        for process in self.processes:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
            process.stderr.close()
        for pid in pids:
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)

    def recorded(self, wait=0):
        end = time.monotonic() + wait
        while not self.record.exists() and time.monotonic() < end:
            time.sleep(0.02)
        return json.loads(self.record.read_text()) if self.record.exists() else []

    def start(self, argv, mode, **env):
        self.record.unlink(missing_ok=True)
        process = subprocess.Popen(argv, env={'H3_MODE': mode, 'H3_RECORD': str(self.record), **env},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.processes.append(process)
        return process

    def guarded(self, seconds, mode, command=None, **env):
        return self.start([sys.executable, '-I', '-B', str(self.guard), str(seconds),
                           sys.executable, '-I', '-B', str(command or self.command)], mode, **env)

    def finish(self, process):
        try:
            return process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            self.fail('the command was still running after the test bound')

    def assertStopped(self, process, count=2):
        """Checked the moment the entry process has returned, without waiting."""
        pids = self.recorded()
        self.assertEqual(len(pids), count)
        for pid in pids:
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)
        # No survivor holds the step's output open either.
        self.assertTrue(drain(process.stdout)[1])


class GuardTests(ProcessCase):
    def test_deadline_stops_a_tree_that_ignores_signals_before_the_guard_returns(self):
        process = self.guarded(1, 'stall')
        self.assertEqual(self.finish(process), 124)
        self.assertStopped(process)
        self.assertIn(b'::error::Step deadline of 1 seconds reached; its processes were stopped.',
                      drain(process.stderr)[0])

    def test_cancellation_signals_stop_the_tree_inside_the_runner_grace(self):
        for number in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(signal=number.name):
                process = self.guarded(300, 'stall')
                self.assertEqual(len(self.recorded(wait=30)), 2)
                began = time.monotonic()
                process.send_signal(number)
                self.assertEqual(self.finish(process), 128 + number)
                # The runner waits 7.5 s after SIGINT before it escalates.
                self.assertLess(time.monotonic() - began, 5)
                self.assertStopped(process)
                self.assertEqual(drain(process.stderr)[0], b'')

    def test_finished_command_keeps_its_status_and_leaves_no_child(self):
        process = self.guarded(300, 'leave')
        self.assertEqual(self.finish(process), 0)
        self.assertStopped(process)
        for status in (0, 7):
            process = self.guarded(300, 'exit', H3_STATUS=str(status))
            self.assertEqual(self.finish(process), status)
            self.assertEqual(self.recorded(), [])
        self.assertEqual(self.finish(self.guarded(300, 'killed')), 137)
        self.assertNotEqual(self.finish(self.guarded(300, 'exit', command=self.root / 'missing.py')), 0)

    def test_without_the_guard_the_same_tree_outlives_its_entry_process(self):
        # The H3 defect as the probe saw it: the runner stops only the entry process.
        process = self.start([sys.executable, '-I', '-B', str(self.command)], 'stall')
        entry, child = self.recorded(wait=30)
        self.assertEqual(entry, process.pid)
        process.kill()
        self.assertEqual(self.finish(process), -signal.SIGKILL)
        os.kill(child, 0)
        self.assertFalse(drain(process.stdout)[1])


class StepTests(ProcessCase):
    def setUp(self):
        super().setUp()
        binary = self.root / 'bin'
        binary.mkdir()
        # `python` is this protected interpreter. The one step that is not a
        # gate phase would install from the network; it runs the stand-in.
        python = binary / 'python'
        python.write_text('#!/bin/sh\ncase "$*" in "-I -B -m pip install requests") exec '
                          + shlex.quote(sys.executable) + ' -I -B ' + shlex.quote(str(self.command)) + ' pip;; esac\n'
                          'exec ' + shlex.quote(sys.executable) + ' "$@"\n')
        python.chmod(0o700)
        (self.root / 'section11-gate.py').write_text(COMMAND)

    def step(self, name, mode, seconds=None, **env):
        source = script(steps(workflows()[0])[name])
        match = EXEC.match(source.splitlines()[-1])
        self.assertIsNotNone(match, name)
        if seconds is not None:
            # Only the number of seconds differs from the copied template.
            shorter = match.group(0).replace(' ' + match.group(1) + ' python', ' ' + str(seconds) + ' python')
            source = source.replace(match.group(0), shorter)
        path = self.root / 'step.sh'
        path.write_text(source)
        return self.start(['/bin/bash', '--noprofile', '--norc', '-e', '-o', 'pipefail', str(path)], mode,
                          RUNNER_TEMP=str(self.root), PATH=str(self.root / 'bin'), **env)

    def test_every_guarded_step_fails_at_its_deadline_with_no_process_left(self):
        names = [name for name in GUARDED if name != SELECT]
        self.assertEqual(len(names), 9)
        for name in names:
            with self.subTest(step=name):
                process = self.step(name, 'stall', seconds=1)
                self.assertEqual(self.finish(process), 124)
                self.assertStopped(process)
                self.assertIn(b'::error::Step deadline of 1 seconds reached', drain(process.stderr)[0])

    def test_cancelling_a_step_signals_the_guard_as_its_entry_process(self):
        process = self.step('Run sync', 'stall')
        self.assertEqual(len(self.recorded(wait=30)), 2)
        process.send_signal(signal.SIGINT)
        self.assertEqual(self.finish(process), 128 + signal.SIGINT)
        self.assertStopped(process)

    def test_steps_pass_arguments_and_status_through_unchanged(self):
        env = {'RUNTIME_TAG': '2026.11.09', 'RUNTIME_COMMIT': 'a' * 40, 'RUNTIME_DIGEST': 'b' * 64,
               'APPLICATION_TAG': '2026.11.08', 'APPLICATION_COMMIT': 'c' * 40, 'APPLICATION_DIGEST': 'd' * 64}
        runtime = ['--tag', '2026.11.09', '--commit', 'a' * 40, '--wrapper-api', '2', '--manifest-sha256', 'b' * 64]
        application = ['--application-tag', '2026.11.08', '--application-commit', 'c' * 40,
                       '--application-sha256', 'd' * 64]
        process = self.step('Run sync', 'exit', H3_STATUS='7', **env)
        self.assertEqual(self.finish(process), 7)
        self.assertEqual(self.recorded(), ['sync', *runtime, *application])
        process = self.step('Publish data and update README', 'exit', **env)
        self.assertEqual(self.finish(process), 0)
        self.assertEqual(self.recorded(), ['publish', *runtime, *application])
        for force, extra in (('false', []), ('true', ['--force-release-download'])):
            process = self.step('Prepare operation', 'exit', FORCE_RELEASE_DOWNLOAD=force, **env)
            self.assertEqual(self.finish(process), 0)
            self.assertEqual(self.recorded(), ['prepare', *runtime, '--accept-install', *extra])
        process = self.step('Install dependencies', 'exit', H3_STATUS='3')
        self.assertEqual(self.finish(process), 3)
        self.assertEqual(self.recorded(), ['pip'])


class Controller:
    """The hosted adapter's context contract, with a scripted publication."""
    def __init__(self, result=None):
        self.info = {'base': 'a' * 40, 'run_sync': True}
        self.result = result
        self.during = None
        self.calls = []

    def context(self, value=None):
        if value is None:
            return dict(self.info)
        self.info = dict(value)

    def publish_data(self):
        self.during = self.context()
        if self.result is not None:
            raise self.result
        self.context(dict(self.context(), published=True))

    def validate_generated(self):
        self.calls.append('validate')

    def run_sync(self, *, isolated):
        self.calls.append(('sync', isolated))

    cache_prepare = finalize_export = cache_promote = validate_generated


class PublicationTests(Offline):
    def maintain(self, info):
        """Maintenance with a known data outcome proceeds to its own checks."""
        with mock.patch.object(hosted, 'context', return_value=info), \
                mock.patch.object(hosted, 'publisher') as publisher, \
                mock.patch.object(hosted, 'maintenance_due', return_value=False), \
                contextlib.redirect_stdout(io.StringIO()):
            hosted.maintain(runtime=mock.Mock())
        return publisher

    def test_publication_is_uncertain_until_this_process_reports_a_known_result(self):
        controller = Controller()
        R.run_phase(controller, 'publish')
        self.assertIs(controller.during['publication_uncertain'], True)
        self.assertEqual(controller.info, {'base': 'a' * 40, 'run_sync': True, 'published': True})
        self.maintain(controller.info).assert_called_once()

    def test_known_refusal_stays_known_and_unknown_or_interrupted_stays_uncertain(self):
        controller = Controller(ValueError('latest.json was not updated by this sync'))
        with self.assertRaisesRegex(ValueError, 'not updated'):
            R.run_phase(controller, 'publish')
        self.assertIs(controller.during['publication_uncertain'], True)
        self.assertEqual(controller.info, {'base': 'a' * 40, 'run_sync': True})
        self.maintain(controller.info).assert_called_once()
        for failure in (hosted.UnknownOutcome('publication outcome unknown'), RuntimeError('not on history'),
                        hosted.APIError(502, 'refused'), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__):
                controller = Controller(failure)
                with self.assertRaises(type(failure)):
                    R.run_phase(controller, 'publish')
                self.assertIs(controller.info['publication_uncertain'], True)
                with mock.patch.object(hosted, 'context', return_value=controller.info), \
                        mock.patch.object(hosted, 'publisher') as publisher, \
                        self.assertRaisesRegex(hosted.UnknownOutcome, 'no maintenance attempted'):
                    hosted.maintain(runtime=mock.Mock())
                publisher.assert_not_called()

    def test_other_phases_do_not_touch_the_publication_record(self):
        controller = Controller()
        controller.context = mock.Mock(side_effect=AssertionError('context is for publication only'))
        for phase in ('cache-prepare', 'finalize-export', 'validate', 'cache-promote'):
            R.run_phase(controller, phase)
        R.run_phase(controller, 'sync')
        self.assertEqual(controller.calls, ['validate'] * 4 + [('sync', True)])


class StoppedPublisherTests(ProcessCase):
    def test_publisher_stopped_at_its_deadline_leaves_maintenance_nothing_to_act_on(self):
        context = self.root / 'section11-hosted-context.json'
        context.write_text(json.dumps({'base': 'a' * 40, 'run_sync': True, 'published': False}))
        publisher = self.root / 'publisher.py'
        publisher.write_text(PUBLISHER)
        process = self.guarded(1, 'stall', command=publisher, H3_MAINT=str(MAINT), H3_CONTEXT=str(context))
        self.assertEqual(self.finish(process), 124)
        self.assertStopped(process, count=1)
        info = json.loads(context.read_text())
        self.assertEqual(info, {'base': 'a' * 40, 'run_sync': True, 'published': False,
                                'publication_uncertain': True})
        with mock.patch.object(hosted, 'context', return_value=info), \
                mock.patch.object(hosted, 'publisher') as pub, \
                self.assertRaisesRegex(hosted.UnknownOutcome, 'no maintenance attempted'):
            hosted.maintain(runtime=mock.Mock())
        pub.assert_not_called()
