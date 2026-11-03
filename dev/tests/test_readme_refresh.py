"""Release-matched hosted README lifecycle and the compact human helper page."""
import contextlib
import io
import json
import re
import unittest
from test_update_prototype import ROOT, Offline, manifest
from test_b2_hosted import H, Remote, DirectPublisher, release
import validate_data


def target(date, label=None):
    _, files, identity = release(date)
    files = dict(files)
    if label is None:
        del files[H.README_TEMPLATE]
    else:
        files[H.README_TEMPLATE] += ('\nRelease ' + label + ' helper\n').encode()
    return manifest(files), files, identity


def plans(output, prefix):
    return [json.loads(line[len(prefix):]) for line in output.splitlines() if line.startswith(prefix)]


class ReadmeLifecycle(Offline):
    def test_install_update_and_rollback_use_matching_template_and_current_timestamp(self):
        old = b'old notes\n**Last successful sync:** first UTC\n'
        kept = {'latest.json': b'old data', 'DOSSIER.md': b'dossier', 'custom/notes.md': b'notes'}
        remote = Remote(dict(kept, **{'README.md': old}))
        pub = DirectPublisher(remote)
        a, b = target('2026.10.30', 'A'), target('2026.10.31', 'B')
        first = H.HostedUpdater(pub, lambda: a, {})
        second = H.HostedUpdater(pub, lambda: b, {})
        rendered = lambda item, stamp: H.render_readme(None, item[1][H.README_TEMPLATE],
                                                      stamp, remote.repo, pub.default)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            before = pub.snapshot()
            first.install(before, accepted=True)
            self.assertEqual(remote.inventory()['README.md'], rendered(a, 'first UTC'))
            self.assertEqual(pub.read(before, 'README.md'), old)
            self.assertNotIn('README.md', H.installation_paths(pub.snapshot()))
            self.assertNotIn('README.md', a[1])
            edited = rendered(a, 'second UTC') + b'\nEdited after installation\n'
            remote.tip = remote.commit({'README.md': edited}, [remote.tip], 'README edit')
            self.assertIn('README.md', second.status(pub.snapshot())['plan']['changed'])
            second.install(pub.snapshot(), accepted=True)
            self.assertEqual(remote.inventory()['README.md'], rendered(b, 'second UTC'))
            current = rendered(b, 'latest UTC') + b'\nEdited after update\n'
            remote.tip = remote.commit({'README.md': current, 'latest.json': b'new data'},
                                       [remote.tip], 'Later sync and edit')
            before_rollback = pub.snapshot()
            second.rollback(before_rollback)
        self.assertEqual(remote.inventory()['README.md'], rendered(a, 'latest UTC'))
        self.assertEqual(pub.read(before_rollback, 'README.md'), current)
        self.assertEqual(remote.inventory()['section11/' + H.README_TEMPLATE], a[1][H.README_TEMPLATE])
        for name, value in dict(kept, **{'latest.json': b'new data'}).items():
            self.assertEqual(remote.inventory()[name], value)
        for plan in plans(output.getvalue(), 'Verified installation plan: ') + plans(
                output.getvalue(), 'Verified rollback plan: '):
            self.assertIn('README.md', plan['changed'])
        self.assertEqual(len(plans(output.getvalue(), 'Verified rollback plan: ')), 1)

    def test_missing_template_at_install_and_rollback_preserves_current_readme(self):
        for existing in (None, b'custom bytes\xff\n**Last successful sync:** old UTC\n'):
            with self.subTest(existing=existing is not None):
                remote = Remote({'README.md': existing} if existing is not None else {})
                pub = DirectPublisher(remote)
                missing, present = target('2026.10.30'), target('2026.10.31', 'B')
                first = H.HostedUpdater(pub, lambda: missing, {})
                second = H.HostedUpdater(pub, lambda: present, {})
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    first.install(pub.snapshot(), accepted=True)
                self.assertEqual(remote.inventory().get('README.md'), existing)
                self.assertIn(H.README_UNCHANGED, output.getvalue())
                plan = plans(output.getvalue(), 'Verified installation plan: ')[0]
                self.assertNotIn('README.md', sum(plan.values(), []))
                with contextlib.redirect_stdout(io.StringIO()):
                    second.install(pub.snapshot(), accepted=True)
                current = remote.inventory()['README.md'] + b'\nCurrent note\n'
                remote.tip = remote.commit({'README.md': current}, [remote.tip], 'Later note')
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    second.rollback(pub.snapshot())
                self.assertEqual(remote.inventory()['README.md'], current)
                self.assertNotIn('section11/' + H.README_TEMPLATE, remote.inventory())
                self.assertIn(H.README_UNCHANGED, output.getvalue())
                self.assertNotIn('README.md', sum(plans(output.getvalue(), 'Verified rollback plan: ')[0].values(), []))

    def test_missing_update_template_keeps_edited_readme_and_reports_it(self):
        remote = Remote()
        pub = DirectPublisher(remote)
        with contextlib.redirect_stdout(io.StringIO()):
            H.HostedUpdater(pub, lambda: target('2026.10.30', 'A'), {}).install(pub.snapshot(), accepted=True)
        current = b'Keep these exact bytes\r\n**Last successful sync:** current UTC\r\n'
        remote.tip = remote.commit({'README.md': current}, [remote.tip], 'Owner edit')
        with contextlib.redirect_stdout(io.StringIO()) as output:
            H.HostedUpdater(pub, lambda: target('2026.10.31'), {}).install(pub.snapshot(), accepted=True)
        self.assertEqual(remote.inventory()['README.md'], current)
        self.assertIn(H.README_UNCHANGED, output.getvalue())
        self.assertNotIn('section11/' + H.README_TEMPLATE, remote.inventory())

    def test_renderer_keeps_placeholder_comment_branch_and_timestamp_contract(self):
        template = (b'<!-- template notes -->\r\n# YOUR_GITHUB_USER/YOUR_REPO_NAME\r\n'
                    b'[data](https://github.com/[your-username]/[repo-name]/blob/main/latest.json)\r\n'
                    b'![Sync Status](https://github.com/YOUR_GITHUB_USER/YOUR_REPO_NAME/actions/workflows/auto-sync.yml/badge.svg)\r\n'
                    b'**Last successful sync:** old\r\n')
        result = H.render_readme(None, template, r'current \1 UTC', 'person/training', 'stable')
        self.assertTrue(result.startswith(b'# person/training\n'))
        self.assertIn(b'/person/training/blob/stable/latest.json', result)
        self.assertIn(b'/person/training/actions/workflows/auto-sync.yml/badge.svg', result)
        self.assertIn(b'**Last successful sync:** current \\1 UTC\n', result)
        for value in (b'YOUR_', b'<!--', b'\r', b'/main/'):
            self.assertNotIn(value, result)
        with_note = result + b'\nOwner text between updates\n'
        self.assertEqual(H.render_readme(with_note, None, 'new UTC', 'person/training', 'stable'),
                         with_note.replace(b'current \\1 UTC', b'new UTC'))


DOSSIER_ITEM = (
    '- `DOSSIER.md`: your private athlete dossier, if you use one, kept here in the root. '
    'It can contain sensitive personal and health details, so keep this repository private; '
    'Git keeps old versions, so deleting it later does not erase it.')
PUBLIC_WARNING = (
    'Raw links work only if this repository is public; then everything here is public, '
    'so never make a repository with your dossier public.')
DOSSIER_PROMPT = (
    '> section11/SECTION_11.md and the report templates in section11/examples/reports/ '
    'and DOSSIER.md if present.')


def template_errors(text):
    errors = [name for name in (*validate_data.FALLBACK, 'maps/weather/', 'archive/')
              if '`' + name + '`' not in text]
    if re.search(r'https://(?:raw\.githubusercontent\.com/CrankAddict/section-11/main/|'
                 r'github\.com/CrankAddict/section-11/(?:blob|tree)/main/)', text, re.I):
        errors.append('official main link')
    if 'CC BY-NC' in text.upper():
        errors.append('old license')
    contents = text.partition('## What is here\n')[2].partition('\n## ')[0]
    if DOSSIER_ITEM not in contents:
        errors.append('dossier item and privacy')
    if PUBLIC_WARNING not in text:
        errors.append('public dossier warning')
    if DOSSIER_PROMPT not in text:
        errors.append('dossier prompt')
    if 'recorded private location' in text:
        errors.append('old dossier location')
    return errors


class ReadmePage(unittest.TestCase):
    def test_helper_page_lists_all_hosted_outputs_and_scopes_its_license(self):
        text = (ROOT / H.README_TEMPLATE).read_text()
        self.assertEqual(template_errors(text), [])
        self.assertLess(len(text.split()), 400)
        for phrase in ('YOUR_GITHUB_USER', 'YOUR_REPO_NAME', 'badge.svg)', '**Last successful sync:**',
                       '## Sync Now', '## Use with your AI', 'SECTION_11.md', 'examples/reports/',
                       'Workout Reference Library', '`custom/`',
                       'connector or link', 'Code > Download ZIP', 'chat or project',
                       'snapshot: re-upload for fresh data and after updates',
                       'everything here is public', '**Update**', '**Status**', '**Rollback**',
                       'SECTION11_AUTO_UPDATE=true', 'section11/examples/maintenance/UPDATING.md',
                       'The Section 11 files in `section11/` are [MIT licensed](section11/LICENSE)'):
            self.assertIn(phrase, text)
        for obsolete in ('interval_data.', 'data_overview', 'requests on a quiet',
                         'Actions cache', 'every 30 minutes', 'AI tools must'):
            self.assertNotIn(obsolete, text)
        self.assertTrue((ROOT / 'LICENSE').read_text().startswith('MIT License'))

    def test_output_omissions_and_official_main_or_old_license_are_violations(self):
        text = (ROOT / H.README_TEMPLATE).read_text()
        for name in (*validate_data.FALLBACK, 'maps/weather/', 'archive/'):
            with self.subTest(name=name):
                self.assertIn(name, template_errors(text.replace('`' + name + '`', '`missing`')))
        for extra in ('\nCC BY-NC 4.0', '\nhttps://github.com/CrankAddict/section-11/blob/main/SKILL.md',
                      '\nhttps://raw.githubusercontent.com/CrankAddict/section-11/main/SECTION_11.md'):
            self.assertTrue(template_errors(text + extra))
        self.assertEqual(template_errors(text + '\nhttps://raw.githubusercontent.com/person/training/main/latest.json'), [])

    def test_dossier_placement_privacy_and_prompt_violations(self):
        text = (ROOT / H.README_TEMPLATE).read_text()
        for phrase in ('`DOSSIER.md`', 'if you use one', 'kept here in the root',
                       'sensitive personal and health details', 'keep this repository private',
                       'Git keeps old versions', 'deleting it later does not erase it'):
            with self.subTest(phrase=phrase):
                self.assertIn('dossier item and privacy', template_errors(text.replace(phrase, 'omitted')))
        misplaced = text.replace(DOSSIER_ITEM, '') + '\n' + DOSSIER_ITEM
        self.assertIn('dossier item and privacy', template_errors(misplaced))
        for phrase, error in (
                ('so never make a repository with your dossier public', 'public dossier warning'),
                ('and DOSSIER.md if present', 'dossier prompt')):
            with self.subTest(phrase=phrase):
                self.assertIn(error, template_errors(text.replace(phrase, 'omitted')))
        self.assertIn('old dossier location', template_errors(
            text + '\nYour dossier stays at its recorded private location.'))
        self.assertEqual(template_errors(text.replace('\nSee the installed', '\n\nSee the installed')), [])
