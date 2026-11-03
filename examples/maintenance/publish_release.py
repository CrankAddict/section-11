"""Pinned tag -> draft -> all assets -> readback -> publication, in one job."""
import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
from distribution import Distribution
from github_api import GitHub, APIError
from release_package import build, notes
from seal_pins import BOOTSTRAP, PublishedSource, verify_files


def workflow_gate(api, commit):
    metadata = api.metadata()
    branch = metadata['default_branch']
    current = api.get('/git/ref/heads/' + quote(branch, safe=''))['object']['sha']
    def active(sha):
        return {p: (v['mode'], v['sha']) for p, v in api.tree(sha).items()
                if p.startswith('.github/workflows/')}
    if active(current) != active(commit):
        raise ValueError('active workflows differ: target ' + commit + ', default ' + current +
                         '; no retarget or token escalation')
    return current


def by_tag(api, tag):
    try:
        release = api.get('/releases/tags/' + quote(tag, safe=''))
    except APIError as exc:
        if exc.status == 404:
            return None
        raise
    if release.get('tag_name') != tag or release.get('prerelease'):
        raise ValueError('release tag lookup returned a different identity')
    return release


def ensure_tag(api, tag, commit):
    try:
        existing = api.resolve_tag(tag)
    except APIError as exc:
        if exc.status != 404:
            raise
        try:
            api.write('POST', '/git/refs', {'ref': 'refs/tags/' + tag, 'sha': commit})
        except Exception:
            # Readback may prove an ambiguous write. Never retry the mutation.
            if api.resolve_tag(tag) != commit:
                raise
        existing = api.resolve_tag(tag)
    if existing != commit:
        raise ValueError('existing tag points elsewhere; never move it')


def upload(api, release, name, content):
    base = release['upload_url'].split('{', 1)[0]
    parsed = urlparse(base)
    expected_path = '/repos/' + api.repo + '/releases/' + str(release['id']) + '/assets'
    if parsed.scheme != 'https' or parsed.netloc != 'uploads.github.com' or parsed.path != expected_path:
        raise ValueError('unexpected release upload_url')
    media = 'application/zip' if name.endswith('.zip') else 'image/png' if name.endswith('.png') else 'text/plain'
    response = requests.post(base, params={'name': name}, data=content,
                             headers={'Authorization': 'Bearer ' + api.token, 'Content-Type': media},
                             timeout=60, allow_redirects=False)
    if response.status_code != 201:
        raise APIError(response.status_code, response.text[:2000])


def assets_readback(api, release_id, expected, allow_missing=False):
    actual = api.pages('/releases/' + str(release_id) + '/assets')
    names = [a['name'] for a in actual]
    if len(names) != len(set(names)) or set(names) - set(expected):
        raise ValueError('duplicate or unexpected release assets')
    verified = set()
    for asset in actual:
        name = asset['name']
        if asset.get('state') == 'starter' and asset.get('size') == 0 and allow_missing:
            continue
        if asset.get('size') != len(expected[name]) or api.asset(asset['id']) != expected[name]:
            raise ValueError('existing asset differs; never overwrite: ' + name)
        verified.add(name)
    if not allow_missing and verified != set(expected):
        raise ValueError('release assets incomplete')
    return actual, verified


def manifest_failure(api, commit, error):
    marker = '<!-- section11-release-manifest-failure -->'
    body = (marker + '\nRelease stopped at ' + commit + ': manifest does not match source.\n\n' +
            str(error) + '\n\nOwner: reconcile files and manifest through the supported workflow. '
            'No release was published; no automatic regeneration occurred.')
    matches = [i for i in api.pages('/issues?state=all') if not i.get('pull_request') and
               marker in (i.get('body') or '') and i['user']['login'] == 'github-actions[bot]']
    if len(matches) > 1:
        raise ValueError('ambiguous manifest failure issues; owner reconciliation required')
    if matches:
        issue = matches[0]
        if issue.get('body') != body or issue['state'] != 'open':
            api.write('PATCH', '/issues/' + str(issue['number']), {'body': body, 'state': 'open'})
        # Make a repeated failure visible without opening a duplicate issue.
        try:
            api.write('POST', '/issues/' + str(issue['number']) + '/comments',
                      {'body': 'Release stopped again at ' + commit + ': ' + str(error)})
        except Exception as exc:
            print('::warning::Could not comment on the manifest failure issue: ' + str(exc)[:300])
    else:
        try:
            issue = api.write('POST', '/issues', {'title': 'Section 11 release: manifest mismatch', 'body': body})
        except Exception:
            matches = [i for i in api.pages('/issues?state=all') if i.get('body') == body and
                       not i.get('pull_request') and i['user']['login'] == 'github-actions[bot]']
            if len(matches) != 1:
                raise RuntimeError('manifest issue denied/unknown; no retry')
            issue = matches[0]
    fresh = api.get('/issues/' + str(issue['number']))
    if fresh.get('body') != body or fresh.get('state') != 'open':
        raise RuntimeError('manifest issue readback differs')
    print('Manifest failure issue:', fresh['html_url'])


def publish(api, commit, raw, files, tag=None, resume=False):
    # Validate even when today's release exists or the last payload is unchanged.
    Distribution.verify(raw, files)
    tag = tag or Distribution.utc_tag()
    Distribution.release_date(tag)
    release = by_tag(api, tag)
    latest = None
    previous_raw = None
    try:
        latest_release = api.get('/releases/latest')
    except APIError as exc:
        if exc.status != 404:
            raise
    else:
        latest = latest_release['tag_name']
        Distribution.release_date(latest)
        if latest_release.get('draft') or latest_release.get('prerelease'):
            raise ValueError('latest release is not stable and published')
        previous_raw, _, _ = api.release(latest)
    # Unchanged content is a successful no-op even when today's release already
    # exists (for example after a same-day recovery dispatch). Only changed
    # content can trip the one-release-per-date rule.
    if previous_raw is not None and Distribution.content_hashes(previous_raw) == Distribution.content_hashes(raw):
        print('Manifest files unchanged; no release')
        return 'unchanged'
    if release is not None and (not resume or not release['draft']):
        raise ValueError('release ' + tag + ' already exists; second same-date release refused, no changes')
    if latest is not None and Distribution.release_date(latest) >= Distribution.release_date(tag):
        raise ValueError('release date does not follow latest published date: ' + latest)
    expected = build(raw, files, commit, tag)
    body = ('<!-- section11-release-v1 commit=' + commit + ' -->\nRelease date: ' + tag +
            ' (UTC)\n\n' + notes(files))
    workflow_gate(api, commit)
    ensure_tag(api, tag, commit)
    if release is None:
        try:
            release = api.write('POST', '/releases',
                                {'tag_name': tag, 'target_commitish': commit, 'name': tag,
                                 'body': body, 'draft': True, 'prerelease': False})
        except Exception:
            release = by_tag(api, tag)
            if release is None:
                raise RuntimeError('draft creation denied/unknown; no retry')
    if release['body'] != body or release.get('prerelease'):
        raise ValueError('existing release identity/notes differ')
    if not release['draft']:
        raise ValueError('release already published; second same-date release refused')
    for name, content in expected.items():
        actual, verified = assets_readback(api, release['id'], expected, allow_missing=True)
        if name in verified:
            continue
        starter = [a for a in actual if a['name'] == name and a.get('state') == 'starter' and a.get('size') == 0]
        if starter:
            # Only this draft's proven empty starter. Never delete a published
            # or unknown/nonempty object. Re-read draft state before deletion.
            fresh = api.get('/releases/' + str(release['id']))
            if not fresh['draft']:
                raise ValueError('release became published during recovery')
            api.write('DELETE', '/releases/assets/' + str(starter[0]['id']), None)
            if any(a['id'] == starter[0]['id'] for a in api.pages('/releases/' + str(release['id']) + '/assets')):
                raise RuntimeError('starter removal not confirmed')
        try:
            upload(api, release, name, content)
        except Exception:
            _, verified = assets_readback(api, release['id'], expected, allow_missing=True)
            if name not in verified:
                raise RuntimeError('asset upload failed/unknown; draft retained; no blind retry: ' + name)
    assets_readback(api, release['id'], expected)
    workflow_gate(api, commit)
    if api.resolve_tag(tag) != commit:
        raise ValueError('tag moved before publish')
    try:
        api.write('PATCH', '/releases/' + str(release['id']), {'draft': False, 'make_latest': 'true'})
    except Exception:
        fresh = api.get('/releases/' + str(release['id']))
        if fresh['draft']:
            raise RuntimeError('publication denied/unknown; no retry')
    fresh = api.get('/releases/' + str(release['id']))
    if fresh['draft'] or fresh['body'] != body or api.resolve_tag(tag) != commit:
        raise ValueError('publication readback differs')
    assets_readback(api, release['id'], expected)
    print('Published and read back all ' + str(len(expected)) + ' assets:', fresh['html_url'])
    return 'published'


def resolve_manifest_failure(api, commit):
    """Close the open manifest-failure issue once the manifest matches again. Best effort."""
    marker = '<!-- section11-release-manifest-failure -->'
    try:
        for issue in api.pages('/issues?state=open'):
            if issue.get('pull_request') or marker not in (issue.get('body') or '') or \
                    issue['user']['login'] != 'github-actions[bot]':
                continue
            api.write('POST', '/issues/' + str(issue['number']) + '/comments',
                      {'body': 'Resolved: manifest.json matches the source at ' + commit + '. Closing automatically.'})
            api.write('PATCH', '/issues/' + str(issue['number']), {'state': 'closed', 'state_reason': 'completed'})
            print('Closed manifest failure issue:', issue['html_url'])
    except Exception as exc:
        print('::warning::Could not close the manifest failure issue: ' + str(exc)[:300])


def release_source(api, source, commit):
    try:
        return Distribution.tree(source)
    except (ValueError, FileNotFoundError) as exc:
        print('Release refused: manifest mismatch:', exc)
        manifest_failure(api, commit, exc)
        raise


def pinned_source(api, source, commit, production=True, report_manifest_failure=False):
    """Default-owned code checks the selected source; imports no candidate code."""
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('exact source commit required')
    if subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() != commit:
        raise ValueError('checkout differs from pinned commit')
    if subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True).strip():
        raise ValueError('release source checkout is not clean')
    workflow_gate(api, commit)
    raw, files = (release_source(api, source, commit) if report_manifest_failure
                  else Distribution.tree(source))
    remote = api.tree(commit)
    for name, data in dict(files, **{'manifest.json': raw}).items():
        entry = remote.get(name, {})
        digest = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if entry.get('type') != 'blob' or entry.get('mode') != '100644' or entry.get('sha') != digest:
            raise ValueError('pinned source tree differs: ' + name)
    if production:
        if BOOTSTRAP not in files:
            raise ValueError('selected source lacks the compatible hosted bootstrap')
        verify_files(files, PublishedSource(api.token))
    return raw, files


def verify_published(api, commit, raw, files):
    """Read-only promotion gate: latest discovery, exact source and every asset."""
    latest = api.release_metadata()
    tag = latest['tag_name']
    actual_raw, actual_files, identity = api.release(tag)
    if identity['commit'] != commit or actual_raw != raw or actual_files != files:
        raise ValueError('published latest differs from the approved source; do not promote main')
    assets_readback(api, latest['id'], build(raw, files, commit, tag))
    if api.resolve_tag(tag) != commit or api.release_metadata()['id'] != latest['id']:
        raise ValueError('published identity changed during promotion readback')
    print('Promotion readback verified:', tag, commit)
    return tag


def verify_promotion(api, commit):
    """Accept a merge/squash tip only when its complete Git tree equals W."""
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('exact released source commit required')
    branch = api.metadata()['default_branch']
    ref = '/git/ref/heads/' + quote(branch, safe='')
    tip = api.get(ref)['object']['sha']
    if not re.fullmatch('[0-9a-f]{40}', tip):
        raise ValueError('invalid promoted main identity')
    def tree_id(sha):
        value = api.get('/git/commits/' + sha)['tree']['sha']
        if not re.fullmatch('[0-9a-f]{40}', value):
            raise ValueError('invalid complete Git tree identity')
        return value
    expected = tree_id(commit)
    if tree_id(tip) != expected:
        raise ValueError('promoted main tree differs from released source')
    if api.get(ref)['object']['sha'] != tip:
        raise ValueError('main changed during promotion readback')
    print('Promoted main tree verified:', tip, expected, '; release remains pinned to', commit)
    return tip


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=Path('.'))
    parser.add_argument('--commit', required=True)
    checks = parser.add_mutually_exclusive_group()
    checks.add_argument('--verify-only', action='store_true')
    checks.add_argument('--verify-published', action='store_true')
    checks.add_argument('--verify-promoted', action='store_true')
    args = parser.parse_args()
    api = GitHub(os.environ['GITHUB_REPOSITORY'])
    metadata = api.metadata()
    if os.environ.get('GITHUB_REF') != 'refs/heads/' + metadata['default_branch']:
        raise ValueError('release must run on default branch')
    if api.repo != Distribution.UPSTREAM:
        raise ValueError('production release must use the official source repository')
    raw, files = pinned_source(api, args.source, args.commit,
                              report_manifest_failure=not (args.verify_only or args.verify_published or args.verify_promoted))
    if args.verify_only:
        build(raw, files, args.commit, Distribution.utc_tag())
        print('Pinned source, matching active workflows, sealed pins and complete assets verified')
        return
    if args.verify_published or args.verify_promoted:
        verify_published(api, args.commit, raw, files)
        if args.verify_promoted:
            verify_promotion(api, args.commit)
        return
    resolve_manifest_failure(api, args.commit)
    publish(api, args.commit, raw, files,
            resume=int(os.environ.get('GITHUB_RUN_ATTEMPT', '1')) > 1)


if __name__ == '__main__':
    from distribution import run_cli
    run_cli(main)
