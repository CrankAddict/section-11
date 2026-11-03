"""Stable hosted adapter: bootstrap, data publication, cache and maintenance."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone

import requests
from direct_commit import DirectPublisher, blob_sha
from distribution import Distribution as D, UnknownOutcome, _sync
from github_api import GitHub, APIError
import hosted_update as update
import validate_data

WRAPPER_API = 2

class HostedGitHub(GitHub):
    """Separate bounded data/control transport; never used for upstream reads."""
    def __init__(self, repo, token=None):
        super().__init__(repo, token)
        self.count = 0
        self.deadline = time.monotonic() + 300

    def request(self, method, path, **kwargs):
        if path != self.prefix and not path.startswith(self.prefix + '/'):
            raise ValueError('cross-repository API path')
        remaining = self.deadline - time.monotonic()
        if self.count >= 1200 or remaining <= 0:
            raise ValueError('data/control request admission bound reached')
        self.count += 1
        headers = {'Accept': 'application/vnd.github+json', 'Authorization': 'Bearer ' + self.token}
        response = requests.request(method, D.API + path, headers=headers,
                                    timeout=min(10, max(0.1, remaining)), allow_redirects=False, **kwargs)
        if not 200 <= response.status_code < 300:
            raise APIError(response.status_code, 'GitHub data/control request refused; no automatic retry')
        if len(response.content) > 64 * 1024 * 1024:
            raise ValueError('GitHub response exceeds size bound')
        return response.json() if response.content else None

    def metadata(self):
        return self.request('GET', self.prefix)

    def tree(self, identity):
        result = self.get('/git/trees/' + identity + '?recursive=1')
        if result.get('truncated') or not isinstance(result.get('tree'), list) or len(result['tree']) > 10000:
            raise ValueError('incomplete or oversized repository inventory')
        names = [item['path'] for item in result['tree']]
        if len(names) != len(set(names)):
            raise ValueError('duplicate Git tree entry')
        managed_size = sum(item.get('size', 0) for item in result['tree'] if item['path'].startswith('section11/'))
        if managed_size > 256 * 1024 * 1024:
            raise ValueError('old managed tree exceeds 256 MiB')
        return {item['path']: item for item in result['tree'] if item['type'] != 'tree'}


def temp_path(name):
    root = Path(os.environ['RUNNER_TEMP'])
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('unsafe runner staging')
    path = root / name
    if path.is_symlink():
        raise ValueError('symlink runner staging')
    return path


def output(**values):
    with open(os.environ['GITHUB_OUTPUT'], 'a') as handle:
        for key, value in values.items():
            value = str(value)
            if not re.fullmatch('[a-z_]+', key) or any(c in value for c in '\r\n'):
                raise ValueError('invalid action output')
            handle.write(key + '=' + value + '\n')


def context(value=None):
    path = temp_path('section11-hosted-context.json')
    if value is None:
        return D.json(path.read_bytes())
    path.write_bytes(update.encoded(value))


def publisher():
    return DirectPublisher(HostedGitHub(os.environ['GITHUB_REPOSITORY']),
                           os.environ['SECTION11_DEFAULT_BRANCH'])


def trigger(api, event, env):
    default = env['SECTION11_DEFAULT_BRANCH']
    if env.get('GITHUB_REF') != 'refs/heads/' + default:
        raise ValueError('run the workflow on the default branch')
    name = env['GITHUB_EVENT_NAME']
    if name not in ('schedule', 'workflow_dispatch'):
        raise ValueError('unsupported hosted event')
    run_id = env['GITHUB_RUN_ID']
    if not re.fullmatch('[1-9][0-9]*', run_id):
        raise ValueError('invalid run identity')
    run = api.get('/actions/runs/' + run_id)
    if (str(run.get('id')) != run_id or run.get('event') != name
            or run.get('head_branch') != default
            or run.get('head_repository', {}).get('full_name') != env['GITHUB_REPOSITORY']
            or run.get('run_attempt') != int(env['GITHUB_RUN_ATTEMPT'])):
        raise ValueError('run identity differs from the default-branch invocation')
    update.eligible_day(run['created_at'], name, True, scheduled=True)
    operation = event.get('inputs', {}).get('operation', 'Sync') or 'Sync'
    if operation not in ('Sync', 'Update', 'Status', 'Rollback'):
        raise ValueError('unknown workflow operation')
    return {'event': name, 'created_at': run['created_at'], 'attempt': run['run_attempt'],
            'operation': operation, 'cron': event.get('schedule', '')}


def data_crons(workflow):
    """Read the owner-preserved literal schedule block."""
    result = []
    for line in workflow.decode('utf-8').splitlines():
        match = re.fullmatch(r'\s*- cron:\s*([\x27\"])([^\x27\"]+)\1\s*(?:#.*)?', line)
        if match:
            result.append(match[2])
    return result

def check_checkout(pub, snapshot, root):
    """Bind producer/cache inputs and installation paths to the observed default."""
    update.safety(snapshot)
    names = set(update.installation_paths(snapshot)) | set(validate_data.FALLBACK) | {
        '.github/workflows/auto-sync.yml', 'custom/README.md', 'README.md', update.CONTROL}
    custom = root / 'custom'
    if custom.is_symlink() or (custom.exists() and not custom.is_dir()):
        raise ValueError('unsafe custom checkout')
    managed = root / 'section11'
    if managed.exists():
        _sync._ordinary_tree_digest(managed)
        names.update('section11/' + p.relative_to(managed).as_posix()
                     for p in managed.rglob('*') if p.is_file())
    names.update(update.ROOT_TOOLS)
    for name in names:
        path = root
        for part in name.split('/'):
            path /= part
            if path.is_symlink():
                raise ValueError('unsafe checkout preimage')
        entry = snapshot['entries'].get(name)
        if entry is None:
            if path.exists():
                raise ValueError('checkout differs from observed default preimage')
        elif (not path.is_file() or entry['type'] != 'blob' or
              entry['mode'] not in ('100644', '100755') or blob_sha(path.read_bytes()) != entry['sha']):
            raise ValueError('checkout differs from observed default preimage')


def materialize_install(root, source, state_bytes, readme_bytes):
    """Runner-only checkout after confirmed installation; never its publisher."""
    stage = temp_path('section11-new-checkout')
    raw, files = D.tree(source)
    stage.mkdir(mode=0o700, exist_ok=False)
    for name, data in dict(files, **{'manifest.json': raw, D.RECEIPT: (source / D.RECEIPT).read_bytes()}).items():
        path = stage / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    target = root / 'section11'
    if target.exists():
        target.rename(temp_path('section11-old-checkout'))
    stage.rename(target)
    for name in _sync._cleanup_paths(root, files, hosted=True):
        path = root / name
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    custom = root / 'custom'
    if custom.is_symlink() or (custom.exists() and not custom.is_dir()):
        raise ValueError('unsafe custom checkout')
    custom.mkdir(exist_ok=True)
    guide = custom / 'README.md'
    if not guide.exists():
        guide.write_bytes(files['examples/maintenance/CUSTOM_README.md'])
    if readme_bytes is not None:
        D.ordinary(root, 'README.md').write_bytes(readme_bytes)
    (root / update.CONTROL).write_bytes(state_bytes)


def prepare(source, source_release, verifier):
    parser = argparse.ArgumentParser()
    parser.add_argument('--wrapper-api', type=int, required=True)
    parser.add_argument('--accept-install', action='store_true')
    args = parser.parse_args()
    if args.wrapper_api != WRAPPER_API or not args.accept_install:
        raise ValueError('owner wrapper update required; explicit installation acceptance missing')
    pub = publisher()
    event = D.json(Path(os.environ['GITHUB_EVENT_PATH']).read_bytes())
    info = trigger(pub.api, event, os.environ)
    before = pub.snapshot()
    root = Path(os.environ['GITHUB_WORKSPACE'])
    check_checkout(pub, before, root)
    source_raw, source_files, source_identity = source_release
    identity = update.installed_identity(pub, before)
    controller = update.HostedUpdater(pub, lambda: verifier.Distribution.fetch(), os.environ)
    initial_state = controller.state(before)
    operation = info['operation']
    if operation == 'Status':
        print(json.dumps(controller.status(before), sort_keys=True))
        output(run_sync='false', maintenance='false')
        return
    if operation == 'Rollback':
        controller.rollback(before)
        output(run_sync='false', maintenance='false')
        return
    if operation == 'Update':
        controller.install(before, accepted=True)
        output(run_sync='false', maintenance='false')
        return
    first_install = identity is None and initial_state['installed_date'] is None
    if first_install:
        if shutil.disk_usage(root).free < sum(len(data) for data in source_files.values()) + 10 * 1024 * 1024:
            raise ValueError('insufficient checkout space before installation')
        controller._release = source_release
        before = controller.install(before, accepted=True)
        materialize_install(root, source, pub.read(before, update.CONTROL, 8192),
                            pub.read(before, 'README.md'))
    elif identity is not None and (identity['commit'] != source_identity['commit'] or identity['manifest_sha256'] != D.digest(source_raw)):
        raise ValueError('checkout and authenticated producer differ; start a fresh run')
    workflow = pub.read(before, '.github/workflows/auto-sync.yml', 128 * 1024)
    if workflow is None:
        raise ValueError('owner sync workflow is missing')
    crons = data_crons(workflow)
    state = controller.state(before)
    available = state['available_date']
    try:
        if not update.notice_matches(before, state):
            available = None
    except ValueError:
        # Bad maintenance preferences must not advertise an unchecked target.
        # Maintenance reports the invalid setting after successful data work.
        available = None
    info.update({'base': before['commit'], 'source': str(source), 'run_sync': True,
                 'scheduled': bool(crons), 'available_date': available,
                 'source_identity': source_identity, 'source_is_latest': first_install})
    context(info)
    output(run_sync='true', maintenance='true')


def cache_prepare():
    info = context()
    stage = temp_path('section11-slow-cache')
    checkout = Path(os.environ['GITHUB_WORKSPACE']).resolve()
    if stage.resolve() == checkout or checkout in stage.resolve().parents:
        raise ValueError('cache staging is inside checkout')
    stage.mkdir(mode=0o700, exist_ok=True)
    for path in stage.iterdir():
        if path.name not in ('cache.json', 'next.json') or path.is_symlink() or not path.is_file():
            raise ValueError('unexpected cache staging entry')
        path.unlink()
    digest = D.digest((Path(info['source']) / 'examples/sync.py').read_bytes())
    prefix = 'section11-slow-v1-' + '-'.join((os.environ['RUNNER_OS'], os.environ['GITHUB_REPOSITORY_ID'], digest)) + '-'
    key = prefix + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
    output(enabled='true', prefix=prefix, key=key)


def run_sync():
    info = context()
    if not info['run_sync']:
        raise ValueError('this is a maintenance-only invocation')
    athlete, key = os.environ.get('ATHLETE_ID', ''), os.environ.get('INTERVALS_KEY', '')
    if not athlete or not key:
        raise ValueError('ATHLETE_ID and INTERVALS_KEY secrets are required')
    for value in (athlete, key, athlete[:5], key[:5]):
        print('::add-mask::' + value, flush=True)
    days = int(os.environ.get('SECTION11_DAYS', '7'))
    if not 1 <= days <= 365:
        raise ValueError('invalid SECTION11_DAYS')
    env = {k: v for k, v in os.environ.items() if k not in ('GITHUB_TOKEN', 'GH_TOKEN')
           and not k.startswith('GIT_CONFIG')}
    env.update({'SECTION11_SYNC_WRAPPER_API': str(WRAPPER_API),
                'SECTION11_EXPORT_EVENT': info['event'], 'SECTION11_EXPORT_CRON': info['cron']})
    subprocess.run([sys.executable, str(Path(info['source']) / 'examples/sync.py'),
                    '--athlete-id', athlete, '--intervals-key', key, '--days', str(days),
                    '--output', 'latest.json'], cwd=os.environ['GITHUB_WORKSPACE'], env=env, check=True)
    finalize_export()


def finalize_export():
    """Token-free notice hook shared by the ordinary and fictional producers."""
    info = context()
    if not info['run_sync']:
        raise ValueError('this is a maintenance-only invocation')
    # Fixed advisory only, including same-date repairs. Clear stale export text.
    path = Path(os.environ['GITHUB_WORKSPACE']) / 'latest.json'
    latest = D.json(validate_data.read_data(path.parent, path.name))
    latest.pop('update_notice', None)
    if info['available_date']:
        latest['update_notice'] = update.NOTICE
    path.write_bytes(update.encoded(latest))


def readme(existing, source, timestamp, repository, default):
    template = None
    if existing is None:
        path = source / update.README_TEMPLATE
        if not path.exists():
            print(update.README_UNCHANGED)
            return None
        template = path.read_bytes()
    return update.render_readme(existing, template, timestamp, repository, default)


def publish_data():
    info = context()
    if not info['run_sync']:
        raise ValueError('no generated data to publish')
    pub = publisher()
    before = pub.snapshot(info['base'])
    root = Path(os.environ['GITHUB_WORKSPACE'])
    latest = validate_data.read_data(root, 'latest.json')
    previous = pub.read(before, 'latest.json')
    if latest == previous:
        raise ValueError('latest.json was not updated by this sync')
    previous_path = temp_path('section11-previous-latest.json')
    previous_path.write_bytes(previous if previous is not None else b'null')
    stage = temp_path('section11-output')
    validate_data.prepare(root, previous_path, stage)
    plan = D.json((stage / 'plan.json').read_bytes())
    changes = {name: validate_data.read_data(stage / 'files', name) for name in plan['saved']}
    changes.update({name: None for name in plan['removed']})
    now = datetime.now(timezone.utc)
    archive = now.strftime('archive/%Y-%m/%Y-%m-%d.json')
    changes[archive] = latest
    readme_bytes = readme(pub.read(before, 'README.md'), Path(info['source']),
                         now.strftime('%Y-%m-%d %H:%M:%S UTC'), pub.api.repo, pub.default)
    if readme_bytes is not None:
        changes['README.md'] = readme_bytes
    # Validate every generated destination and its remote type before publication.
    for path in changes:
        entry = before['entries'].get(path)
        if entry is not None and (entry['mode'] != '100644' or entry['type'] != 'blob'):
            raise ValueError('non-ordinary data publication preimage')
        for i in range(1, len(path.split('/'))):
            if '/'.join(path.split('/')[:i]) in before['entries']:
                raise ValueError('data publication parent is not a directory')
    expected = dict(changes)
    after = pub.publish(before, changes, 'Sync training data - ' + now.strftime('%Y-%m-%d %H:%M:%S UTC'),
                        update.exact_validator(expected))
    info['base'] = after['commit']
    info['published'] = True
    context(info)
    output(published='true')


def validate_generated():
    # Token-free validation before the publisher step. Publication independently
    # stages and revalidates against the observed prior export before committing.
    validate_data.plan(Path(os.environ['GITHUB_WORKSPACE']))


def cache_promote():
    if not context().get('published'):
        raise ValueError('cache save requires confirmed data publication')
    stage = temp_path('section11-slow-cache')
    source, target = stage / 'next.json', stage / 'cache.json'
    if any(p.is_symlink() for p in (stage, source, target)):
        raise ValueError('symlink cache staging')
    info = source.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 0 < info.st_size <= 8 * 1024 * 1024:
        raise ValueError('invalid cache snapshot')
    os.replace(source, target)
    output(ready='true')


def maintain():
    info = context()
    success = info.get('published', False)
    if info.get('publication_uncertain'):
        raise UnknownOutcome('data publication needs reconciliation; no maintenance attempted')
    pub = publisher()
    before = pub.snapshot(info['base'])
    day = update.eligible_day(info['created_at'], info['event'], success,
                              info['attempt'], info['scheduled'])
    if day is None:
        return
    controller = update.HostedUpdater(pub, _sync._fetch_verified_release, os.environ)
    if info['source_is_latest']:
        raw, files = D.tree(Path(info['source']))
        controller._release = (raw, files, info['source_identity'])
    after, status = controller.maintain(before, day, success, run_attempt=info['attempt'])
    info['base'] = after['commit']
    context(info)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=('cache-prepare', 'sync', 'finalize-export', 'validate', 'publish', 'cache-promote', 'maintain'))
    parser.add_argument('--wrapper-api', type=int, required=True)
    args = parser.parse_args()
    if args.wrapper_api != WRAPPER_API:
        raise ValueError('owner wrapper update required')
    {'cache-prepare': cache_prepare, 'sync': run_sync, 'finalize-export': finalize_export,
     'validate': validate_generated, 'publish': publish_data,
     'cache-promote': cache_promote, 'maintain': maintain}[args.operation]()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, requests.exceptions.RequestException) as exc:
        operation = sys.argv[1] if len(sys.argv) > 1 else ''
        if operation == 'publish' and isinstance(exc, (UnknownOutcome, RuntimeError)):
            info = context()
            info['publication_uncertain'] = True
            context(info)
        if operation == 'maintain':
            print('::warning::Section 11 maintenance failed or is unknown; data outcome is unchanged. '
                  'Inspect this step before further maintenance; no automatic retry.', file=sys.stderr)
        print('::error::' + str(exc).splitlines()[0], file=sys.stderr)
        sys.exit(2 if isinstance(exc, UnknownOutcome) else 1)
