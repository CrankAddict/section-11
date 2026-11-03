"""Seal reviewed bytes offline; independently read back published Git blobs.

No commits, publication, tag resolution, retries or manifest generation.
Blob SHA1 addresses bytes; a separate SHA256 authenticates their exact content.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.request

UPSTREAM = 'https://api.github.com/repos/CrankAddict/section-11'
VERIFIER = 'examples/sync.py'
BOOTSTRAP = 'examples/maintenance/hosted_bootstrap.py'
WORKFLOWS = ('examples/json-auto-sync/auto-sync.yml', 'examples/json-on-demand/auto-sync.yml')
MAX_BYTES = 8 * 1024 * 1024


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def blob_id(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def require_pin(blob, digest):
    if not re.fullmatch('[0-9a-f]{40}', blob) or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('unsealed or malformed source pins')


def pins(data, prefix):
    text = data.decode('utf-8')
    values = []
    for suffix in ('BLOB', 'SHA256'):
        pattern = (r"^" + prefix + '_' + suffix + r" = '([^']+)'$" if prefix == 'VERIFIER'
                   else r'^      ' + prefix + '_' + suffix + r': ([^\s]+)$')
        matches = re.findall(pattern, text, re.M)
        if len(matches) != 1:
            raise ValueError('missing or ambiguous pin block')
        values.append(matches[0])
    return tuple(values)


class PublishedSource:
    def __init__(self, token):
        if not token:
            raise ValueError('GITHUB_TOKEN is required for authenticated source readback')
        self.token = token
        self.count = 0
        self.deadline = time.monotonic() + 60

    def read(self, suffix, raw=False):
        if not re.fullmatch(r'/git/(?:trees|blobs)/[0-9a-f]{40}(?:\?recursive=1)?', suffix):
            raise ValueError('unexpected source endpoint')
        remaining = self.deadline - time.monotonic()
        if self.count >= 40 or remaining <= 0:
            raise ValueError('source readback admission bound reached')
        self.count += 1
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                raise ValueError('source readback redirect refused')
        request = urllib.request.Request(UPSTREAM + suffix, headers={
            'Authorization': 'Bearer ' + self.token,
            'Accept': 'application/vnd.github.raw+json' if raw else 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28'})
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=min(10, remaining)) as response:
            limit = MAX_BYTES if raw else 2 * MAX_BYTES
            data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError('source readback response exceeds bound')
        return data if raw else json.loads(data)

    def blob(self, identity, digest):
        require_pin(identity, digest)
        first = self.read('/git/blobs/' + identity, raw=True)
        if not 0 < len(first) <= MAX_BYTES or blob_id(first) != identity or sha256(first) != digest:
            raise ValueError('published blob identity or digest differs')
        blob = self.read('/git/blobs/' + identity)
        if blob.get('sha') != identity or blob.get('encoding') != 'base64' or type(blob.get('size')) is not int or not 0 < blob['size'] <= MAX_BYTES:
            raise ValueError('invalid source blob')
        second = base64.b64decode(''.join(blob['content'].split()), validate=True)
        if len(second) != blob['size'] or blob_id(second) != identity or first != second:
            raise ValueError('independent source readback differs')
        return first

    def tree(self, commit):
        require_pin(commit, '0' * 64)
        tree = self.read('/git/trees/' + commit + '?recursive=1')
        if tree.get('truncated') or not isinstance(tree.get('tree'), list) or len(tree['tree']) > 10000:
            raise ValueError('incomplete source tree')
        return tree['tree']


def ordinary(root, name):
    path = root / name
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError('expected ordinary pin source')
    return path.read_bytes()


def validate_payload(files):
    """Check all six slots and exact artifact relationships without execution."""
    bootstrap = files[BOOTSTRAP]
    if not 0 < len(bootstrap) <= 1024 * 1024:
        raise ValueError('bootstrap exceeds workflow download bound')
    vc, vd = pins(bootstrap, 'VERIFIER')
    require_pin(vc, vd)
    pairs = [pins(files[name], 'BOOTSTRAP') for name in WORKFLOWS]
    for bc, bd in pairs:
        require_pin(bc, bd)
        if blob_id(bootstrap) != bc or sha256(bootstrap) != bd:
            raise ValueError('bootstrap identity or digest differs from release bytes')
    if pairs[0] != pairs[1]:
        raise ValueError('workflow bootstrap pins differ')
    return (vc, vd), pairs[0]


def verify_files(files, published):
    verifier, bootstrap = validate_payload(files)
    for name, pair in ((VERIFIER, verifier), (BOOTSTRAP, bootstrap)):
        remote = published.blob(*pair)
        if blob_id(remote) != pair[0] or sha256(remote) != pair[1] or (name == BOOTSTRAP and remote != files[name]):
            raise ValueError('published pin target differs from candidate')
    return {'verifier': verifier, 'bootstrap': bootstrap}


def replace_pins(before, prefix, pair):
    if pins(before, prefix) not in (('UNSEALED', 'UNSEALED'), pair):
        raise ValueError('existing pins differ; owner must review an explicit reseal')
    text = before.decode('utf-8')
    for suffix, value in zip(('BLOB', 'SHA256'), pair):
        if prefix == 'VERIFIER':
            text = re.sub(r"(?m)^" + prefix + '_' + suffix + r" = '[^']+'$",
                          prefix + '_' + suffix + " = '" + value + "'", text)
        else:
            text = re.sub(r'(?m)^      ' + prefix + '_' + suffix + r': [^\s]+$',
                          '      ' + prefix + '_' + suffix + ': ' + value, text)
    return text.encode()


def check_local(files):
    verifier, bootstrap = validate_payload(files)
    if not 0 < len(files[VERIFIER]) <= MAX_BYTES:
        raise ValueError('verifier exceeds bootstrap download bound')
    if verifier != (blob_id(files[VERIFIER]), sha256(files[VERIFIER])):
        raise ValueError('first-release verifier differs from reviewed local file')
    return {'verifier': verifier, 'bootstrap': bootstrap}


def verify_source(files, published, commit):
    """First-release readback: exact W paths plus raw and JSON blob responses."""
    result = check_local(files)
    tree = published.tree(commit)
    for name in (VERIFIER, BOOTSTRAP, *WORKFLOWS):
        entries = [entry for entry in tree if entry.get('path') == name]
        if len(entries) != 1 or entries[0].get('mode') != '100644' or entries[0].get('type') != 'blob' or entries[0].get('sha') != blob_id(files[name]):
            raise ValueError('published source path differs: ' + name)
    verify_files(files, published)
    return dict(result, commit=commit)


def seal(root):
    root = Path(root).absolute()
    before = {name: ordinary(root, name) for name in (VERIFIER, BOOTSTRAP, *WORKFLOWS)}
    after = dict(before)
    verifier = (blob_id(before[VERIFIER]), sha256(before[VERIFIER]))
    after[BOOTSTRAP] = replace_pins(before[BOOTSTRAP], 'VERIFIER', verifier)
    bootstrap = (blob_id(after[BOOTSTRAP]), sha256(after[BOOTSTRAP]))
    for name in WORKFLOWS:
        after[name] = replace_pins(before[name], 'BOOTSTRAP', bootstrap)
    result = check_local(after)
    # Validate every block and source preimage before the first local write.
    for name in before:
        if ordinary(root, name) != before[name]:
            raise ValueError('pin preimage changed')
    for name in (BOOTSTRAP, *WORKFLOWS):
        if before[name] != after[name]:
            (root / name).write_bytes(after[name])
        if ordinary(root, name) != after[name]:
            raise ValueError('written pin readback differs; preserve files for reconciliation')
    return dict(result, files=[BOOTSTRAP, *WORKFLOWS], published=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('seal', 'check', 'verify'))
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--commit')
    args = parser.parse_args()
    if args.operation == 'seal':
        if args.commit:
            parser.error('offline seal does not take --commit')
        result = seal(args.source)
    else:
        files = {name: ordinary(args.source.absolute(), name) for name in (VERIFIER, BOOTSTRAP, *WORKFLOWS)}
        if args.operation == 'check':
            if args.commit:
                parser.error('offline check does not take --commit')
            result = check_local(files)
        else:
            if not args.commit:
                parser.error('published verify requires the full --commit of W')
            result = verify_source(files, PublishedSource(os.environ.get('GITHUB_TOKEN', '')), args.commit)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
