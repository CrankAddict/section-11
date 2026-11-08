"""11d/11e/11f/11g/12a document contracts and direct violation controls."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from test_docs_contract import heading_ids

ROOT = Path(__file__).resolve().parents[2]
AI_DOCS = ('SKILL.md', 'PROJECT_INSTRUCTIONS_AGENTIC.md',
           'PROJECT_INSTRUCTIONS_WEB.md', 'SECTION_11.md')


def copied_reference_issues(text, installed):
    """Check explicit data-root paths, including anchors inside copied fences."""
    errors = []
    for reference in re.findall(r'[\w./-]+\.md#[\w-]+', text):
        path, anchor = reference.split('#')
        if not path.startswith('section11/') or path not in installed:
            errors.append(reference)
        elif anchor not in heading_ids(installed[path]):
            errors.append(reference)
    return errors


def ai_contract(text):
    value = ' '.join(text.replace('`', '').split())
    errors = []
    for phrase in ('documents live in section11/', 'custom files in custom/',
                   'user data in the', 'only when the user points to it',
                   'section11/SECTION_11.md', 'section11/examples/reports/',
                   'connected repo', 'uploaded/attached files', 'user-supplied links'):
        if phrase not in value:
            errors.append(phrase)
    if not re.search(r'(missing.*ask|ask.*missing)', value):
        errors.append('missing-file request')
    for forbidden in ('./SECTION_11.md', 'data directory reports/', 'root copy',
                      'root copies', 'both root and',
                      'raw.githubusercontent.com/CrankAddict/section-11/main/',
                      'github.com/CrankAddict/section-11/tree/main/examples/reports',
                      'fetched from CrankAddict/section-11'):
        if forbidden in value:
            errors.append(forbidden)
    return errors


class AlignmentDocsTests(unittest.TestCase):
    def test_copied_contract_and_heartbeat_references_resolve_from_data_root(self):
        names = ('PROJECT_INSTRUCTIONS_AGENTIC.md', 'PROJECT_INSTRUCTIONS_WEB.md',
                 'examples/agentic/openclaw/HEARTBEAT_TEMPLATE.md')
        installed = {'section11/' + name: (ROOT / name).read_text() for name in
                     ('SECTION_11.md', 'examples/agentic/EXTERNAL_APIS.md')}
        for name in names:
            source = (ROOT / name).read_text()
            copied = source.split('```')[1] if name.startswith('PROJECT_') else source
            with self.subTest(name=name):
                # Source document and copied payload use the same explicit base;
                # no relative Markdown href depends on the paste destination.
                for text in (source, copied):
                    self.assertEqual(copied_reference_issues(text, installed), [])
                    self.assertIn('regardless of where', text)
                    self.assertRegex(text, r'data (?:folder|repository root)')
                    self.assertNotRegex(text, r'\]\([^)]*(?:SECTION_11|EXTERNAL_APIS)\.md')
                self.assertGreaterEqual(len(re.findall(r'section11/[^`\s]+\.md#', copied)), 3)
                self.assertTrue(copied_reference_issues(copied.replace('section11/SECTION_11.md#', 'SECTION_11.md#'), installed))
                self.assertTrue(copied_reference_issues(copied.replace('#which-interval-data-to-use', '#missing-heading'), installed))
        self.assertEqual(copied_reference_issues('`section11/SECTION_11.md#shared-report-layout`', installed), [])

    def test_setup_openclaw_uses_installed_skill_and_heartbeat_only(self):
        text = (ROOT / 'SETUP_ASSISTANT.md').read_text().split('**OpenClaw:**', 1)[1].split('**Claude Code:**', 1)[0]
        self.assertIn('section11/SKILL.md', text)
        self.assertIn('section11/examples/agentic/openclaw/HEARTBEAT_TEMPLATE.md', text)
        self.assertEqual(text.count('If unavailable, ask the user'), 2)
        self.assertNotIn('or from the repo root', text)
        self.assertNotIn('github.com/CrankAddict', text)

    def test_on_demand_overview_has_one_complete_repository_delivery(self):
        text = (ROOT / 'examples/json-on-demand/SETUP.md').read_text().split('## Overview', 1)[1].split('## Prerequisites', 1)[0]
        normalized = ' '.join(text.split())
        self.assertIn('connector or link', normalized)
        self.assertIn('Code > Download ZIP', normalized)
        self.assertIn('It includes `section11/`', normalized)
        self.assertIn('artifact is a data-only extra', normalized)
        self.assertNotIn('download the resulting files as a ZIP artifact', text)
        self.assertNotIn('with no extra steps', text)

    def test_conversion_warning_is_conditional_in_hosted_guides(self):
        for name in ('examples/json-auto-sync/SETUP.md', 'examples/json-on-demand/SETUP.md', 'SETUP_ASSISTANT.md'):
            text = ' '.join((ROOT / name).read_text().split())
            self.assertIn('Brand-new repositories can skip this warning', text, name)
            self.assertIn('already ha', text, name)

    def test_cloud_instructions_choose_final_folder_and_retarget_after_whole_move(self):
        for name in ('examples/json-local-sync/SETUP.md', 'SETUP_ASSISTANT.md'):
            text = ' '.join((ROOT / name).read_text().split())
            self.assertIn('final data directory before `--init`', text)
            self.assertIn('move the whole data folder including `section11/` and `.sync_config`', text)
            self.assertIn('`python3 section11/examples/sync.py --update` once from the new folder', text)
            self.assertNotIn("timer's `--output`", text)

    def test_local_dossier_copy_preserves_existing_files_and_dangling_links(self):
        guide = (ROOT / 'examples/json-local-sync/SETUP.md').read_text()
        command = next(line for line in guide.splitlines() if line.startswith('[ -e DOSSIER.md ]'))
        self.assertNotIn('cp -n ', guide)
        self.assertIn('├── sync.log', guide)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'section11').mkdir()
            (root / 'section11/DOSSIER_TEMPLATE.md').write_bytes(b'template')
            def copy():
                subprocess.run(['/bin/sh', '-c', command], cwd=root, check=True, capture_output=True)
            copy()
            self.assertEqual((root / 'DOSSIER.md').read_bytes(), b'template')
            (root / 'DOSSIER.md').write_bytes(b'existing private dossier')
            copy()
            self.assertEqual((root / 'DOSSIER.md').read_bytes(), b'existing private dossier')
            (root / 'DOSSIER.md').unlink()
            (root / 'DOSSIER.md').symlink_to('missing-dossier')
            copy()
            self.assertTrue((root / 'DOSSIER.md').is_symlink())
            self.assertFalse((root / 'missing-dossier').exists())

    def test_gemini_caution_has_conditional_fallback_without_fixed_limits(self):
        sections = ((ROOT / 'README.md').read_text().split('#### Gemini (Gems)', 1)[1].split('\n#### ', 1)[0],
                    (ROOT / 'SETUP_ASSISTANT.md').read_text().split('- **Gemini Gems:**', 1)[1].split('\n', 1)[0])
        for section in sections:
            text = ' '.join(section.split())
            self.assertIn('Gemini limits ZIP uploads', text)
            self.assertIn('If a Gem rejects or truncates the ZIP', text)
            self.assertIn('repository import in an ordinary Gemini chat', text)
            self.assertNotRegex(text.split('Gemini limits ZIP uploads', 1)[1], r'\d')

    def test_every_manual_delivery_summary_includes_optional_dossier(self):
        starts = {'README.md': '- **Manual export:**',
                  'SETUP_ASSISTANT.md': '- **Manual export:**',
                  'examples/json-local-sync/SETUP.md': 'For manual uploads,',
                  'examples/json-manual/SETUP.md': 'Include `DOSSIER.md`'}
        for name, start in starts.items():
            text = (ROOT / name).read_text()
            summary = text[text.index(start):].split('\n\n', 1)[0]
            normalized = ' '.join(summary.replace('`', '').replace('>', '').split())
            with self.subTest(name=name):
                self.assertIn('DOSSIER.md if used', normalized)
                self.assertIn('ZIP of the section11/ folder only', normalized)
                self.assertIn('Never zip the whole data folder', normalized)

    def test_external_sources_is_attribution_without_fetch_instructions(self):
        text = (ROOT / 'SKILL.md').read_text()
        section = text.split('**External Sources**', 1)[1].split('\n**', 1)[0]
        normalized = ' '.join(section.split())
        self.assertIn('files are maintained in the open-source', normalized)
        self.assertIn('https://github.com/CrankAddict/section-11', normalized)
        self.assertIn('can be inspected there', normalized)
        self.assertNotRegex(section.lower(), r'fetch|download|raw\.githubusercontent|/main/')

    def test_all_ai_contracts_have_one_installed_layout_and_retained_delivery_paths(self):
        for name in AI_DOCS:
            text = (ROOT / name).read_text()
            with self.subTest(name=name):
                self.assertEqual(ai_contract(text), [])
                self.assertEqual(text.count('documents live in'), 1)

    def test_old_root_and_official_main_fallbacks_are_direct_violations(self):
        text = (ROOT / 'SKILL.md').read_text()
        self.assertEqual(ai_contract(text), [])
        for addition in ('\nCheck ./SECTION_11.md',
                         '\nUse data directory reports/',
                         '\nFetch https://raw.githubusercontent.com/CrankAddict/section-11/main/SECTION_11.md'):
            self.assertTrue(ai_contract(text + addition))
        self.assertEqual(ai_contract(text + '\nUse the user-supplied links for installed files.'), [])

    def test_push_wording_keeps_preview_contract_and_only_managed_paths(self):
        text = (ROOT / 'SKILL.md').read_text()
        self.assertIn("If `push.py` is available (`section11/examples/agentic/push.py`), the skill can manage", text)
        self.assertIn('section11/examples/agentic/pull.py', text)
        self.assertNotIn('With verified execution and write authority', text)
        self.assertIn('require `--confirm` to write', text)

    def test_hosted_and_manual_zip_delivery_are_distinct_and_snapshots_explicit(self):
        for name in ('README.md', 'SETUP_ASSISTANT.md',
                     'examples/json-auto-sync/SETUP.md', 'examples/json-on-demand/SETUP.md'):
            text = ' '.join((ROOT / name).read_text().split())
            with self.subTest(name=name):
                self.assertIn('Download ZIP', text)
                self.assertRegex(text, r'connector or (?:a )?link')
                self.assertIn('snapshot', text)
                self.assertRegex(text.lower(), r're-upload for fresh data and after updates')
        for name in ('README.md', 'SETUP_ASSISTANT.md', 'examples/json-manual/SETUP.md',
                     'examples/json-local-sync/SETUP.md'):
            text = ' '.join((ROOT / name).read_text().replace('>', '').split())
            with self.subTest(name=name):
                self.assertIn('ZIP of the `section11/` folder only', text)
                self.assertIn('Never zip the whole data folder', text)
        setup = (ROOT / 'SETUP_ASSISTANT.md').read_text()
        self.assertNotIn('upload `SECTION_11.md`, plus `DOSSIER.md`', setup)
        self.assertIn('Direct them to: https://github.com/CrankAddict/section-11/blob/main/DOSSIER_TEMPLATE.md', setup)
        web = (ROOT / 'PROJECT_INSTRUCTIONS_WEB.md').read_text()
        self.assertIn('raw.githubusercontent.com/[USERNAME]/[REPO]/main/latest.json', web)
