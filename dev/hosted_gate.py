"""Fixed no-network gate. CP4 embeds this exact file; dev/ is not released."""
import hashlib
import json
import os
import re
import stat
import sys
import unicodedata

ENTRY = 'examples/maintenance/hosted_runtime.py'
LIMIT = 1024 * 1024


def pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError('duplicate manifest key')
        value[key] = item
    return value


def manifest(raw):
    if len(raw) > LIMIT:
        raise ValueError('manifest exceeds gate bound')
    obj = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                     parse_constant=lambda _: (_ for _ in ()).throw(ValueError('invalid JSON constant')))
    files = obj.get('files') if isinstance(obj, dict) else None
    schema = obj.get('schema_version', 1) if isinstance(obj, dict) else None
    if type(schema) is not int or schema not in (1, 2) or not isinstance(files, dict) or not 0 < len(files) <= 512:
        raise ValueError('unsupported manifest schema or inventory')
    aliases, leaves = {}, set()
    for name, item in files.items():
        parts = name.split('/')
        if (not name or len(name) > 240 or name != name.strip() or '\\' in name or ':' in name
                or any(ord(c) < 32 or ord(c) == 127 for c in name)
                or any(not p or p.startswith('.') or p.endswith(('.', ' ')) for p in parts)
                or parts[0] in {'dev', 'custom', 'section11', 'maps', 'archive', 'node_modules'}
                or unicodedata.normalize('NFC', name).casefold() == 'manifest.json'
                or name in {'manifest.json', 'DOSSIER.md', 'latest.json', 'history.json', 'intervals.json',
                            'routes.json', 'saved_workouts.json', 'ftp_history.json', 'route_eta_history.json'}):
            raise ValueError('unsafe manifest path')
        for i in range(1, len(parts) + 1):
            path = '/'.join(parts[:i])
            key = unicodedata.normalize('NFC', path).casefold()
            if key in aliases and aliases[key] != path:
                raise ValueError('manifest path alias')
            aliases[key] = path
        if not isinstance(item, dict) or not isinstance(item.get('hash'), str) or not re.fullmatch('[0-9a-f]{64}', item['hash']):
            raise ValueError('invalid manifest hash')
        leaves.add(name)
    if any('/'.join(p.split('/')[:i]) in leaves for p in leaves for i in range(1, len(p.split('/')))):
        raise ValueError('manifest file/directory collision')
    if ENTRY not in files:
        raise ValueError('manifest lacks hosted runtime entry')
    return files


def read(path):
    """Read one exact ordinary file through no-follow directory handles."""
    parts = os.path.abspath(path).split('/')[1:]
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        before = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
        with os.fdopen(os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd), 'rb') as handle:
            opened = os.fstat(handle.fileno())
            if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1 or opened != before or opened.st_size > LIMIT:
                raise ValueError('unsafe gate input')
            data = handle.read(LIMIT + 1)
            after = os.fstat(handle.fileno())
        current = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        if len(data) > LIMIT or identity(opened) != identity(after) or identity(after) != identity(current):
            raise ValueError('gate input changed during read')
        return data
    finally:
        os.close(fd)


def verify(raw, entry):
    files = manifest(raw)
    if len(entry) > LIMIT or hashlib.sha256(entry).hexdigest() != files[ENTRY]['hash']:
        raise ValueError('hosted runtime hash mismatch')
    return entry


def main():
    base = os.path.join(os.environ['RUNNER_TEMP'], 'section11-entry')
    checkout = os.path.abspath(os.environ['GITHUB_WORKSPACE'])
    if os.path.commonpath((os.path.abspath(base), checkout)) == checkout:
        raise ValueError('entry staging is inside checkout')
    s = os.stat(base, follow_symlinks=False)
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077:
        raise ValueError('entry staging is not private')
    path = os.path.join(base, 'hosted_runtime.py')
    raw = read(os.path.join(base, 'manifest.json'))
    # Later phases bind the manifest before executing any release code. CP4
    # supplies this digest from the successful token-free bootstrap step output.
    if len(sys.argv) < 2 or sys.argv[1] != 'bootstrap':
        if sys.argv.count('--manifest-sha256') != 1:
            raise ValueError('selected manifest digest required')
        index = sys.argv.index('--manifest-sha256') + 1
        if index == len(sys.argv) or not re.fullmatch('[0-9a-f]{64}', sys.argv[index]) or hashlib.sha256(raw).hexdigest() != sys.argv[index]:
            raise ValueError('selected manifest changed before runtime execution')
    entry = verify(raw, read(path))
    # Execute the verified bytes themselves, never reopen an executable pathname.
    exec(compile(entry, path, 'exec'), {'__name__': '__main__', '__file__': path,
         'OFFICIAL_MANIFEST': raw, 'VERIFIED_ENTRY': entry})


if __name__ == '__main__':
    main()
