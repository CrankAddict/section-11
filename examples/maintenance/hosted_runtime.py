"""Release-delivered hosted acquisition. Start through dev/hosted_gate.py only."""
import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile

API = 'https://api.github.com'
REPOSITORY = 'CrankAddict/section-11'
PREFIX = '/repos/' + REPOSITORY
RAW = 'https://raw.githubusercontent.com/' + REPOSITORY + '/'
ENTRY = 'examples/maintenance/hosted_runtime.py'
RECEIPT = '.section11-release.json'
MAX_BYTES = 64 * 1024 * 1024
MAX_MANIFEST = 1024 * 1024
MAX_FILES = 512
MAX_ENTRIES = 4096
PAYLOAD = ('examples/sync.py', 'examples/maintenance/hosted.py',
           'examples/maintenance/hosted_update.py', 'examples/maintenance/distribution.py',
           'examples/maintenance/github_api.py', 'examples/maintenance/direct_commit.py',
           'examples/maintenance/validate_data.py', 'examples/maintenance/wrapper-api.json')
PHASES = ('bootstrap', 'prepare', 'cache-prepare', 'sync', 'finalize-export',
          'validate', 'publish', 'cache-promote', 'maintain')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def decode(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('duplicate JSON key')
            value[key] = item
        return value
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('invalid JSON constant')))


def path_key(name):
    return unicodedata.normalize('NFC', name).casefold()


def payload_path(name):
    parts = name.split('/')
    if (not name or len(name) > 240 or name != name.strip() or '\\' in name or ':' in name
            or any(ord(c) < 32 or ord(c) == 127 for c in name)
            or any(not p or p.startswith('.') or p.endswith(('.', ' ')) for p in parts)
            or parts[0] in {'dev', 'custom', 'section11', 'maps', 'archive', 'node_modules'}
            or path_key(name) == 'manifest.json'
            or name in {'manifest.json', 'DOSSIER.md', 'latest.json', 'history.json', 'intervals.json',
                        'routes.json', 'saved_workouts.json', 'ftp_history.json', 'route_eta_history.json'}):
        raise ValueError('unsafe distribution path')


def manifest(raw):
    if len(raw) > MAX_MANIFEST:
        raise ValueError('manifest exceeds runtime bound')
    obj = decode(raw)
    files = obj.get('files') if isinstance(obj, dict) else None
    schema = obj.get('schema_version', 1) if isinstance(obj, dict) else None
    if type(schema) is not int or schema not in (1, 2) or not isinstance(files, dict) or not 0 < len(files) <= MAX_FILES:
        raise ValueError('unsupported manifest schema or inventory')
    aliases = {}
    for name, entry in files.items():
        payload_path(name)
        parts = name.split('/')
        for i in range(1, len(parts) + 1):
            p = '/'.join(parts[:i])
            key = path_key(p)
            if key in aliases and aliases[key] != p:
                raise ValueError('manifest path alias')
            aliases[key] = p
        if not isinstance(entry, dict) or not isinstance(entry.get('hash'), str) or not re.fullmatch('[0-9a-f]{64}', entry['hash']):
            raise ValueError('invalid manifest hash')
    if any('/'.join(p.split('/')[:i]) in files for p in files for i in range(1, len(p.split('/')))):
        raise ValueError('manifest file/directory collision')
    return files


def release_tag(tag):
    if not isinstance(tag, str) or not re.fullmatch(r'[0-9]{4}\.[0-9]{2}\.[0-9]{2}(?:-[1-9][0-9]{0,5})?', tag):
        raise ValueError('invalid release tag')
    day, separator, sequence = tag.partition('-')
    datetime.strptime(day, '%Y.%m.%d')
    if separator and int(sequence) < 2:
        raise ValueError('invalid release sequence')
    return tag


def commit_sha(commit):
    if not isinstance(commit, str) or not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('invalid release commit')
    return commit


def receipt(raw, identity):
    return (json.dumps({'schema': 1, 'repository': REPOSITORY, 'tag': release_tag(identity['tag']),
                        'commit': commit_sha(identity['commit']), 'manifest_sha256': digest(raw)},
                       sort_keys=True) + '\n').encode()


def file_identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


@contextmanager
def directory(path):
    """Hold each ancestor open; reject path replacement before returning."""
    path = Path(os.path.abspath(path))
    handles = [os.open('/', os.O_RDONLY | os.O_DIRECTORY)]
    links = []
    try:
        for name in path.parts[1:]:
            parent = handles[-1]
            before = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISDIR(before.st_mode):
                raise ValueError('unsafe directory')
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            handles.append(fd)
            if (before.st_dev, before.st_ino) != (os.fstat(fd).st_dev, os.fstat(fd).st_ino):
                raise ValueError('directory changed during open')
            links.append((parent, name, before))
        yield handles[-1]
        for parent, name, before in links:
            current = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISDIR(current.st_mode) or (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino):
                raise ValueError('directory changed during use')
    finally:
        for fd in reversed(handles):
            os.close(fd)


def read_file(root, name, limit, *, optional=False, oversized_miss=False):
    parts = name.split('/')
    opened_path = False
    try:
        with directory(Path(root).joinpath(*parts[:-1])) as fd:
            before = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
            opened_path = True
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise ValueError('unsafe ordinary file')
            if before.st_size > limit:
                if oversized_miss:
                    return None
                raise ValueError('file exceeds read bound')
            with os.fdopen(os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd), 'rb') as handle:
                opened = os.fstat(handle.fileno())
                if file_identity(before) != file_identity(opened):
                    raise ValueError('file changed before read')
                data = handle.read(limit + 1)
                after = os.fstat(handle.fileno())
            current = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
            if len(data) > limit or file_identity(opened) != file_identity(after) or file_identity(after) != file_identity(current):
                raise ValueError('file changed during read')
            return data
    except FileNotFoundError:
        if optional and not opened_path:
            return None
        raise ValueError('file disappeared during verification') from None


def inventory(root):
    result, aliases = {}, {}
    def walk(fd, prefix):
        before = os.fstat(fd)
        with os.scandir(fd) as entries:
            for entry in entries:
                name = prefix + entry.name
                if len(result) >= MAX_ENTRIES or len(name) > 240 or len(name.split('/')) > 32:
                    raise ValueError('tree inventory bound exceeded')
                if (entry.name in ('', '.', '..') or entry.name.endswith(('.', ' '))
                        or '\\' in name or ':' in name or any(ord(c) < 32 or ord(c) == 127 for c in name)):
                    raise ValueError('unsafe tree name')
                key = path_key(name)
                if key in aliases:
                    raise ValueError('tree path alias')
                aliases[key] = name
                s = os.stat(entry.name, dir_fd=fd, follow_symlinks=False)
                if not stat.S_ISDIR(s.st_mode) and (not stat.S_ISREG(s.st_mode) or s.st_nlink != 1):
                    raise ValueError('unsafe tree member')
                result[name] = file_identity(s)
                if stat.S_ISDIR(s.st_mode):
                    child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        if file_identity(s) != file_identity(os.fstat(child)):
                            raise ValueError('tree directory changed')
                        walk(child, name + '/')
                    finally:
                        os.close(child)
                if file_identity(s) != file_identity(os.stat(entry.name, dir_fd=fd, follow_symlinks=False)):
                    raise ValueError('tree member changed')
        if file_identity(before) != file_identity(os.fstat(fd)):
            raise ValueError('tree changed during enumeration')
    with directory(root) as fd:
        walk(fd, '')
    return result


def expected_inventory(names):
    return set(names) | {'/'.join(p.split('/')[:i]) for p in names for i in range(1, len(p.split('/')))}


def private_root(temp, checkout):
    temp, checkout = Path(os.path.abspath(temp)), Path(os.path.abspath(checkout))
    if temp == checkout or checkout in temp.parents or temp in checkout.parents:
        raise ValueError('runner staging overlaps checkout')
    with directory(temp), directory(checkout):
        pass
    return temp


def new_stage(temp, name):
    with directory(temp) as fd:
        os.mkdir(name, mode=0o700, dir_fd=fd)
    return Path(temp) / name


def check_stage(stage):
    with directory(stage) as fd:
        s = os.fstat(fd)
        if s.st_uid != os.getuid() or s.st_mode & 0o077:
            raise ValueError('stage is not private')


def write_file(stage, name, data):
    # Only this process's exclusive private stage is writable by acquisition.
    check_stage(stage)
    target = Path(stage) / name
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with directory(target.parent) as fd:
        with os.fdopen(os.open(target.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd), 'wb') as handle:
            handle.write(data)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Transport:
    """One attempt per read, bounded redirects and bodies; no credential discovery."""
    def __init__(self, token='', *, opener=None):
        self.token = token
        self.opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        self.requests = self.bytes = 0
        self.deadline = time.monotonic() + 240

    def read(self, url, limit, kind):
        original = url
        for hop in range(4):
            parsed = urllib.parse.urlsplit(url)
            host = parsed.hostname
            if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.fragment:
                raise ValueError('unsafe transport origin')
            if ((kind == 'api' and host != 'api.github.com')
                    or (kind == 'raw' and (url != original or not url.startswith(RAW)))
                    or (kind == 'asset' and (host not in ('github.com', 'release-assets.githubusercontent.com')
                                            or (hop and host != 'release-assets.githubusercontent.com')))):
                raise ValueError('transport redirect/origin refused')
            if kind == 'api' and (not parsed.path.startswith(PREFIX + '/') or parsed.query):
                raise ValueError('non-official metadata path')
            remaining = self.deadline - time.monotonic()
            if remaining <= 0 or self.requests >= 64:
                raise ValueError('release request/time bound reached')
            headers = {'Accept': 'application/vnd.github+json' if kind == 'api' else 'application/octet-stream',
                       'User-Agent': 'section11-hosted-runtime'}
            if kind == 'api' and self.token:
                headers['Authorization'] = 'Bearer ' + self.token
                headers['X-GitHub-Api-Version'] = '2022-11-28'
            self.requests += 1
            try:
                response = self.opener.open(urllib.request.Request(url, headers=headers), timeout=min(30, remaining))
            except urllib.error.HTTPError as exc:
                if exc.code not in (301, 302, 303, 307, 308):
                    exc.close()
                    raise ValueError('release read refused: HTTP ' + str(exc.code)) from None
                location = exc.headers.get('Location')
                exc.close()
                if not location:
                    raise ValueError('release redirect lacks location')
                url = urllib.parse.urljoin(url, location)
                continue
            except (OSError, urllib.error.URLError):
                raise ValueError('release read failed; next run may try again') from None
            with response:
                chunks, size = [], 0
                while True:
                    # read1 returns after one buffered transport read, permitting
                    # elapsed checks between chunks. CP4 also sets a step deadline.
                    chunk = response.read1(min(65536, limit - size + 1))
                    size += len(chunk)
                    self.bytes += len(chunk)
                    if size > limit or self.bytes > 3 * MAX_BYTES or time.monotonic() > self.deadline:
                        raise ValueError('release byte/time bound reached')
                    if not chunk:
                        return b''.join(chunks)
                    chunks.append(chunk)
        raise ValueError('release redirect bound reached')

    def api(self, suffix):
        return decode(self.read(API + PREFIX + suffix, 4 * 1024 * 1024, 'api'))

    def resolve(self, tag):
        obj = self.api('/git/ref/tags/' + release_tag(tag)).get('object')
        seen = set()
        for _ in range(4):
            if not isinstance(obj, dict):
                break
            sha = commit_sha(obj.get('sha'))
            if obj.get('type') == 'commit':
                return sha
            if obj.get('type') != 'tag' or sha in seen:
                break
            seen.add(sha)
            obj = self.api('/git/tags/' + sha).get('object')
        raise ValueError('unresolved release tag')

    def official_manifest(self, commit):
        raw = self.read(RAW + commit_sha(commit) + '/manifest.json', MAX_MANIFEST, 'raw')
        manifest(raw)
        return raw


def metadata(transport, tag):
    tag = release_tag(tag)
    release = transport.api('/releases/tags/' + tag)
    if (not isinstance(release, dict) or release.get('tag_name') != tag
            or release.get('draft') is not False or release.get('prerelease') is not False
            or not isinstance(release.get('published_at'), str) or not release['published_at']
            or type(release.get('id')) is not int or release['id'] < 1
            or release.get('html_url') != 'https://github.com/' + REPOSITORY + '/releases/tag/' + tag
            or not isinstance(release.get('assets'), list) or len(release['assets']) > 32):
        raise ValueError('invalid stable release metadata')
    name = 'section11-' + tag + '.zip'
    assets = [a for a in release['assets'] if isinstance(a, dict) and a.get('name') == name]
    url = 'https://github.com/' + REPOSITORY + '/releases/download/' + tag + '/' + name
    if (len(assets) != 1 or type(assets[0].get('size')) is not int
            or not 0 < assets[0]['size'] <= MAX_BYTES or assets[0].get('browser_download_url') != url):
        raise ValueError('invalid canonical asset metadata')
    return assets[0]


def verify_files(raw, files):
    wanted = manifest(raw)
    if set(files) != set(wanted) or len(raw) + sum(map(len, files.values())) > MAX_BYTES:
        raise ValueError('release inventory/size mismatch')
    if any(digest(files[name]) != item['hash'] for name, item in wanted.items()):
        raise ValueError('release payload hash mismatch')


def archive(data, raw):
    wanted = manifest(raw)
    if len(data) > MAX_BYTES:
        raise ValueError('archive exceeds size bound')
    with zipfile.ZipFile(io.BytesIO(data)) as zipped:
        infos = zipped.infolist()
        expected = {'section11/' + p for p in wanted} | {'section11/manifest.json'}
        if len(infos) != len(expected) or {i.filename for i in infos} != expected:
            raise ValueError('canonical archive inventory mismatch')
        if sum(i.file_size for i in infos) > MAX_BYTES:
            raise ValueError('expanded archive exceeds size bound')
        for info in infos:
            if info.is_dir() or (info.external_attr >> 16) & 0o170000 not in (0, 0o100000) or info.flag_bits & 1:
                raise ValueError('unsafe archive member')
        if zipped.read('section11/manifest.json') != raw:
            raise ValueError('archive manifest differs from official source')
        files = {p: zipped.read('section11/' + p) for p in wanted}
    verify_files(raw, files)
    return files


def full_release(transport, tag, *, expected_commit=None, official_raw=None):
    asset = metadata(transport, tag)
    commit = transport.resolve(tag)
    if expected_commit is not None and commit != expected_commit:
        raise ValueError('release tag moved')
    raw = official_raw if official_raw is not None else transport.official_manifest(commit)
    data = transport.read(asset['browser_download_url'], MAX_BYTES, 'asset')
    if len(data) != asset['size']:
        raise ValueError('canonical asset length changed')
    files = archive(data, raw)
    if transport.resolve(tag) != commit:
        raise ValueError('release tag moved')
    return raw, files, {'tag': tag, 'commit': commit, 'repository': REPOSITORY,
                        'url': 'https://github.com/' + REPOSITORY + '/releases/tag/' + tag}


def installed_identity(checkout):
    control = read_file(checkout, '.section11-update.json', 8192, optional=True)
    state = decode(control) if control is not None else {}
    if not isinstance(state, dict):
        raise ValueError('invalid installed control data')
    control_tag = state.get('installed_date')
    if control_tag is not None:
        release_tag(control_tag)
    raw = read_file(Path(checkout) / 'section11', RECEIPT, 4096, optional=True)
    value = None
    if raw is not None:
        try:
            candidate = decode(raw)
        except ValueError:
            candidate = None
        if isinstance(candidate, dict):
            tag = candidate.get('tag')
            if tag is not None:
                release_tag(tag)
                if control_tag is not None and control_tag != tag:
                    raise ValueError('conflicting installed release identities')
                control_tag = tag
            # Readable provenance remains binding even with extra/noncanonical fields.
            if tag is not None and any(k in candidate for k in ('commit', 'manifest_sha256', 'repository')):
                if (candidate.get('repository') != REPOSITORY or candidate.get('schema') != 1
                        or not isinstance(candidate.get('manifest_sha256'), str)
                        or not re.fullmatch('[0-9a-f]{64}', candidate['manifest_sha256'])):
                    raise ValueError('invalid known installed provenance')
                commit_sha(candidate.get('commit'))
                value = candidate
    managed = Path(checkout) / 'section11'
    if control_tag is None and os.path.lexists(managed):
        raise ValueError('installed release identity unavailable; owner recovery required')
    return control_tag, value, raw


def check_application_api(files):
    contract = decode(files.get('examples/maintenance/wrapper-api.json', b'null'))
    if not isinstance(contract, dict) or type(contract.get('auto-sync.yml')) is not int or contract['auto-sync.yml'] != 2:
        raise ValueError('unsupported application wrapper API')
    if 'examples/sync.py' not in files or 'examples/maintenance/hosted.py' not in files:
        raise ValueError('release lacks hosted application')


def read_stage(stage, raw, identity):
    check_stage(stage)
    expected = expected_inventory(set(manifest(raw)) | {'manifest.json', RECEIPT})
    before = inventory(stage)
    if set(before) != expected:
        raise ValueError('staged inventory changed')
    if read_file(stage, 'manifest.json', MAX_MANIFEST) != raw or read_file(stage, RECEIPT, 4096) != receipt(raw, identity):
        raise ValueError('staged identity changed')
    files, size = {}, len(raw)
    for name in manifest(raw):
        files[name] = read_file(stage, name, MAX_BYTES - size)
        size += len(files[name])
    verify_files(raw, files)
    check_application_api(files)
    if inventory(stage) != before:
        raise ValueError('stage changed during verification')
    return raw, files, identity


def acquire_application(transport, checkout, temp, selected, operation='Sync', force=False):
    temp = private_root(temp, checkout)
    if operation not in ('Sync', 'Sync timer', 'Update', 'Status', 'Rollback') or type(force) is not bool:
        raise ValueError('unsupported acquisition intent')
    tag, known, local_receipt = installed_identity(checkout)
    first = tag is None
    tag = selected['tag'] if first else tag
    asset = metadata(transport, tag)
    commit = transport.resolve(tag)
    if tag == selected['tag'] and commit != selected['commit']:
        raise ValueError('selected release tag moved')
    raw = transport.official_manifest(commit)
    if tag == selected['tag'] and selected.get('manifest_sha256', digest(raw)) != digest(raw):
        raise ValueError('selected release manifest changed')
    identity = {'tag': tag, 'commit': commit, 'repository': REPOSITORY,
                'url': 'https://github.com/' + REPOSITORY + '/releases/tag/' + tag}
    if known and (known['commit'] != commit or known['manifest_sha256'] != digest(raw)):
        raise ValueError('installed release provenance changed')
    wanted = manifest(raw)
    managed = Path(checkout) / 'section11'
    before = inventory(managed) if os.path.lexists(managed) else {}
    expected = expected_inventory(set(wanted) | {'manifest.json', RECEIPT})
    aliases = {path_key(p): p for p in expected}
    if any(path_key(p) in aliases and aliases[path_key(p)] != p for p in before):
        raise ValueError('checkout path aliases official inventory')
    stage = new_stage(temp, 'section11-trusted-source')
    hit = (not first and not force and operation in ('Sync', 'Sync timer')
           and local_receipt == receipt(raw, identity)
           and set(before) == expected
           and read_file(managed, 'manifest.json', MAX_MANIFEST, optional=True, oversized_miss=True) == raw)
    if (before or os.path.lexists(managed)) and inventory(managed) != before:
        raise ValueError('checkout changed during identity check')
    size = len(raw)
    # Keep miss copies private and never overwrite them with release content.
    copied = {}
    if hit:
        for name, item in wanted.items():
            data = read_file(managed, name, MAX_BYTES - size, oversized_miss=True)
            if data is None:
                hit = False
                break
            size += len(data)
            copied[name] = data
        if inventory(managed) != before:
            raise ValueError('checkout changed during fingerprint copy')
        if hit:
            for name, data in copied.items():
                write_file(stage, name, data)
            # Hash actual completed copies, not later reads from checkout paths.
            hit = all(digest(read_file(stage, p, MAX_BYTES)) == wanted[p]['hash'] for p in wanted)
    if not hit:
        if copied and any(stage.iterdir()):
            # Retain the failed private candidate for this job only; no deletion
            # of checkout paths or reuse of an incomplete execution stage.
            stage.rename(Path(temp) / 'section11-fingerprint-miss')
            stage = new_stage(temp, 'section11-trusted-source')
        data = transport.read(asset['browser_download_url'], MAX_BYTES, 'asset')
        if len(data) != asset['size']:
            raise ValueError('canonical asset length changed')
        files = archive(data, raw)
        for name, data in files.items():
            write_file(stage, name, data)
    write_file(stage, 'manifest.json', raw)
    write_file(stage, RECEIPT, receipt(raw, identity))
    release = read_stage(stage, raw, identity)
    if (before or os.path.lexists(managed)) and inventory(managed) != before:
        raise ValueError('checkout changed during acquisition')
    if transport.resolve(tag) != commit:
        raise ValueError('installed release tag moved')
    print('Section 11 acquisition ' + ('hit' if hit else 'full ZIP') + ': ' + tag
          + '; requests=' + str(transport.requests) + '; bytes=' + str(transport.bytes))
    return release


def clean_environment(env):
    return {k: v for k, v in env.items() if k not in ('GH_TOKEN', 'GITHUB_TOKEN') and not k.startswith('GIT_CONFIG')}


def runtime_payload(temp, raw, entry, selected, *, checkout, transport=None):
    files = manifest(raw)
    if not set(PAYLOAD + (ENTRY,)) <= set(files) or digest(entry) != files[ENTRY]['hash']:
        raise ValueError('release lacks authenticated runtime payload')
    temp = private_root(temp, checkout)
    managed = Path(checkout) / 'section11'
    def snapshot():
        with directory(checkout) as fd:
            try:
                root = os.stat('section11', dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                return None, {}
            return file_identity(root), inventory(managed)
    root, before = snapshot()
    aliases = {path_key(p): p for p in expected_inventory(set(files) | {'manifest.json', RECEIPT})}
    if any(path_key(p) in aliases and aliases[path_key(p)] != p for p in before):
        raise ValueError('checkout path aliases official inventory')
    stage = new_stage(temp, 'section11-runtime')
    transport = transport or Transport()
    payload = {ENTRY: entry}
    total = len(raw) + len(entry)
    reused = fetched = 0
    for name in PAYLOAD:
        data = read_file(managed, name, MAX_BYTES - total, optional=name not in before,
                         oversized_miss=True) if root is not None else None
        if data is not None and digest(data) == files[name]['hash']:
            reused += 1
        else:
            data = transport.read(RAW + selected['commit'] + '/' + name, MAX_BYTES - total, 'raw')
            fetched += 1
        total += len(data)
        if digest(data) != files[name]['hash']:
            raise ValueError('runtime payload hash mismatch')
        payload[name] = data
    if snapshot() != (root, before):
        raise ValueError('checkout changed during runtime copy')
    check_application_api(payload)
    for name, data in payload.items():
        write_file(stage, name, data)
    verify_runtime(temp, raw, entry)
    print('Section 11 runtime verified: reused=' + str(reused) + '; fetched=' + str(fetched)
          + '; requests=' + str(transport.requests) + '; bytes=' + str(transport.bytes))
    return stage


def verify_runtime(temp, raw, entry):
    stage = Path(temp) / 'section11-runtime'
    check_stage(stage)
    before = inventory(stage)
    if set(before) != expected_inventory(PAYLOAD + (ENTRY,)):
        raise ValueError('runtime inventory changed')
    wanted, payload, total = manifest(raw), {}, len(raw)
    for name in PAYLOAD + (ENTRY,):
        payload[name] = read_file(stage, name, MAX_BYTES - total)
        total += len(payload[name])
        if name not in wanted or digest(payload[name]) != wanted[name]['hash']:
            raise ValueError('runtime payload hash mismatch')
    if payload[ENTRY] != entry or inventory(stage) != before:
        raise ValueError('runtime changed during verification')
    check_application_api(payload)
    return stage


def load_controller(stage):
    """Called only after every runtime dependency has passed verification."""
    sys.path.insert(0, str(Path(stage) / 'examples/maintenance'))
    spec = importlib.util.spec_from_file_location('section11_verified_hosted', Path(stage) / 'examples/maintenance/hosted.py')
    controller = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(controller)
    if controller.WRAPPER_API != 2:
        raise ValueError('unsupported controller wrapper API')
    return controller


class Runtime:
    def __init__(self, transport, selected, raw):
        self.transport, self.selected, self.raw = transport, selected, raw
        self._latest = None

    def latest(self):
        if self._latest is None:
            self._latest = full_release(self.transport, self.selected['tag'],
                                        expected_commit=self.selected['commit'], official_raw=self.raw)
        return self._latest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=PHASES)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--wrapper-api', type=int, required=True)
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--application-sha256')
    parser.add_argument('--application-tag')
    parser.add_argument('--application-commit')
    parser.add_argument('--accept-install', action='store_true')
    parser.add_argument('--force-release-download', action='store_true')
    args = parser.parse_args()
    if args.wrapper_api != 2:
        raise ValueError('unsupported wrapper API')
    selected = {'tag': release_tag(args.tag), 'commit': commit_sha(args.commit)}
    # These bytes are passed in memory by the fixed gate, never by a checkout import.
    raw, entry = globals().get('OFFICIAL_MANIFEST'), globals().get('VERIFIED_ENTRY')
    if not isinstance(raw, bytes) or not isinstance(entry, bytes):
        raise ValueError('start the runtime through the fixed gate')
    selected['manifest_sha256'] = digest(raw)
    if args.phase != 'bootstrap' and args.manifest_sha256 != digest(raw):
        raise ValueError('selected runtime manifest changed')
    token = os.environ.get('GITHUB_TOKEN', '')
    ambient_credential = any(k in ('GH_TOKEN', 'GITHUB_TOKEN') or k.startswith('GIT_CONFIG') for k in os.environ)
    clean = clean_environment(os.environ)
    os.environ.clear()
    os.environ.update(clean)
    if args.phase == 'bootstrap' and ambient_credential:
        raise ValueError('initial runtime verification must be token-free')
    temp = private_root(os.environ['RUNNER_TEMP'], os.environ['GITHUB_WORKSPACE'])
    if args.phase == 'bootstrap':
        runtime_payload(temp, raw, entry, selected, checkout=os.environ['GITHUB_WORKSPACE'])
        emit(manifest_sha256=digest(raw))
        return
    stage = verify_runtime(temp, raw, entry)
    controller = load_controller(stage)
    privileged = args.phase in ('prepare', 'publish', 'maintain')
    if privileged and not token:
        raise ValueError('explicit job token missing')
    transport = Transport(token if privileged else '')
    runtime = Runtime(transport, selected, raw)
    if privileged and transport.resolve(selected['tag']) != selected['commit']:
        raise ValueError('selected runtime tag moved')
    if args.phase == 'prepare':
        if not args.accept_install:
            raise ValueError('explicit installation acceptance missing')
        event = decode(read_file(Path(os.environ['GITHUB_EVENT_PATH']).parent,
                                 Path(os.environ['GITHUB_EVENT_PATH']).name, MAX_MANIFEST))
        operation = event.get('inputs', {}).get('operation', 'Sync') or 'Sync'
        release = acquire_application(transport, os.environ['GITHUB_WORKSPACE'], temp, selected,
                                      operation, args.force_release_download)
        os.environ['GITHUB_TOKEN'] = token
        controller.prepare(temp / 'section11-trusted-source', release, controller._sync,
                           runtime=runtime, argv=['--wrapper-api', '2', '--accept-install'])
        emit(application_tag=release[2]['tag'], application_commit=release[2]['commit'],
             application_sha256=digest(release[0]))
        print('Section 11 upstream total: requests=' + str(transport.requests) + '; bytes=' + str(transport.bytes))
        return
    identity = {'tag': release_tag(args.application_tag), 'commit': commit_sha(args.application_commit)}
    source = temp / 'section11-trusted-source'
    app_raw = read_file(source, 'manifest.json', MAX_MANIFEST)
    if digest(app_raw) != args.application_sha256:
        raise ValueError('application manifest changed between phases')
    read_stage(source, app_raw, identity)
    info = controller.context()
    if info.get('source') != str(source) or info.get('source_identity', {}).get('commit') != identity['commit'] or info.get('source_identity', {}).get('tag') != identity['tag']:
        raise ValueError('controller application identity changed')
    if privileged:
        os.environ['GITHUB_TOKEN'] = token
    if args.phase == 'maintain':
        controller.maintain(runtime=runtime)
    else:
        try:
            {'cache-prepare': controller.cache_prepare, 'sync': lambda: controller.run_sync(isolated=True),
             'finalize-export': controller.finalize_export, 'validate': controller.validate_generated,
             'publish': controller.publish_data, 'cache-promote': controller.cache_promote}[args.phase]()
        except RuntimeError:
            if args.phase == 'publish':
                info = controller.context()
                info['publication_uncertain'] = True
                controller.context(info)
            raise
    if privileged:
        print('Section 11 upstream total: requests=' + str(transport.requests) + '; bytes=' + str(transport.bytes))


def emit(**values):
    # CP4 captures these values as step outputs, outside the data checkout.
    path = os.environ.get('GITHUB_OUTPUT')
    if path:
        with open(path, 'a') as handle:
            for name, value in values.items():
                handle.write(name + '=' + value + '\n')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError, zipfile.BadZipFile):
        # Transport exception strings may contain signed asset URLs. Never echo them.
        print('::error::Hosted acquisition or phase verification failed; no retry in this run.', file=sys.stderr)
        sys.exit(1)
