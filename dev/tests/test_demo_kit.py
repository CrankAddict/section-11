"""Offline synthetic demo, existing publication validator and wrapper fidelity."""
import ast
import contextlib
import importlib.util
import io
import json
import re
import subprocess
from datetime import date
from pathlib import Path
from unittest import mock

from test_docs_contract import markdown_links
from test_update_prototype import Offline, ROOT, inventory, validate_data, write


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
            paths = ['LICENSE', 'dev/demo/generate.py', 'examples/maintenance/CUSTOM_README.md',
                     'examples/json-auto-sync/auto-sync.yml']
            paths += [p.relative_to(ROOT).as_posix() for p in (ROOT / 'dev/demo/templates').rglob('*') if p.is_file()]
            files = {name: (ROOT / name).read_bytes() for name in paths}
            name = 'examples/json-auto-sync/auto-sync.yml'
            files[name] = re.sub(rb'BOOTSTRAP_BLOB: [^\s]+', b'BOOTSTRAP_BLOB: ' + b'a' * 40, files[name])
            files[name] = re.sub(rb'BOOTSTRAP_SHA256: [^\s]+', b'BOOTSTRAP_SHA256: ' + b'b' * 64, files[name])
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

    def test_built_readme_explains_local_setup_and_installed_guide_links(self):
        output = self.root / 'kit'
        with contextlib.redirect_stdout(io.StringIO()):
            B.build(self.source(), output)
        readme = (output / 'README.md').read_text()
        self.assertEqual(readme, (ROOT / 'dev/demo/templates/README.md').read_text())
        self.assertIn('**fictional demo data**', readme)
        self.assertIn('Keep this repository entirely\nfictional.', readme)
        self.assertEqual(readme.count('## Local setup\n'), 1)
        local = readme.split('## Local setup\n', 1)[1]
        tree = local.split('```text\n', 1)[1].split('\n```', 1)[0]
        self.assertTrue(tree.startswith('training-data/\n'))
        self.assertRegex(tree, r'(?m)^[├└]── latest\.json, history\.json, .*# live JSON files$')
        for name, meaning in (('archive/', 'where present'), ('maps/', 'where present'),
                              ('section11/', 'managed official files'), ('custom/', 'personal files'),
                              ('DOSSIER.md', 'private dossier'), ('state/', 'private request accounting')):
            lines = [line for line in tree.splitlines() if line.startswith(('├── ' + name, '└── ' + name))]
            self.assertEqual(len(lines), 1, name)
            self.assertIn(meaning, lines[0])
        # State is named without displaying any private directory contents.
        self.assertTrue(all(line.startswith(('├── ', '└── ')) for line in tree.splitlines()[1:]))
        prose = ' '.join(local.split())
        for wording in ('Keep `state/` on the machine; never publish it.',
                        'Keep your real dossier private.',
                        'Auto sync is installed by default using launchd, systemd, cron or Windows Task Scheduler',
                        'explicit --no-timer choice keeps manual operation',
                        'manual by default and ask for your confirmation',
                        'opt into a daily update on the first run at or after 04:00 UTC',
                        'one-step rollback to the previous installation'):
            self.assertIn(wording, prose)
        links = {target for _line, target, _syntax in markdown_links(local)}
        self.assertEqual(links, {'section11/examples/json-local-sync/SETUP.md',
                                 'section11/examples/maintenance/UPDATING.md'})
        for target in links:
            self.assertTrue((ROOT / target.removeprefix('section11/')).is_file(), target)
        self.assertFalse((output / 'state').exists())
        self.assertFalse((output / 'section11').exists())

    def test_public_templates_use_user_facing_terms(self):
        output = self.root / 'kit'
        with contextlib.redirect_stdout(io.StringIO()):
            B.build(self.source(), output)
        templates = ROOT / 'dev/demo/templates'
        markdown = sorted(templates.rglob('*.md'))
        self.assertEqual({p.name for p in markdown}, {'README.md', 'SETUP_DEMO.md', 'DOSSIER.md'})
        for path in markdown:
            with self.subTest(path=path.name):
                text = path.read_text()
                self.assertIsNone(INTERNAL_TERMS.search(text))
                self.assertEqual((output / path.relative_to(templates)).read_text(), text)
        for term in ('Round 4', 'round-7', 'worker', 'Coach', 'Astra', 'T3 job',
                     'fixture release', 'prototype kit', 'checkpoint', 'rehearsal',
                     'pilot-workspace', 'reference/jobs/example', 'working/jobs/example'):
            with self.subTest(term=term):
                self.assertIsNotNone(INTERNAL_TERMS.search(term))
        self.assertIsNone(INTERNAL_TERMS.search(
            'Use an official date release, not a test or development copy. '
            'GitHub supplies the job token. Keep this demo fictional.'))
        readme = (output / 'README.md').read_text()
        self.assertIn('A test or development copy cannot\nsubstitute for an official release.', readme)

    def test_kit_complete_owner_files_and_exact_workflow_exceptions(self):
        output = self.root / 'kit'
        with contextlib.redirect_stdout(io.StringIO()):
            B.build(self.source(), output)
        self.assertEqual(set(inventory(output)), {
            'README.md', 'SETUP_DEMO.md', 'DOSSIER.md', 'LICENSE', '.gitignore', 'custom/README.md',
            'demo/generate.py', '.github/workflows/auto-sync.yml'})
        auto = (output / '.github/workflows/auto-sync.yml').read_text()
        original = (self.source() / 'examples/json-auto-sync/auto-sync.yml').read_text()
        start = original.index('      - name: Prepare slow cache staging\n')
        end = original.index('      - name: Verify generated data\n', start)
        restored = auto.replace('      - name: Generate clearly fictional daily data\n'
                                "        if: steps.prepare.outputs.run_sync == 'true'\n"
                                '        run: |\n'
                                '          python demo/generate.py\n'
                                '          python "$RUNNER_TEMP/section11-trusted-source/examples/maintenance/hosted.py" finalize-export --wrapper-api 2\n', original[start:end])
        start = original.index('      - name: Prepare changed slow sources for saving\n')
        end = original.index('      - name: Eligible update maintenance\n', start)
        restored = restored.replace('      - name: Eligible update maintenance\n',
                                    original[start:end] + '      - name: Eligible update maintenance\n')
        restored = restored.replace("- cron: '7 5 * * *'", "- cron: '7,37 * * * *'")
        self.assertEqual(restored, original)
        self.assertNotIn('secrets.', auto)
        self.assertNotIn('--rehearsal', auto)
        self.assertFalse((output / 'section11').exists())
        setup = (output / 'SETUP_DEMO.md').read_text()
        for required in ('first official', 'workflow', 'SECTION11_AUTO_UPDATE', 'no official date release',
                         'No PR-creation or merge setting', 'sha', 'Status', 'Rollback'):
            self.assertIn(required.lower(), setup.lower())
        prose = ' '.join(setup.split())
        self.assertIn('verified release updates (Protocol 11.103 / sync.py 3.166 or later)', prose)
        self.assertIn('This kit does not create the repository or install a release for you.', prose)
        self.assertIn('a test kit or development files', prose)
        with self.assertRaises(FileExistsError):
            B.build(self.source(), output)

    def test_unsealed_demo_refuses_before_creating_output(self):
        source = self.source()
        path = source / 'examples/json-auto-sync/auto-sync.yml'
        path.write_text(path.read_text().replace('BOOTSTRAP_BLOB: ' + 'a' * 40, 'BOOTSTRAP_BLOB: UNSEALED'))
        with self.assertRaisesRegex(ValueError, 'published sealed workflow'):
            B.build(source, self.root / 'refused')
        self.assertFalse((self.root / 'refused').exists())
