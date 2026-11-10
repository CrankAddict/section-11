"""Regressions for the first B3 live rehearsal; all scheduler calls are mocked."""
import csv
import io
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from test_update_prototype import SYNC, ROOT, REAL_TIMERS, Offline, inventory, write




class RehearsalWorkflowTests(Offline):
    def test_push_before_install_stops_once_and_installed_neighbor_passes(self):
        text = (ROOT / 'examples/agentic/push-workout.yml').read_text()
        marker = '      - name: Require installed Section 11\n        run: |\n'
        guard = text.split(marker, 1)[1].split('      - name:', 1)[0]
        guard = '\n'.join(line[10:] for line in guard.splitlines())
        self.assertLess(text.index(marker), text.index('      - name: Setup Python'))
        self.assertLess(text.index(marker), text.index('      - name: Run managed push'))
        before = inventory(self.root)
        missing = subprocess.run(['/bin/sh', '-c', guard], cwd=self.root, capture_output=True, text=True, check=False)
        self.assertEqual(missing.returncode, 1)
        self.assertEqual(missing.stdout, 'Section 11 is not installed yet; run Sync once first\n')
        self.assertEqual(missing.stderr, '')
        self.assertEqual(inventory(self.root), before)
        write(self.root, {'section11/examples/agentic/push.py': b'raise AssertionError("guard must not execute push")\n'})
        installed = subprocess.run(['/bin/sh', '-c', guard], cwd=self.root, capture_output=True, text=True, check=False)
        self.assertEqual((installed.returncode, installed.stdout, installed.stderr), (0, '', ''))
        self.assertIn('run: python section11/examples/agentic/push.py --workflow', text)

    def test_guides_commit_both_stubs_before_sync_and_hosted_gate_order_is_explicit(self):
        for kind in ('json-auto-sync', 'json-on-demand'):
            guide = (ROOT / 'examples' / kind / 'SETUP.md').read_text()
            prose = ' '.join(guide.split())
            self.assertIn('same owner commit, before the first Sync', prose)
            self.assertNotIn('After the first successful **Sync**', guide)
            workflow = (ROOT / 'examples' / kind / 'auto-sync.yml').read_text()
            names = ['Require default branch', 'Checkout default branch', 'Setup Python',
                     'Select and fetch official runtime', 'Write fixed verification gate',
                     'Verify runtime dependencies', 'Install dependencies', 'Prepare operation']
            positions = [workflow.index('- name: ' + name) for name in names]
            self.assertEqual(positions, sorted(positions))
