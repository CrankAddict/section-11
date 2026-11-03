"""Exact-tree, single-parent GitHub publication. No force, rebase or write retry."""
import base64
import hashlib
import re
from urllib.parse import quote

from distribution import UnknownOutcome


def sha(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{40}', value):
        raise ValueError('invalid Git object identity')
    return value


def blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def path_name(name):
    if (not isinstance(name, str) or not name or len(name) > 1024
            or any(c in name for c in '\\\0\r\n\t')
            or any(p in ('', '.', '..') for p in name.split('/'))):
        raise ValueError('unsafe Git tree path')
    return name


def checked_tree(entries):
    if not isinstance(entries, dict) or len(entries) > 10000:
        raise ValueError('Git tree exceeds the 10000-entry bound')
    result = {}
    folded = set()
    for name, entry in entries.items():
        path_name(name)
        if name.casefold() in folded or entry.get('path') != name:
            raise ValueError('ambiguous Git tree path')
        folded.add(name.casefold())
        mode, kind = entry.get('mode'), entry.get('type')
        if (mode, kind) not in (('100644', 'blob'), ('100755', 'blob'),
                                ('120000', 'blob'), ('160000', 'commit')):
            raise ValueError('invalid Git tree entry')
        result[name] = {'path': name, 'mode': mode, 'type': kind, 'sha': sha(entry.get('sha'))}
    for name in folded:
        if any('/'.join(name.split('/')[:i]) in folded for i in range(1, len(name.split('/')))):
            raise ValueError('Git file/directory collision')
    return result


class DirectPublisher:
    """Transport receives only trusted, independently validated change plans.

    Remote tree object IDs bind every untouched byte and mode. Changed blobs are
    read back by their Git content identity, then the full tree and sole parent
    are checked before the one non-forced ref update. API calls are injectable.
    """
    def __init__(self, api, default=None):
        self.api = api
        metadata = api.metadata()
        self.default = metadata['default_branch']
        if (not isinstance(self.default, str) or not self.default or
                any(c in self.default for c in '\0\r\n') or
                (default is not None and self.default != default)):
            raise ValueError('default branch changed or is invalid')
        self.ref = '/git/ref/heads/' + quote(self.default, safe='')
        self.write_ref = '/git/refs/heads/' + quote(self.default, safe='')

    def tip(self):
        obj = self.api.get(self.ref)['object']
        if obj.get('type') != 'commit':
            raise ValueError('default branch is not a commit')
        return sha(obj.get('sha'))

    def snapshot(self, commit=None):
        commit = self.tip() if commit is None else sha(commit)
        obj = self.api.get('/git/commits/' + commit)
        if obj.get('sha') != commit:
            raise ValueError('commit readback mismatch')
        tree = sha(obj['tree']['sha'])
        return {'commit': commit, 'tree': tree, 'entries': checked_tree(self.api.tree(tree)),
                'parents': [sha(p['sha']) for p in obj['parents']],
                'message': obj['message']}

    def read(self, snapshot, name, limit=64 * 1024 * 1024):
        entry = snapshot['entries'].get(name)
        if entry is None:
            return None
        if entry['type'] != 'blob' or entry['mode'] not in ('100644', '100755'):
            raise ValueError('non-ordinary publication path')
        data = self.api.blob(entry['sha'])
        if len(data) > limit or blob_sha(data) != entry['sha']:
            raise ValueError('Git blob readback mismatch or size bound')
        return data

    def publish(self, before, changes, message, validate, modes=None):
        """validate(before, changes) must reject every unauthorized scope/value."""
        validate(before, changes)
        modes = dict(modes or {})
        if any(name not in changes or changes[name] is None or mode not in ('100644', '100755')
               for name, mode in modes.items()):
            raise ValueError('invalid approved file modes')
        if len(changes) > 10000 or not isinstance(message, str) or len(message) > 8192:
            raise ValueError('publication plan exceeds bounds')
        wanted = dict(before['entries'])
        updates = []
        total = 0
        for name, data in sorted(changes.items()):
            path_name(name)
            if data is None:
                if name in wanted:
                    del wanted[name]
                    updates.append({'path': name, 'mode': before['entries'][name]['mode'],
                                    'type': before['entries'][name]['type'], 'sha': None})
            else:
                if not isinstance(data, bytes):
                    raise ValueError('publication content must be bytes')
                total += len(data)
                if total > 256 * 1024 * 1024:
                    raise ValueError('publication byte bound exceeded')
                entry = {'path': name, 'mode': modes.get(name, '100644'), 'type': 'blob', 'sha': blob_sha(data)}
                if entry != wanted.get(name):
                    wanted[name] = entry
                    updates.append(entry)
        checked_tree(wanted)
        if not updates:
            return before
        if self.tip() != before['commit']:
            raise ValueError('default tip changed; no publication, start a fresh run')
        # Orphan Git objects are harmless if a later guard refuses publication.
        for entry in updates:
            if entry['sha'] is not None:
                obj = self.api.write('POST', '/git/blobs', {
                    'encoding': 'base64', 'content': base64.b64encode(changes[entry['path']]).decode()})
                if obj.get('sha') != entry['sha']:
                    raise ValueError('created blob identity differs from approved bytes')
        obj = self.api.write('POST', '/git/trees', {'base_tree': before['tree'], 'tree': updates})
        tree = sha(obj.get('sha'))
        if checked_tree(self.api.tree(tree)) != wanted:
            raise ValueError('prepared complete tree differs from approved plan')
        obj = self.api.write('POST', '/git/commits', {
            'message': message, 'tree': tree, 'parents': [before['commit']]})
        commit = sha(obj.get('sha'))
        prepared = self.snapshot(commit)
        if (prepared['tree'] != tree or prepared['entries'] != wanted
                or prepared['parents'] != [before['commit']] or prepared['message'] != message):
            raise ValueError('prepared commit differs from approved parent/tree/message')
        validate(before, changes)
        if self.tip() != before['commit']:
            raise ValueError('default tip changed; no publication, start a fresh run')
        failure = None
        try:
            self.api.write('PATCH', self.write_ref, {'sha': commit, 'force': False})
        except Exception as exc:
            failure = exc
        # Read back after success, denial and lost responses alike. Never retry.
        try:
            remote = self.tip()
            present = remote == commit
            if not present:
                comparison = self.api.get('/compare/' + commit + '...' + remote)
                present = comparison.get('status') in ('ahead', 'identical')
                if comparison.get('status') not in ('ahead', 'identical', 'behind', 'diverged'):
                    raise ValueError('unrecognized ancestry response')
            if present:
                current = self.snapshot(remote)
                if remote == commit and current != prepared:
                    raise ValueError('published commit readback differs')
                print('Confirmed publication:', commit)
                if remote != commit:
                    raise UnknownOutcome('publication confirmed in history; default advanced afterwards; '
                                         'inspect current state before another run: ' + commit)
                return current
        except UnknownOutcome:
            raise
        except Exception as exc:
            raise UnknownOutcome('publication outcome unknown; no retry; inspect commit ' + commit) from exc
        if failure is not None:
            raise RuntimeError('publication not on observed default history; no retry; inspect commit ' + commit) from failure
        raise UnknownOutcome('acknowledged publication absent on readback; no retry; inspect commit ' + commit)
