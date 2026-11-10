"""Dossier-template migration is independent of release/layout updates."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
OLDER_TEMPLATE = "   If it follows an older template, migrate rather than patch: preserve stable personal, health, medication, supplement, goal, equipment, fueling and preference context; remove duplicated dynamic metrics, zones, current phase, live schedule, load and readiness; move uncertain facts to open review items; add authority, revision, date, privacy and source configuration; and show a kept / moved / removed / needs-confirmation review before any replacement. Delete no old file without permission."


class SetupAssistantTests(unittest.TestCase):
    def test_both_dossier_routes_keep_template_migration_and_approval(self):
        text = (ROOT / 'SETUP_ASSISTANT.md').read_text()
        web = text.split('### Step 7: Athlete Dossier\n', 1)[1].split('### Step 8:', 1)[0]
        local = text.split('5. Handle the dossier.', 1)[1].split('6. First sync:', 1)[0]
        for route in (web, local):
            with self.subTest(route='web' if route is web else 'local'):
                for phrase in (
                    'use it as migration input rather than current truth',
                    'maintenance or migration, not creation',
                    'Propose a migration to the current template rather than silently restructuring their file.',
                ):
                    self.assertEqual(route.count(phrase), 1, phrase)
                self.assertIn('needs-confirmation review before', route)
                self.assertIn('approval', route)
        self.assertIn(OLDER_TEMPLATE, web)
        self.assertIn('Older template: migrate with a kept / moved / removed / needs-confirmation review before replacement.', local)

    def test_verified_release_guidance_survives_dossier_restoration(self):
        text = ' '.join((ROOT / 'SETUP_ASSISTANT.md').read_text().split())
        for phrase in (
            'first Sync installs and reads back the complete verified release and receipt',
            '`--init` verifies the official date release',
            'all commands use `section11/examples/sync.py`',
            'No PR-creation setting or new personal token is needed',
            'No PR or merge is required',
            'check after data work at most once every 10 minutes; failed checks count',
            'Default is manual `--update`',
            '"auto_update": true',
            '`--rollback` restores the one previous local installation',
        ):
            self.assertIn(phrase, text)
        self.assertNotIn('migrate_layout', text)

    def test_root_dossier_and_user_controlled_location_transition_are_consistent(self):
        for name in ('SETUP_ASSISTANT.md', 'PROJECT_INSTRUCTIONS_AGENTIC.md',
                     'PROJECT_INSTRUCTIONS_WEB.md', 'SKILL.md', 'SECTION_11.md',
                     'DOSSIER_TEMPLATE.md'):
            with self.subTest(name=name):
                text = ' '.join((ROOT / name).read_text().split()).lower()
                for phrase in ('data-folder root', 'repository root on github',
                               'delivery copies', 'once', 'ask', 'move it',
                               'until', 'point to', 'private', 'git keeps old versions'):
                    self.assertIn(phrase, text)
                self.assertTrue('never move or copy it yourself' in text or 'never moves or copies it itself' in text)
                self.assertNotIn('not necessarily the data directory', text)
                self.assertNotIn('not applicable — uploaded manually', text)
                self.assertNotIn('**official dossier location:**', text)
        template = (ROOT / 'DOSSIER_TEMPLATE.md').read_text()
        self.assertIn('**Data directory:**', template)
        self.assertIn('**Dossier revision:**', template)
        self.assertIn('**Last reviewed:**', template)
        self.assertIn('**Obtain the athlete\'s exact approval.**', template)

    def test_powershell_routes_and_external_venv_prerequisites(self):
        for name in ('json-local-sync', 'json-manual'):
            with self.subTest(name=name):
                text = (ROOT / 'examples' / name / 'SETUP.md').read_text()
                technical = text.split('# Technical guide\n', 1)[1]
                route = technical.split('```powershell\n', 1)[1].split('```', 1)[0]
                commands = ('New-Item', 'Set-Location -LiteralPath', ' --init', ' --setup',
                            'Get-ChildItem -LiteralPath . -Force -ErrorAction Stop',
                            'Copy-Item -LiteralPath', ' --output ')
                indices = [route.index(command) for command in commands]
                self.assertEqual(indices, sorted(indices))
                self.assertIn('C:\\Users\\René Martin\\Training data', route)
                self.assertIn('py -3 "', route)
                self.assertIn('Where-Object Name -eq "DOSSIER.md"', route)
                for phrase in ('externally-managed-environment', 'Homebrew', 'Debian/Ubuntu',
                               'outside the data folder', 'cloud-synced', '-m venv',
                               'LOCALAPPDATA', 'standard timer uses it', '/usr/bin/python3', '3.9'):
                    self.assertIn(phrase, text)
        assistant = (ROOT / 'SETUP_ASSISTANT.md').read_text().split('**Local setup:**', 1)[1]
        self.assertLess(assistant.index('python3 --version'), assistant.index('1. Choose'))
        self.assertLess(assistant.index('import requests'), assistant.index('1. Choose'))


if __name__ == '__main__':
    unittest.main()
