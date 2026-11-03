"""Common accepted hosted installation, daily policy and history rollback."""
import json
import os
import re
from datetime import datetime, timezone

from direct_commit import sha, checked_tree, blob_sha
from distribution import Distribution as D

CONTROL = '.section11-update.json'
ROOT_TOOLS = ('sync.py', 'push.py', 'pull.py')
README_TEMPLATE = 'examples/json-auto-sync/DATA_REPO_README_TEMPLATE.md'
README_UNCHANGED = 'Target release has no standard README template; README.md left unchanged.'
NOTICE = 'A verified Section 11 update is available. Run Update in the sync workflow to install it.'
MARKER = 'Section 11 installation v1\n'
RECOVERY = ('The previous installation needs its earlier workflow. No rollback was published. '
            'Restore the earlier auto-sync.yml and, if used, push-workout.yml from repository history '
            'together with their matching section11/ and root sync.py, push.py and pull.py files. '
            'Preserve newer data, custom files, settings and dossier. The Actions token cannot restore workflows.')


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def policy(env=None):
    env = os.environ if env is None else env
    value = env.get('SECTION11_AUTO_UPDATE', '')
    if value is None or value == '':
        return False
    if value.lower() not in ('true', 'false'):
        raise ValueError('invalid automatic update setting; maintenance stopped')
    return value.lower() == 'true'


def control(raw):
    if raw is None:
        return {'schema': 1, 'attempted_day': None, 'installed_date': None,
                'available_date': None, 'available_tree': None, 'skip_release': None}
    if len(raw) > 8192:
        raise ValueError('oversized update control record')
    value = D.json(raw)
    required = {'schema', 'attempted_day', 'installed_date', 'available_date', 'available_tree', 'skip_release'}
    if (not isinstance(value, dict) or set(value) - {'history_path'} != required
            or type(value['schema']) is not int or value['schema'] != 1):
        raise ValueError('invalid update control schema; preserve it for owner review')
    for key in ('attempted_day', 'installed_date', 'available_date', 'skip_release'):
        if value[key] is not None:
            D.release_date(value[key])
    if value['available_tree'] is not None and not re.fullmatch('[0-9a-f]{64}', str(value['available_tree'])):
        raise ValueError('invalid available-plan preimage')
    if 'history_path' in value:
        name = value['history_path']
        D.path(name)
        if name.split('/')[0] in D.KEEP_ROOT:
            raise ValueError('invalid installation history path')
    return value


def suppression(state, env=None):
    return {state['skip_release']} if state['skip_release'] is not None else set()


def receipt(raw):
    if raw is None:
        return None
    if len(raw) > 4096:
        return None
    try:
        value = D.json(raw)
        if (set(value) != {'schema', 'repository', 'tag', 'commit', 'manifest_sha256'}
                or type(value['schema']) is not int or value['schema'] != 1
                or value['repository'] != D.UPSTREAM
                or not re.fullmatch('[0-9a-f]{40}', value['commit'])
                or not re.fullmatch('[0-9a-f]{64}', value['manifest_sha256'])):
            return None
        D.release_date(value['tag'])
        return value
    except (ValueError, TypeError, KeyError):
        return None


def cleanup_paths(snapshot, release_paths=()):
    entries = snapshot['entries']
    protected_envs = D.python_roots(entries)
    selected = {p: e for p, e in entries.items()
                if D.cleanup_reason(p, release_paths, hosted=True, python_roots=protected_envs,
                                    opaque=e['mode'] in ('120000', '160000'))}
    if any(e['mode'] not in ('100644', '100755') or e.get('type', 'blob') != 'blob'
           for e in selected.values()):
        raise ValueError('non-ordinary cleanup path; preserve installation')
    return selected


def installation_paths(snapshot, release_paths=()):
    cleanup = cleanup_paths(snapshot, release_paths)
    return {p: e for p, e in snapshot['entries'].items()
            if p.startswith('section11/') or p in cleanup}


def workflow_notice(snapshot):
    # .github/ is always owner-controlled. Report exact retained workflow names.
    known = {'auto-sync.yml', 'push-workout.yml', 'section11-update.yml',
             'section11-validate.yml', 'section11-promote.yml'}
    paths = sorted(p for p in snapshot['entries'] if p.startswith('.github/workflows/')
                   and (p.rsplit('/', 1)[-1] in known or p.rsplit('/', 1)[-1].startswith('section11-')))
    if paths:
        print('Owner-managed Section 11 workflows retained: ' + ', '.join(paths) +
              '. The Actions token cannot remove or update workflows; keep compatible stubs, replace old stubs or remove obsolete Section 11 workflows in GitHub.')


def installation_digest(snapshot):
    # A pending plan can also restore missing custom guidance. Bind that
    # create-only preimage so a completed repair cannot leave a stale notice.
    entries = dict(installation_paths(snapshot))
    entries['custom/README.md'] = snapshot['entries'].get('custom/README.md')
    return D.digest(encoded(entries))


def notice_matches(snapshot, state):
    return (state['available_date'] is not None and
            state['available_date'] not in suppression(state) and
            state['available_tree'] == installation_digest(snapshot))


def safety(snapshot, release_paths=()):
    entries = snapshot['entries']
    managed = installation_paths(snapshot, release_paths)
    for path in ('section11', 'custom', *ROOT_TOOLS, CONTROL, 'README.md'):
        entry = entries.get(path)
        if entry and (path in ('section11', 'custom') or entry['mode'] != '100644' or entry['type'] != 'blob'):
            raise ValueError('unsafe installation path/type collision')
        if path in ROOT_TOOLS or path in (CONTROL, 'README.md'):
            if any(p.startswith(path + '/') for p in entries):
                raise ValueError('installation file/directory collision')
    for path, entry in entries.items():
        if path in managed or path == 'custom/README.md':
            if entry['mode'] not in ('100644', '100755') or entry['type'] != 'blob':
                raise ValueError('non-ordinary managed/custom path')
    if any(p.startswith('custom/README.md/') for p in entries):
        raise ValueError('custom README type collision')


def target_changes(snapshot, release, state):
    raw, files, identity = release
    D.verify(raw, files)
    if not {'examples/sync.py', 'examples/maintenance/CUSTOM_README.md'} <= set(files):
        raise ValueError('release lacks required installer entries')
    safety(snapshot)
    changes = {p: None for p in set(installation_paths(snapshot)) | set(cleanup_paths(snapshot, files))}
    for path in cleanup_paths(snapshot, files):
        if snapshot['entries'][path]['mode'] not in ('100644', '100755') or snapshot['entries'][path]['type'] != 'blob':
            raise ValueError('non-ordinary cleanup path')
    changes.update({'section11/' + p: b for p, b in files.items()})
    changes['section11/manifest.json'] = raw
    changes['section11/' + D.RECEIPT] = D.receipt(raw, identity)
    if 'custom/README.md' not in snapshot['entries']:
        changes['custom/README.md'] = files['examples/maintenance/CUSTOM_README.md']
    changes[CONTROL] = encoded(control(encoded(state)))
    return changes


def installed_identity(publisher, snapshot):
    return receipt(publisher.read(snapshot, 'section11/' + D.RECEIPT, 4096))


def chronology(installed, target):
    if installed:
        if D.release_date(installed['tag']) > D.release_date(target['tag']):
            raise ValueError('known date downgrade refused')
        if installed['tag'] == target['tag'] and installed['commit'] != target['commit']:
            raise ValueError('same-date changed release refused')


def content_ahead(publisher, snapshot, files):
    old = {name: publisher.read(snapshot, 'section11/' + name)
           for name in ('SECTION_11.md', 'examples/sync.py')}
    if any(value is None for value in old.values()):
        return False
    try:
        return any(tuple(map(int, a.split('.'))) > tuple(map(int, b.split('.')))
                   for a, b in zip(D.identity(old), D.identity(files)))
    except (ValueError, KeyError):
        return False


def changed_paths(snapshot, changes):
    added, changed, removed = [], [], []
    for name, data in sorted(changes.items()):
        old = snapshot['entries'].get(name)
        if data is None and old is not None:
            removed.append(name)
        elif data is not None and old is None:
            added.append(name)
        elif data is not None and (old['sha'] != blob_sha(data) or old['mode'] != '100644'):
            changed.append(name)
    return {'added': added, 'changed': changed, 'removed': removed}


def exact_validator(expected):
    def validate(before, changes):
        if changes != expected:
            raise ValueError('publication differs from exact validated scope/bytes')
    return validate


def render_readme(existing, template, timestamp, repository, default):
    """Use the same standard README rendering for installation and first Sync."""
    if existing is None:
        text = template.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
        owner, repo = repository.split('/')
        text = text.replace('[your-username]', owner).replace('[repo-name]', repo)
        text = text.replace('YOUR_GITHUB_USER', owner).replace('YOUR_REPO_NAME', repo)
        text = re.sub(r'\A<!--.*?-->\s*', '', text, count=1, flags=re.S)
        text = text.replace('/main/', '/' + default + '/')
    else:
        text = existing.decode('utf-8')
    line = '**Last successful sync:** ' + timestamp
    if 'Last successful sync:' in text:
        text = re.sub(r'\*\*Last successful sync:\*\*.*', lambda _: line, text)
    elif existing is None:
        text += '\n' + line + '\n'
    else:
        text = re.sub(r'(?m)^(.*badge\.svg\).*)$', lambda m: m[1] + '\n\n' + line + '\n', text)
    return text.encode()


class HostedUpdater:
    def __init__(self, publisher, fetch_release, env=None):
        self.publisher = publisher
        self.fetch_release = fetch_release
        self.env = os.environ if env is None else env
        self._release = None

    def latest(self):
        if self._release is None:
            self._release = self.fetch_release()
            raw, files, identity = self._release
            D.verify(raw, files)
            if identity.get('repository', D.UPSTREAM) != D.UPSTREAM:
                raise ValueError('foreign release target')
            D.receipt(raw, identity)
        return self._release

    def state(self, snapshot):
        return control(self.publisher.read(snapshot, CONTROL, 8192))

    def readme_changes(self, before, template):
        if template is None:
            print(README_UNCHANGED)
            return {}
        previous = self.publisher.read(before, 'README.md')
        stamp = re.search(rb'(?m)^\*\*Last successful sync:\*\* ([^\r\n]*)', previous or b'')
        # Installing code is not a successful data sync. Retain the prior stamp
        # when available; otherwise keep the template's neutral placeholder.
        timestamp = stamp[1].decode('utf-8', errors='replace') if stamp else '_updated automatically_'
        return {'README.md': render_readme(None, template, timestamp,
                                          self.publisher.api.repo, self.publisher.default)}

    def installation_changes(self, before, release, state):
        changes = target_changes(before, release, state)
        changes.update(self.readme_changes(before, release[1].get(README_TEMPLATE)))
        return changes

    def publish_control(self, before, state, message):
        safety(before)
        expected = {CONTROL: encoded(control(encoded(state)))}
        return self.publisher.publish(before, expected, message, exact_validator(expected))

    def claim(self, before, day):
        D.release_date(day)
        state = self.state(before)
        if state['attempted_day'] is not None and state['attempted_day'] >= day:
            return None
        state['attempted_day'] = day
        if not notice_matches(before, state):
            state['available_date'] = None
            state['available_tree'] = None
        return self.publish_control(before, state, 'Section 11 maintenance attempt ' + day)

    def status(self, before):
        workflow_notice(before)
        state = self.state(before)
        release = self.latest()
        if state['installed_date'] and state['installed_date'] > release[2]['tag']:
            raise ValueError('known date downgrade refused')
        identity = installed_identity(self.publisher, before)
        chronology(identity, release[2])
        changes = self.installation_changes(before, release, state)
        plan = changed_paths(before, changes)
        return {'installed': identity['tag'] if identity else 'unknown',
                'target': release[2]['tag'], 'suppressed': release[2]['tag'] in suppression(state, self.env),
                'content_ahead': content_ahead(self.publisher, before, release[1]), 'plan': plan}

    def install(self, before, accepted=False, automatic=False):
        if not accepted and not automatic:
            raise ValueError('explicit workflow installation acceptance is required')
        if automatic and not policy(self.env):
            raise ValueError('automatic installation is not enabled')
        state = self.state(before)
        release = self.latest()
        identity = installed_identity(self.publisher, before)
        if automatic and identity is None and state['installed_date'] is None:
            raise ValueError('first installation requires explicit workflow acceptance')
        if state['installed_date'] and state['installed_date'] > release[2]['tag']:
            raise ValueError('known date downgrade refused')
        chronology(identity, release[2])
        if automatic and release[2]['tag'] in suppression(state, self.env):
            raise ValueError('rolled-back release remains skipped in automatic mode')
        if accepted and state['skip_release'] == release[2]['tag']:
            state['skip_release'] = None
        ahead = content_ahead(self.publisher, before, release[1])
        if ahead:
            if automatic:
                raise ValueError('higher installed version labels hold automatic replacement')
            print('Higher installed version labels: explicit Update accepts the verified target.')
        state['available_date'] = None
        state['available_tree'] = None
        state['installed_date'] = release[2]['tag']
        cleanup = cleanup_paths(before, release[1])
        # A cleanup-only install can leave section11/ byte-identical. Retain one
        # changed path so bounded history lookup still finds that installation.
        if cleanup:
            name = sorted(cleanup)[0]
            # Legacy directories may contain ordinary hidden files, which are
            # valid cleanup preimages but not release-manifest filenames.
            state['history_path'] = (name.split('/')[0] if name.startswith(
                ('section11-legacy-github', 'section11-legacy-dev')) else name)
        else:
            state.pop('history_path', None)
        expected = self.installation_changes(before, release, state)
        workflow_notice(before)
        print('Verified installation plan:', json.dumps(changed_paths(before, expected), sort_keys=True))
        message = MARKER + json.dumps({'schema': 1, 'tag': release[2]['tag'],
                                      'commit': release[2]['commit'],
                                      'manifest_sha256': D.digest(release[0])}, sort_keys=True)
        return self.publisher.publish(before, expected, message, exact_validator(expected))

    def maintain(self, before, day, success, automatic=True, run_attempt=1):
        """Explicit operations use install/status/rollback; failure consumes claim."""
        claimed = self.claim(before, day)
        if claimed is None:
            return before, None
        full = policy(self.env)
        # No latest-target discovery request precedes a confirmed daily claim.
        # Bootstrap authentication of the installed controller is separate.
        status = self.status(claimed)
        if 'custom/README.md' not in claimed['entries']:
            expected = {'custom/README.md': self.latest()[1]['examples/maintenance/CUSTOM_README.md']}
            claimed = self.publisher.publish(claimed, expected, 'Restore missing Section 11 custom guidance',
                                             exact_validator(expected))
            status = self.status(claimed)
        # README replacement accompanies an installation; a later README edit
        # alone must not turn an ordinary Sync into a new installation.
        need = any(path != 'README.md' for key in ('added', 'changed', 'removed')
                   for path in status['plan'][key])
        if need and not status['suppressed'] and not status['content_ahead']:
            state = self.state(claimed)
            state['available_date'] = status['target']
            state['available_tree'] = installation_digest(claimed)
            claimed = self.publish_control(claimed, state, 'Section 11 available release ' + status['target'])
            # Persist the verified plan before attempting installation. A failed
            # or unknown write cannot erase it or authorize another daily attempt.
            if full:
                return self.install(claimed, automatic=True), status
            print('::notice::' + NOTICE)
        else:
            state = self.state(claimed)
            if state['available_date'] is not None:
                state['available_date'] = None
                state['available_tree'] = None
                claimed = self.publish_control(claimed, state, 'Clear obsolete Section 11 update notice')
        return claimed, status

    def rollback(self, before):
        from urllib.parse import quote
        safety(before)
        state = self.state(before)
        current = installed_identity(self.publisher, before)
        if current is None:
            raise ValueError(RECOVERY)
        # Ask GitHub for the latest change to each installation path. The four
        # bounded queries skip any number of unrelated data/control commits.
        candidates = set()
        for path in dict.fromkeys(('section11', *ROOT_TOOLS, *([state['history_path']] if 'history_path' in state else []))):
            items = self.publisher.api.get('/commits?sha=' + before['commit'] +
                                           '&path=' + quote(path, safe='/') + '&per_page=1')
            if not isinstance(items, list) or len(items) > 1:
                raise ValueError('invalid installation history response')
            if items:
                candidates.add(sha(items[0]['sha']))
        selected = None
        for candidate in sorted(candidates):
            if all(other == candidate or
                   self.publisher.api.get('/compare/' + other + '...' + candidate).get('status') == 'ahead'
                   for other in candidates):
                selected = self.publisher.snapshot(candidate)
                break
        if selected is None or len(selected['parents']) != 1:
            raise ValueError('no recorded compatible installation commit; ' + RECOVERY)
        if not selected['message'].startswith(MARKER):
            raise ValueError('installation changed after update; preserve later code edits')
        installed_manifest = self.publisher.read(selected, 'section11/manifest.json')
        if installed_manifest is None or D.digest(installed_manifest) != current['manifest_sha256']:
            raise ValueError('recorded installation manifest differs from verified release')
        release_paths = D.manifest(installed_manifest)['files']
        if installation_paths(before, release_paths) != installation_paths(selected, release_paths):
            raise ValueError('installation changed after update; preserve later code edits')
        prior = self.publisher.snapshot(selected['parents'][0])
        safety(prior, release_paths)
        prior_identity = installed_identity(self.publisher, prior)
        if prior_identity is None:
            raise ValueError(RECOVERY)
        # Git object readback authenticates the exact previous snapshot, including
        # personal edits. Its release receipt identifies chronology, not those edits.
        record = D.json(selected['message'][len(MARKER):])
        if (record != {'schema': 1, 'tag': current['tag'], 'commit': current['commit'],
                       'manifest_sha256': current['manifest_sha256']}):
            raise ValueError('installation history identity changed')
        allowed = set(installation_paths(selected, release_paths)) | set(installation_paths(prior, release_paths)) | {CONTROL, 'custom/README.md', 'README.md'}
        actual = {p for p in selected['entries'].keys() | prior['entries'].keys()
                  if selected['entries'].get(p) != prior['entries'].get(p)}
        if not actual <= allowed or ('custom/README.md' in actual and 'custom/README.md' in prior['entries']):
            raise ValueError('recorded installation commit contains unrelated changes')
        state['skip_release'] = current['tag']
        state['available_date'] = None
        state['available_tree'] = None
        state['installed_date'] = prior_identity['tag']
        state.pop('history_path', None)
        expected = {p: None for p in installation_paths(before, release_paths)}
        expected.update({p: self.publisher.read(prior, p) for p in installation_paths(prior, release_paths)})
        expected.update(self.readme_changes(before, expected.get('section11/' + README_TEMPLATE)))
        expected[CONTROL] = encoded(state)
        modes = {p: prior['entries'][p]['mode'] for p in installation_paths(prior, release_paths)}
        print('Verified rollback plan:', json.dumps(changed_paths(before, expected), sort_keys=True))
        return self.publisher.publish(before, expected, 'Section 11 rollback; rejected ' + current['tag'],
                                      exact_validator(expected), modes=modes)


def eligible_day(created_at, event, success, run_attempt=1, scheduled=True):
    if event not in ('schedule', 'workflow_dispatch'):
        return None
    instant = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
    if instant.tzinfo is None:
        raise ValueError('run creation time lacks a timezone')
    instant = instant.astimezone(timezone.utc)
    if instant.hour < 4 or (event == 'schedule' and not scheduled):
        return None
    return instant.strftime('%Y.%m.%d')
