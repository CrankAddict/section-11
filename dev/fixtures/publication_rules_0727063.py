import json
import os
import re
import shutil
import stat
import struct
import sys
import zlib
from pathlib import Path

MAX_BYTES = 64 * 1024 * 1024
MAX_FILES = 128
FALLBACK = ('latest.json', 'history.json', 'intervals.json', 'routes.json',
            'saved_workouts.json', 'ftp_history.json', 'route_eta_history.json')

def checked_path(root, relative):
    if (not isinstance(relative, str) or len(relative) > 240
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./-]*', relative)
            or any(part.startswith('.') or not part for part in relative.split('/'))
            or Path(relative).suffix not in ('.json', '.png')):
        raise ValueError('unsafe data path')
    target = root
    parts = relative.split('/')
    for index, part in enumerate(parts):
        target = target / part
        if target.is_symlink():
            raise ValueError('symlink data path')
        if target.exists():
            mode = target.stat().st_mode
            if not (stat.S_ISREG(mode) if index == len(parts) - 1 else stat.S_ISDIR(mode)):
                raise ValueError('non-ordinary data path')
    return target

def read_data(root, relative):
    target = checked_path(root, relative)
    if target.stat().st_size > MAX_BYTES:
        raise ValueError('data file exceeds 64 MiB')
    content = target.read_bytes()
    if len(content) > MAX_BYTES:
        raise ValueError('data file exceeds 64 MiB')
    if target.suffix == '.json':
        def invalid_constant(value):
            raise ValueError('non-finite JSON number')
        json.loads(content, parse_constant=invalid_constant)
    else:
        if (len(content) < 33 or content[:8] != b'\x89PNG\r\n\x1a\n'
                or content[8:16] != b'\x00\x00\x00\x0dIHDR'
                or struct.unpack('>I', content[29:33])[0] != zlib.crc32(content[12:29]) & 0xffffffff):
            raise ValueError('invalid PNG signature or IHDR')
        width, height, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', content[16:29])
        depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
        if (not 0 < width <= 16384 or not 0 < height <= 16384 or depth not in depths.get(color, ())
                or compression or filtering or interlace not in (0, 1)):
            raise ValueError('invalid PNG IHDR fields')
    return content

def declared(document, root):
    overview = document['data_overview']
    paths = overview['managed_files']
    if (overview.get('version') != 1 or not isinstance(paths, list)
            or not 1 <= len(paths) <= MAX_FILES or not all(isinstance(p, str) for p in paths)
            or len(set(paths)) != len(paths) or 'latest.json' not in paths):
        raise ValueError('invalid sync file declaration')
    for relative in paths:
        checked_path(root, relative)
    return sorted(paths)

def plan(root, previous=None):
    latest = json.loads(read_data(root, 'latest.json'))
    mode = 'declared'
    try:
        current = declared(latest, root)
        for relative in current:
            read_data(root, relative)
    except (KeyError, TypeError, ValueError, OSError):
        mode = 'legacy_fallback'
        current = []
        for relative in FALLBACK:
            target = checked_path(root, relative)
            if target.exists():
                read_data(root, relative)
                current.append(relative)
    removed = []
    if mode == 'declared' and previous is not None:
        try:
            old = declared(previous, root)
            removed = sorted(set(old) - set(current))
            for relative in removed:
                target = checked_path(root, relative)
                if target.exists():
                    read_data(root, relative)
        except (KeyError, TypeError, ValueError, OSError):
            # Invalid prior ownership evidence never authorizes deletion.
            removed = []
    return {'mode': mode, 'saved': sorted(current), 'removed': removed,
            'touched': sorted(set(current) | set(removed))}

def prepare(root, previous_path, stage):
    try:
        previous = json.loads(previous_path.read_bytes())
    except (OSError, ValueError):
        previous = None
    result = plan(root, previous)
    stage.mkdir()  # A new runner-local stage, never merge old contents.
    for relative in result['saved']:
        target = stage / 'files' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(read_data(root, relative))
    (stage / 'plan.json').write_text(json.dumps(result))
    for key in ('saved', 'removed', 'touched'):
        (stage / (key + '.txt')).write_text(''.join(p + '\n' for p in result[key]))
    print('Publication validation:', result['mode'], len(result['saved']), 'files')

def restore(root, stage):
    result = json.loads((stage / 'plan.json').read_bytes())
    # Validate every destination after reset before any write or deletion.
    for relative in result['touched']:
        checked_path(root, relative)
    for relative in result['saved']:
        read_data(stage / 'files', relative)
    for relative in result['removed']:
        checked_path(root, relative).unlink(missing_ok=True)
    for relative in result['saved']:
        target = checked_path(root, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(stage / 'files' / relative, target)

if __name__ == '__main__':
    root = Path.cwd()
    stage = Path(os.environ['RUNNER_TEMP']) / 'section11-output'
    if sys.argv[1] == 'prepare':
        prepare(root, Path(os.environ['RUNNER_TEMP']) / 'tracked-latest.json', stage)
    elif sys.argv[1] == 'restore':
        restore(root, stage)
    else:
        raise ValueError('unknown publication operation')
