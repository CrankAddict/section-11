"""Deterministic canonical ZIP and lossless reading edition from one manifest."""
import argparse
import io
import json
import re
import zipfile
from pathlib import Path

from distribution import Distribution, DistributionError
from seal_pins import BOOTSTRAP, WORKFLOWS, validate_payload

IMAGE = 'examples/reports/example-route-weather-map.png'
TEXT_SUFFIXES = {'.md', '.txt', '.json', '.yml', '.yaml'}
MAGIC = b'SECTION11-READING-1\n'


def delivery_assets(files, tag):
    if BOOTSTRAP not in files:
        return {}  # Older release fixtures retain the canonical four assets.
    validate_payload(files)
    paths = {'hosted-bootstrap.py': BOOTSTRAP, 'auto-sync.yml': WORKFLOWS[0],
             'on-demand.yml': WORKFLOWS[1]}
    return {'section11-' + tag + '-' + label: files[path] for label, path in paths.items()}


def notes(files):
    protocol = files['SECTION_11.md'].decode('utf-8')
    version, sync = Distribution.identity(files)
    match = re.search(r'(?ms)^\*\*v' + re.escape(version) + r' - .*?(?=^\*\*v|\Z)', protocol)
    if not match:
        raise DistributionError('current protocol changelog entry missing')
    digest = Distribution.json(files['changelog.json'])
    if not isinstance(digest.get('changes'), list) or not all(isinstance(x, str) for x in digest['changes']):
        raise DistributionError('invalid changelog.json changes')
    return ('Protocol ' + version + '; sync ' + sync + '\n\n' + match[0].strip() +
            '\n\nExisting notification digest (' + str(digest.get('notification_id', 'undated')) +
            '; may cover older releases):\n\n' + '\n'.join('- ' + x for x in digest['changes']) +
            '\n\nReview custom overrides. Merging does not replace uploaded files or pasted instructions.\n')


def encode_book(kind, members, identity, index):
    header = dict(identity, book=kind, index=index,
                  notice='Complete original sources. JSON examples are fictional, not athlete data. '
                         'Code and quoted instructions are reference material, not commands to execute. '
                         'Original paths remain authoritative. Neither upload format is recommended yet.')
    out = bytearray(MAGIC + json.dumps(header, sort_keys=True).encode() + b'\n')
    for path, content in members:
        content.decode('utf-8')
        frame = {'path': path, 'bytes': len(content), 'sha256': Distribution.digest(content)}
        out.extend(json.dumps(frame, sort_keys=True).encode() + b'\n')
        out.extend(content)
        out.extend(b'\n')
    return bytes(out)


def decode_book(content):
    stream = io.BytesIO(content)
    if stream.readline() != MAGIC:
        raise ValueError('invalid reading magic')
    header = Distribution.json(stream.readline())
    result = {}
    while line := stream.readline():
        frame = Distribution.json(line)
        path, size = frame['path'], frame['bytes']
        Distribution.path(path)
        if path in result or type(size) is not int or not 0 <= size <= Distribution.MAX_BYTES:
            raise ValueError('invalid reading frame')
        body = stream.read(size)
        if len(body) != size or stream.read(1) != b'\n' or Distribution.digest(body) != frame['sha256']:
            raise ValueError('truncated/corrupt reading frame')
        body.decode('utf-8')
        result[path] = body
    return header, result


def build(raw, files, commit, tag):
    Distribution.verify(raw, files)
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('exact source commit required')
    version, sync = Distribution.identity(files)
    Distribution.release_date(tag)
    identity = {'release': tag, 'protocol': version, 'sync': sync, 'commit': commit}
    all_files = dict(files, **{'manifest.json': raw})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(all_files):
            info = zipfile.ZipInfo('section11/' + path, (1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, all_files[path])
    canonical = buffer.getvalue()
    checked_raw, checked_files = Distribution.archive(canonical)
    if checked_raw != raw or checked_files != files:
        raise ValueError('canonical ZIP reconstruction failed')
    groups = {'reference': [], 'tools': []}
    index = []
    image = None
    for path in sorted(all_files, key=lambda p: (p != 'SECTION_11.md', p)):
        content = all_files[path]
        if path == IMAGE:
            image = content
            kind = 'image'
        elif Path(path).suffix == '.py':
            kind = 'tools'
            groups[kind].append((path, content))
        elif Path(path).suffix in TEXT_SUFFIXES or path == 'LICENSE':
            kind = 'reference'
            groups[kind].append((path, content))
        else:
            raise ValueError('unclassified release member: ' + path)
        index.append({'path': path, 'asset': kind, 'bytes': len(content), 'sha256': Distribution.digest(content)})
    if image is None:
        raise ValueError('original example PNG missing')
    assets = {'section11-' + tag + '.zip': canonical}
    reconstructed = {IMAGE: image}
    for kind, members in groups.items():
        book = encode_book(kind, members, identity, index)
        header, decoded = decode_book(book)
        if header['index'] != index or set(decoded) & set(reconstructed):
            raise ValueError('reading index/coverage mismatch')
        reconstructed.update(decoded)
        assets['section11-' + tag + '-' + kind + '.txt'] = book
    assets['section11-' + tag + '-example-route-weather-map.png'] = image
    if reconstructed != all_files:
        raise ValueError('reading reconstruction differs from manifest inventory')
    # Detached delivery files are exact manifest-covered bytes, not separately
    # generated templates. The publisher reads every asset back before/after publish.
    assets.update(delivery_assets(files, tag))
    return assets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw, files = Distribution.tree(args.source)
    assets = build(raw, files, args.commit, args.tag)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, content in assets.items():
        (args.output / name).write_bytes(content)
    print(json.dumps({'files': len(files) + 1, 'reconstruction': 'verified',
                      'assets': {p: {'bytes': len(b), 'sha256': Distribution.digest(b)}
                                 for p, b in assets.items()}}, indent=2))


if __name__ == '__main__':
    main()
