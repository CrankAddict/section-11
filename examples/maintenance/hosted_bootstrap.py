"""Reviewed hosted entry. B3 seals this block before owner workflow publication."""
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import sys
import urllib.request

# B3 PIN BLOCK: Git blob identity and SHA256 of reviewed examples/sync.py bytes.
# Both values are computed offline; published availability is verified after push.
VERIFIER_BLOB = 'c6ba1df25b3f15fe36657048de1ca89641317748'
VERIFIER_SHA256 = 'a1f1943c4e8c9347769647574f7ff48ecca13c0f7b543227e30aa7f6ae034723'
UNSEALED_MESSAGE = 'Section 11 bootstrap is unsealed; wait for a verified published workflow.'


def require_pins(blob, digest):
    if (not re.fullmatch('[0-9a-f]{40}', blob) or
            not re.fullmatch('[0-9a-f]{64}', digest)):
        raise ValueError(UNSEALED_MESSAGE)


def pinned_verifier(stage, blob=VERIFIER_BLOB, digest=VERIFIER_SHA256, fetch=None, token=''):
    require_pins(blob, digest)  # Before mkdir, network, imports or publication.
    url = 'https://api.github.com/repos/CrankAddict/section-11/git/blobs/' + blob
    if fetch is None:
        if not token:
            raise ValueError('authenticated bootstrap source token missing')
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                raise ValueError('bootstrap source redirect refused')
        request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token,
            'Accept': 'application/vnd.github.raw+json', 'X-GitHub-Api-Version': '2022-11-28'})
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=10) as response:
            data = response.read(8 * 1024 * 1024 + 1)
    else:
        data = fetch(url)
    if len(data) > 8 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('bootstrap verifier digest mismatch; no code executed')
    if hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() != blob:
        raise ValueError('bootstrap verifier blob identity mismatch; no code executed')
    stage.mkdir(mode=0o700, parents=False, exist_ok=False)
    path = stage / 'trusted_sync.py'
    path.write_bytes(data)
    spec = importlib.util.spec_from_file_location('section11_trusted_bootstrap', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    require_pins(VERIFIER_BLOB, VERIFIER_SHA256)
    # Nothing from the data checkout is imported. Only this fixed official API
    # source read receives the job token; the verifier and producer do not.
    token = os.environ.pop('GITHUB_TOKEN', '')
    os.environ.pop('GH_TOKEN', None)
    temp = Path(os.environ['RUNNER_TEMP'])
    root = Path(os.environ['GITHUB_WORKSPACE'])
    if any(p.is_symlink() for p in (temp, *temp.parents)):
        raise ValueError('unsafe bootstrap staging')
    verifier = pinned_verifier(temp / 'section11-trusted-bootstrap', token=token)
    D = verifier.Distribution
    installed = verifier._known_local_identity(root / 'section11')
    installed_tag = installed['tag'] if installed else None
    control_path = root / '.section11-update.json'
    if installed_tag is None and control_path.is_file() and not control_path.is_symlink():
        if control_path.stat().st_size > 8192:
            raise ValueError('oversized update control record')
        state = D.json(control_path.read_bytes())
        installed_tag = state.get('installed_date') if isinstance(state, dict) else None
        if installed_tag is not None:
            D.release_date(installed_tag)
    with verifier._release_request_budget():
        # Authenticate controller code against the official installed date. These
        # trust reads are separate from latest-target maintenance discovery.
        raw, files, identity = D.fetch(installed_tag)
        if installed and (identity['commit'] != installed['commit'] or
                          D.digest(raw) != installed['manifest_sha256']):
            raise ValueError('installed controller provenance changed; owner recovery required')
        if 'examples/maintenance/hosted.py' not in files:
            raise ValueError('release lacks the hosted controller; B3 must publish a compatible verified release')
        source = temp / 'section11-trusted-source'
        source.mkdir(mode=0o700, exist_ok=False)
        for name, data in dict(files, **{'manifest.json': raw}).items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (source / D.RECEIPT).write_bytes(D.receipt(raw, identity))
        sys.path.insert(0, str(source / 'examples/maintenance'))
        spec = importlib.util.spec_from_file_location('section11_verified_hosted', source / 'examples/maintenance/hosted.py')
        controller = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(controller)
        os.environ['GITHUB_TOKEN'] = token
        controller.prepare(source, (raw, files, identity), verifier)


if __name__ == '__main__':
    try:
        main()
    except ValueError as exc:
        print(str(exc).splitlines()[0], file=sys.stderr)
        sys.exit(1)
