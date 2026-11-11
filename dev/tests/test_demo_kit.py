"""Offline synthetic demo, existing publication validator and wrapper fidelity."""
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import re
import shlex
import subprocess
import sys
from datetime import date
from pathlib import Path
from unittest import mock

from test_docs_contract import markdown_links
from test_update_prototype import Offline, ROOT, inventory, validate_data, write
from test_final_workflow_cp4 import deadline_guard, steps, R
from test_b2_hosted import H, Remote, DirectPublisher, release


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'dev/demo' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G = load('section11_demo_generator', 'generate.py')
B = load('section11_demo_builder', 'build_demo.py')

INTERNAL_TERMS = re.compile(
    r'\b(?:round[\s_-]*\d+|workers?|coach|astra|t3|fixtures?|prototypes?'
    r'|checkpoint|rehearsal|pilot-workspace)\b|(?:reference|working)/jobs/',
    re.IGNORECASE,
)


class DemoTests(Offline):
    def source(self):
        source = self.root / 'sealed-source'
        if not source.exists():
            paths = ['LICENSE', 'manifest.json', 'dev/demo/generate.py', 'examples/maintenance/CUSTOM_README.md',
                     'examples/json-auto-sync/auto-sync.yml']
            paths += [p.relative_to(ROOT).as_posix() for p in (ROOT / 'dev/demo/templates').rglob('*') if p.is_file()]
            files = {name: (ROOT / name).read_bytes() for name in paths}
            # Exercise the actual release workflow and its unchanged manifest.
            write(source, files)
        return source

    def produce(self, day=date(2026, 10, 24)):
        with contextlib.redirect_stdout(io.StringIO()):
            G.produce(self.root, day)

    def test_deterministic_per_date_and_next_date_changes(self):
        self.produce()
        first = inventory(self.root)
        self.produce()
        self.assertEqual(inventory(self.root), first)
        self.produce(date(2026, 10, 25))
        second = inventory(self.root)
        self.assertEqual(set(first), set(G.FILES))
        self.assertTrue(all(first[name] != second[name] for name in G.FILES))

    def test_default_date_is_utc_not_local_clock(self):
        with mock.patch.object(G, 'datetime') as clock, contextlib.redirect_stdout(io.StringIO()):
            clock.now.return_value.date.return_value = date(2026, 10, 24)
            G.produce(self.root)
            clock.now.assert_called_once_with(G.timezone.utc)
        self.assertEqual(json.loads((self.root / 'latest.json').read_bytes())['metadata']['last_updated'],
                         '2026-10-24T00:00:00Z')

    def test_only_invented_labelled_data_and_stdlib_no_external_inputs(self):
        self.produce()
        code = (ROOT / 'dev/demo/generate.py').read_text()
        modules = {node.module.split('.')[0] for node in ast.walk(ast.parse(code)) if isinstance(node, ast.ImportFrom)}
        modules.update(alias.name.split('.')[0] for node in ast.walk(ast.parse(code))
                       if isinstance(node, ast.Import) for alias in node.names)
        self.assertEqual(modules, {'argparse', 'json', 'datetime', 'pathlib'})
        for name in G.FILES:
            document = json.loads((self.root / name).read_bytes())
            self.assertIs(document['metadata']['synthetic'], True)
            self.assertIn('no real person', document['metadata']['notice'])
        latest = json.loads((self.root / 'latest.json').read_bytes())
        self.assertEqual(latest['athlete_profile']['name'], 'Fictional Demo Rider')
        self.assertIsNone(latest['athlete_profile']['location'])
        self.assertEqual(latest['fitness_metrics']['status'], 'unavailable')
        self.assertTrue(all(a['id'].startswith('demo-') and a['synthetic'] for a in latest['activities']))
        self.assertEqual(json.loads((self.root / 'routes.json').read_bytes())['events'], [])

    def test_owner_files_and_managed_install_preserved(self):
        for name in ('DOSSIER.md', 'custom/preferences.json', 'section11/sentinel.txt'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('preserve')
        self.produce()
        for name in ('DOSSIER.md', 'custom/preferences.json', 'section11/sentinel.txt'):
            self.assertEqual((self.root / name).read_text(), 'preserve')

    def test_owner_authored_demo_explanation_is_preserved_at_its_live_path(self):
        output = self.root / 'kit'
        with contextlib.redirect_stdout(io.StringIO()):
            B.build(self.source(), output)
        about = (output / 'repo/demo/ABOUT_THIS_DEMO.md').read_bytes()
        self.assertEqual(about, (ROOT / 'dev/demo/templates/demo/ABOUT_THIS_DEMO.md').read_bytes())
        # Exact owner-authored public page from 6fb830d, not a rewritten demo README.
        self.assertEqual(hashlib.sha256(about).hexdigest(),
                         'a77732991f522b8b15a56a82705413d299a0f2ca527bce65a9de726a5ad75f65')
        self.assertTrue(about.startswith(b'# About this demo\n'))
        links = {target for _line, target, _syntax in markdown_links(about.decode())}
        for target in ('#demo-vs-real-setup',
                       'https://github.com/CrankAddict/section-11-demo/blob/main/section11/LICENSE',
                       'https://github.com/CrankAddict/section-11-demo/blob/main/section11/examples/json-local-sync/SETUP.md'):
            self.assertIn(target, links)
        self.assertFalse((output / 'repo/README.md').exists())
        self.assertFalse((output / 'repo/section11').exists())

    def test_first_install_supplies_the_standard_readme_without_demo_text(self):
        output = self.root / 'kit'
        with contextlib.redirect_stdout(io.StringIO()):
            B.build(self.source(), output)
        owner_files = inventory(output / 'repo')
        self.assertNotIn('README.md', owner_files)
        remote = Remote(owner_files)
        remote.repo = 'CrankAddict/section-11-demo'
        pub = DirectPublisher(remote)
        target = release()
        with contextlib.redirect_stdout(io.StringIO()):
            H.HostedUpdater(pub, lambda: target, {}).install(pub.snapshot(), accepted=True)
        installed = remote.inventory()
        expected = H.render_readme(None, (ROOT / H.README_TEMPLATE).read_bytes(),
                                   '_updated automatically_', remote.repo, pub.default)
        self.assertEqual(installed['README.md'], expected)
        self.assertTrue(expected.startswith(b'# Your Section 11 training data\n'))
        self.assertNotIn(b'# About this demo', expected)
        self.assertNotIn(b'# Section 11 public demo', expected)
        self.assertIn(b'[MIT licensed](section11/LICENSE)', expected)
        for name, data in owner_files.items():
            self.assertEqual(installed[name], data, name)

    def test_repository_output_excludes_legacy_and_owner_only_files(self):
        source = self.source()
        write(source / 'dev/demo/templates', {
            'README.md': b'# Section 11 public demo\n', 'LICENSE': b'legacy license\n',
            '.gitignore': b'legacy ignore rules\n', 'owner-notes.md': b'not for the repository\n'})
        output = self.root / 'kit'
        with contextlib.redirect_stdout(io.StringIO()):
            B.build(source, output)
        self.assertEqual({path.name for path in output.iterdir()}, {'SETUP_DEMO.md', 'repo'})
        for name in ('README.md', 'LICENSE', '.gitignore', 'SETUP_DEMO.md', 'owner-notes.md'):
            self.assertFalse((output / 'repo' / name).exists(), name)
        self.assertTrue((output / 'repo/demo/ABOUT_THIS_DEMO.md').is_file())
        self.assertTrue((output / 'repo/custom/README.md').is_file())

    def test_public_templates_use_user_facing_terms(self):
        output = self.root / 'kit'
        with contextlib.redirect_stdout(io.StringIO()):
            B.build(self.source(), output)
        templates = ROOT / 'dev/demo/templates'
        markdown = sorted(templates.rglob('*.md'))
        self.assertEqual({p.relative_to(templates).as_posix() for p in markdown},
                         {'demo/ABOUT_THIS_DEMO.md', 'SETUP_DEMO.md', 'DOSSIER.md'})
        for path in markdown:
            with self.subTest(path=path.name):
                text = path.read_text()
                self.assertIsNone(INTERNAL_TERMS.search(text))
                base = output if path.name == 'SETUP_DEMO.md' else output / 'repo'
                self.assertEqual((base / path.relative_to(templates)).read_text(), text)
        for term in ('Round 4', 'round-7', 'worker', 'Coach', 'Astra', 'T3 job',
                     'fixture release', 'prototype kit', 'checkpoint', 'rehearsal',
                     'pilot-workspace', 'reference/jobs/example', 'working/jobs/example'):
            with self.subTest(term=term):
                self.assertIsNotNone(INTERNAL_TERMS.search(term))
        self.assertIsNone(INTERNAL_TERMS.search(
            'Use an official date release, not a test or development copy. '
            'GitHub supplies the job token. Keep this demo fictional.'))
        setup = (output / 'SETUP_DEMO.md').read_text()
        self.assertIn('Do not use a test kit or development files.', setup)

    def test_kit_complete_owner_files_and_exact_workflow_exceptions(self):
        output = self.root / 'kit'
        with contextlib.redirect_stdout(io.StringIO()):
            B.build(self.source(), output)
        self.assertEqual(set(inventory(output)), {
            'SETUP_DEMO.md', 'repo/DOSSIER.md', 'repo/custom/README.md', 'repo/demo/ABOUT_THIS_DEMO.md',
            'repo/demo/generate.py', 'repo/.github/workflows/auto-sync.yml'})
        auto = (output / 'repo/.github/workflows/auto-sync.yml').read_text()
        original = (self.source() / 'examples/json-auto-sync/auto-sync.yml').read_text()
        start = original.index('      - name: Prepare slow cache staging\n')
        end = original.index('      - name: Verify generated data\n', start)
        demo = '      - name: ' + steps(auto)['Generate clearly fictional daily data']
        restored = auto.replace(demo, original[start:end])
        start = original.index('      - name: Prepare changed slow sources for saving\n')
        end = original.index('      - name: Eligible update maintenance\n', start)
        restored = restored.replace('      - name: Eligible update maintenance\n',
                                    original[start:end] + '      - name: Eligible update maintenance\n')
        restored = restored.replace("- cron: '7 5 * * *'", "- cron: '7,37 * * * *'")
        self.assertEqual(restored, original)
        self.assertNotIn('secrets.', auto)
        self.assertNotIn('--rehearsal', auto)
        self.assertFalse((output / 'repo/section11').exists())
        setup = (output / 'SETUP_DEMO.md').read_text()
        for required in ('first official', 'workflow', 'SECTION11_AUTO_UPDATE', 'no official date release',
                         'No PR-creation or merge setting', 'sha', 'Status', 'Rollback'):
            self.assertIn(required.lower(), setup.lower())
        prose = ' '.join(setup.split())
        self.assertIn('guarded workflow (workflow v11.111 or later)', prose)
        self.assertIn('This kit does not create the repository or install a release for you.', prose)
        self.assertIn('a test kit or development files', prose)
        with self.assertRaises(FileExistsError):
            B.build(self.source(), output)

    def test_unsealed_demo_refuses_before_creating_output(self):
        source = self.source()
        path = source / 'examples/json-auto-sync/auto-sync.yml'
        path.write_text(path.read_text().replace("<<'SECTION11_GATE'", "<<'UNSEALED'"))
        with self.assertRaisesRegex(ValueError, 'published sealed workflow'):
            B.build(source, self.root / 'refused')
        self.assertFalse((self.root / 'refused').exists())

    def test_modified_workflow_refuses_before_any_output(self):
        source = self.source()
        path = source / B.WORKFLOW
        original = path.read_bytes()
        changes = {
            'gate': (b"LIMIT = 1024 * 1024", b"LIMIT = 2 * 1024 * 1024", 'fixed gate differs'),
            'gate delimiter': (b"<<'SECTION11_GATE'", b"<<'OTHER_GATE'", 'fixed gate'),
            'deadline': (b'child = subprocess.Popen', b'child = unsafe.Popen', 'release manifest'),
            'runtime': (b'CrankAddict/section-11/', b'example/untrusted/', 'release manifest'),
            'phase': (b'--wrapper-api 2', b'--wrapper-api 3', 'release manifest'),
            'condition': (b"if: steps.prepare.outputs.run_sync == 'true'", b'if: always()', 'release manifest'),
            'schedule': (b"7,37 * * * *", b"7 * * * *", 'release manifest'),
        }
        for name, (before, after, error) in changes.items():
            with self.subTest(name=name):
                self.assertIn(before, original)
                path.write_bytes(original.replace(before, after, 1))
                prior = inventory(self.root)
                with self.assertRaisesRegex(ValueError, error):
                    B.build(source, self.root / 'refused')
                self.assertEqual(inventory(self.root), prior)
                self.assertFalse((self.root / 'refused').exists())

    def test_missing_malformed_or_mismatched_manifest_refuses(self):
        source = self.source()
        path = source / 'manifest.json'
        original = path.read_bytes()
        obj = json.loads(original)
        del obj['files'][B.WORKFLOW]
        for raw in (None, b'{', b'{"files":{},"files":{}}', json.dumps(obj).encode(),
                    original.replace(json.loads(original)['files'][B.WORKFLOW]['hash'].encode(), b'0' * 64)):
            with self.subTest(raw=raw is None):
                if raw is None:
                    path.unlink()
                else:
                    path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, 'published sealed workflow'):
                    B.build(source, self.root / 'refused')
                self.assertFalse((self.root / 'refused').exists())

    def test_legacy_workflow_and_mixed_pins_refuse(self):
        source = self.source()
        path = source / B.WORKFLOW
        original = path.read_bytes()
        legacy = (ROOT / 'dev/fixtures/hosted/json-auto-sync-v11.105.yml').read_bytes()
        for raw in (legacy, original + b'      BOOTSTRAP_BLOB: ' + b'a' * 40 + b'\n'):
            with self.subTest(legacy=raw == legacy):
                path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, 'legacy or unsealed'):
                    B.build(source, self.root / 'refused')
                self.assertFalse((self.root / 'refused').exists())

    def test_step_boundaries_refuse_new_duplicate_or_reordered_steps(self):
        text = (self.source() / B.WORKFLOW).read_text()
        names = ('Prepare slow cache staging', 'Restore slow sources', 'Run sync')
        following = 'Verify generated data'
        anchor = '      - name: Run sync\n'
        for replacement in ('      - name: Unexpected new step\n' + anchor,
                            anchor + anchor, '      - name: Renamed sync\n'):
            with self.subTest(replacement=replacement):
                with self.assertRaisesRegex(ValueError, 'demo workflow step'):
                    B.replace_steps(text.replace(anchor, replacement), names, following, B.DEMO_STEP)
        with self.assertRaisesRegex(ValueError, 'step order'):
            B.replace_steps(text, (names[1], names[0], names[2]), following, B.DEMO_STEP)
        result = B.replace_steps(text, names, following, B.DEMO_STEP)
        self.assertEqual(result.count('Generate clearly fictional daily data'), 1)
        self.assertIn('      - name: Verify generated data\n', result)

    def test_real_workflow_guard_identity_order_and_conditions(self):
        source = self.source()
        self.assertIn('finalize-export', R.PHASES)
        self.assertEqual((source / B.WORKFLOW).read_bytes(), (ROOT / B.WORKFLOW).read_bytes())
        self.assertEqual((source / 'manifest.json').read_bytes(), (ROOT / 'manifest.json').read_bytes())
        auto = B.sync_workflow(source)
        original = steps((source / B.WORKFLOW).read_text())
        blocks = steps(auto)
        generate = blocks['Generate clearly fictional daily data']
        self.assertEqual(list(blocks)[-5:], ['Generate clearly fictional daily data', 'Verify generated data',
                         'Publish data and update README', 'Eligible update maintenance', 'Upload data files for download'])
        for name in ('Verify generated data', 'Publish data and update README',
                     'Eligible update maintenance', 'Upload data files for download'):
            self.assertEqual(blocks[name], original[name])
        self.assertIn("        if: steps.prepare.outputs.run_sync == 'true'\n", generate)
        self.assertIn('        id: sync\n', generate)
        self.assertIn('        shell: bash\n', generate)
        self.assertNotIn('continue-on-error', generate)
        self.assertNotRegex(auto, r'steps\.(?:slow_cache_context|slow_cache_save_file)\.|steps\.sync\.outputs\.')
        self.assertNotIn('section11-trusted-source/examples/maintenance/hosted.py', auto)
        self.assertNotIn('secrets.', auto)
        env = generate.split('        env:\n', 1)[1].split('        shell:', 1)[0]
        expected_env = original['Verify generated data'].split('        env:\n', 1)[1].split('        run:', 1)[0]
        self.assertEqual(env, expected_env)
        commands = [line[10:] for line in generate.split('        run: |\n', 1)[1].splitlines()]
        self.assertEqual(commands[0], 'python -I -B "$RUNNER_TEMP/section11-deadline.py" 30 python -I -B demo/generate.py')
        validate = original['Verify generated data'].split('        run: ', 1)[1].strip()
        self.assertEqual(commands[1], validate.replace('section11-gate.py" validate ', 'section11-gate.py" finalize-export '))
        self.assertEqual(len(commands), 2)
        seconds = sum(int(re.search(r'section11-deadline.py" (\d+)', command)[1]) for command in commands)
        minutes = int(re.search(r'timeout-minutes: (\d+)', generate)[1])
        self.assertGreaterEqual(minutes * 60 - seconds, 30)
        self.assertEqual(B.SEAL.embedded_gate(auto.encode()), (ROOT / 'dev/hosted_gate.py').read_bytes())
        self.assertEqual(deadline_guard(auto), deadline_guard((source / B.WORKFLOW).read_text()))
        self.assertEqual(re.findall(r"(?m)^    - cron: (.+)$", auto), ["'7 5 * * *'"])

    def test_changed_identity_or_missing_deadline_requires_builder_review(self):
        text = (self.source() / B.WORKFLOW).read_text()
        B.require_phase_contract(text)
        for before, after in (('--application-sha256', '--new-application-digest'),
                              ('steps.bootstrap.outputs.manifest_sha256', 'steps.bootstrap.outputs.new_digest'),
                              ("<<'SECTION11_DEADLINE'", "<<'RENAMED_DEADLINE'")):
            with self.subTest(before=before):
                with self.assertRaisesRegex(ValueError, 'identity or deadline contract changed'):
                    B.require_phase_contract(text.replace(before, after))

    def test_generated_step_runs_and_propagates_producer_and_gate_failures(self):
        auto = B.sync_workflow(self.source())
        block = steps(auto)['Generate clearly fictional daily data']
        script = '\n'.join(line[10:] for line in block.split('        run: |\n', 1)[1].splitlines())
        # Use the test interpreter for every Python process, as on the runner.
        script = script.replace('python ', shlex.quote(sys.executable) + ' ')
        for producer_status, gate_status in ((0, 0), (7, 0), (0, 9)):
            with self.subTest(producer=producer_status, gate=gate_status):
                run = self.root / ('run-' + str(producer_status) + '-' + str(gate_status))
                record = run / 'gate-arguments.json'
                producer = ((ROOT / 'dev/demo/generate.py').read_bytes() if not producer_status
                            else b'import sys\nsys.exit(7)\n')
                write(run, {'demo/generate.py': producer,
                            'section11-deadline.py': deadline_guard(auto).encode(),
                            'section11-gate.py': b'import json, os, sys\nfrom pathlib import Path\n'
                                b'root = Path(os.environ["RUNNER_TEMP"])\n'
                                b'assert (root / "latest.json").is_file()\n'
                                b'(root / "gate-arguments.json").write_text(json.dumps(sys.argv[1:]))\n'
                                b'sys.exit(int(os.environ["DEMO_GATE_STATUS"]))\n'})
                env = {'PATH': '/bin:/usr/bin', 'RUNNER_TEMP': str(run), 'TMPDIR': str(self.root),
                       'RUNTIME_TAG': '2026.11.11', 'RUNTIME_COMMIT': 'a' * 40, 'RUNTIME_DIGEST': 'b' * 64,
                       'APPLICATION_TAG': '2026.11.10', 'APPLICATION_COMMIT': 'c' * 40,
                       'APPLICATION_DIGEST': 'd' * 64, 'DEMO_GATE_STATUS': str(gate_status)}
                result = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-e', '-o', 'pipefail', '-c', script],
                                        cwd=run, env=env, capture_output=True, timeout=20)
                self.assertEqual(result.returncode, producer_status or gate_status, result.stderr)
                self.assertEqual(record.exists(), producer_status == 0)
                if producer_status == 0:
                    self.assertEqual(json.loads(record.read_text()), [
                        'finalize-export', '--tag', env['RUNTIME_TAG'], '--commit', env['RUNTIME_COMMIT'],
                        '--wrapper-api', '2', '--manifest-sha256', env['RUNTIME_DIGEST'],
                        '--application-tag', env['APPLICATION_TAG'], '--application-commit', env['APPLICATION_COMMIT'],
                        '--application-sha256', env['APPLICATION_DIGEST']])

    def test_current_owner_instructions_match_workflow(self):
        output = self.root / 'kit'
        with contextlib.redirect_stdout(io.StringIO()):
            B.build(self.source(), output)
        for name in ('SETUP_DEMO.md',):
            text = ' '.join((output / name).read_text().split())
            self.assertNotIn('Old workflow only', text)
            self.assertNotIn('04:00 UTC', text)
            self.assertIn('ten-minute', text)
            self.assertIn('05:07 UTC', text)
        setup = ' '.join((output / 'SETUP_DEMO.md').read_text().split())
        self.assertIn('Use for the first Sync after adopting this workflow', setup)
        self.assertIn('SECTION11_SYNC_TIMER', setup)
        for text in (setup, ' '.join((ROOT / 'dev/README.md').read_text().split())):
            for phrase in ('demo/ABOUT_THIS_DEMO.md', 'description', 'homepage',
                           'repo/.github/workflows/auto-sync.yml',
                           'Never replace the root README of a running demo',
                           'failed run with no data commit', 'Hosted acquisition or phase verification failed'):
                self.assertIn(phrase, text)
