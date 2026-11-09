"""Pinned tag -> draft -> all assets -> readback -> publication, in one job."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import timedelta
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
        except Exception as exc:
            # The caller reads the state and stops, even if the write landed.
            raise RuntimeError('tag creation failed/unknown; no retry') from exc
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


def release_inventory(api, commit, day):
    """Latest, one release page and two date prefixes; never walk history."""
    clock = Distribution.calendar_day(day)
    releases, commits = {}, {}
    try:
        pointer = api.get('/releases/latest')
    except APIError as exc:
        if exc.status != 404:
            raise
        pointer = None
    if pointer is not None:
        key = Distribution.release_key(pointer['tag_name'])
        if (pointer.get('draft') is not False or pointer.get('prerelease') is not False or
                type(pointer.get('id')) is not int or not pointer.get('published_at')):
            raise ValueError('latest is not a stable published release; owner recovery required')
        if key[0] > clock:
            raise ValueError('latest date is ahead of the UTC release clock; owner recovery required')
    page = api.get('/releases?per_page=100&page=1')
    if not isinstance(page, list) or len(page) > 100:
        raise ValueError('invalid first release page; owner recovery required')
    for release in page:
        tag = release['tag_name']
        if not re.match(r'^[0-9]{4}\.', tag):
            continue  # Historical protocol-version tags are not date releases.
        Distribution.release_key(tag)
        if (tag in releases or release.get('prerelease') is not False or
                type(release.get('draft')) is not bool or type(release.get('id')) is not int):
            raise ValueError('ambiguous or non-stable release collision: ' + tag)
        releases[tag] = release
    latest = pointer['tag_name'] if pointer is not None else None
    if latest is None:
        if any(not r['draft'] for r in releases.values()):
            raise ValueError('published releases exist but latest is unavailable; next dispatch rechecks discovery')
    else:
        listed = releases.get(latest)
        if listed is not None and (listed['id'] != pointer['id'] or listed['draft']):
            raise ValueError('latest pointer and release inventory differ; owner recovery required')
        releases[latest] = pointer
        commits[latest] = api.resolve_tag(latest)

    def check_draft(release):
        tag = release['tag_name']
        match = re.match(r'<!-- section11-release-v1 commit=([0-9a-f]{40}) -->\n', release.get('body') or '')
        if match is None:
            raise ValueError('draft source is unknown: ' + tag + '; owner recovery required')
        source = match[1]
        if source != commit:
            raise ValueError('draft collision: ' + tag + ' belongs to source ' + source +
                             '; dispatch that exact source to resume it before a different release')
        if tag not in commits:
            commits[tag] = api.resolve_tag(tag)
        if commits[tag] != source:
            raise ValueError('draft/tag collision: ' + tag + ' body source ' + source +
                             ', tag source ' + commits[tag] + '; owner recovery required')

    for release in page:
        if release.get('draft') and release['tag_name'] in releases:
            check_draft(release)
    for date in (clock, clock - timedelta(days=1)):
        prefix = date.strftime('%Y.%m.%d')
        refs = api.get('/git/matching-refs/tags/' + prefix + '?per_page=100&page=1')
        # A full page cannot establish the next number. Stop, never paginate.
        if not isinstance(refs, list) or len(refs) >= 100:
            raise ValueError('date tag discovery limit reached for ' + prefix + '; owner recovery required')
        seen = set()
        for ref in refs:
            name = ref['ref']
            if not name.startswith('refs/tags/' + prefix):
                raise ValueError('unexpected date tag inventory ref')
            tag = name[len('refs/tags/'):]
            if Distribution.release_key(tag)[0] != date or tag in seen:
                raise ValueError('duplicate or unexpected date tag collision: ' + tag)
            seen.add(tag)
            if tag not in commits:
                commits[tag] = api.resolve_tag(tag)
            release = releases.get(tag)
            if release is None:
                release = by_tag(api, tag)
                if release is not None:
                    releases[tag] = release
            if release is not None and release['draft']:
                check_draft(release)
            elif release is None and commits[tag] != commit:
                raise ValueError('unpublished tag collision: ' + tag + ' belongs to source ' + commits[tag] +
                                 '; dispatch that exact source to resume it before a different release')
    return latest, releases, commits


def source_manifest(api, tag, commit):
    if api.resolve_tag(tag) != commit:
        raise ValueError('release tag moved before source read: ' + tag)
    raw = api.manifest_at(commit)
    Distribution.content_hashes(raw)
    if api.resolve_tag(tag) != commit:
        raise ValueError('release tag moved during source read: ' + tag)
    return raw


def confirm_latest(api, release):
    """Read-only visibility wait: at most ten GETs within a 30-second budget."""
    start = time.monotonic()
    observed = 'not read'
    for attempt in range(10):
        remaining = 30 - (time.monotonic() - start)
        if remaining <= 0:
            break
        try:
            latest = api.get('/releases/latest', timeout=min(3, remaining))
        except APIError as exc:
            if exc.status != 404:
                raise
            observed = '404'
        else:
            observed = str(latest.get('id')) + '/' + str(latest.get('tag_name'))
            if (latest.get('id') == release['id'] and latest.get('tag_name') == release['tag_name']
                    and latest.get('draft') is False and latest.get('prerelease') is False
                    and latest.get('published_at')):
                print('Latest confirmed:', observed, 'after', round(time.monotonic() - start, 3), 's')
                return
        print('Latest readback', attempt + 1, ':', observed,
              'after', round(time.monotonic() - start, 3), 's')
        remaining = 30 - (time.monotonic() - start)
        if attempt < 9 and remaining > 0:
            time.sleep(min(3, remaining))
    raise RuntimeError('published release is not confirmed latest (observed ' + observed +
                       '); next dispatch only rechecks it when content is unchanged; '
                       'no re-publication, asset change or latest write; owner recovery if it persists')


def stopped_state(api, tag, commit):
    """Report observed remote state without converting readback into more writes."""
    if tag is None:
        return ('Release discovery/preflight stopped before release writes. Next dispatch repeats '
                'discovery; resolve the reported source/collision first.')
    observations = []
    try:
        observations.append('tag=' + api.resolve_tag(tag))
    except Exception as exc:
        observations.append('tag unconfirmed (' + str(exc)[:200] + ')')
    try:
        release = by_tag(api, tag)
        observations.append('release absent' if release is None else
                            'release ' + str(release['id']) + (' draft' if release['draft'] else ' published'))
    except Exception as exc:
        observations.append('release unconfirmed (' + str(exc)[:200] + ')')
    return ('GitHub readback for ' + tag + ': ' + '; '.join(observations) +
            '. Stop here. Next dispatch with source ' + commit +
            ' checks the first releases page and today/previous UTC day tags to resume a visible identity; '
            'a published identity only gets read-only confirmation, never replacement assets. '
            'An older or still-invisible unfinished tag/draft needs owner review before another dispatch.')


def publish(api, commit, raw, files, tag=None, resume=False):
    # The optional tag argument is the frozen UTC day, not an identity override.
    # Recovery is discovered from immutable source identity, not run_attempt.
    transaction = {'tag': None}
    try:
        return publish_transaction(api, commit, raw, files, tag or Distribution.utc_tag(), transaction)
    except Exception:
        print(stopped_state(api, transaction['tag'], commit))
        raise


def publish_transaction(api, commit, raw, files, day, transaction):
    Distribution.verify(raw, files)
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('exact source commit required')
    clock = Distribution.calendar_day(day)
    latest, releases, commits = release_inventory(api, commit, day)
    if any(Distribution.release_date(t) > clock for t in commits):
        raise ValueError('release date is ahead of the UTC release clock; owner recovery required')
    published = [t for t, r in releases.items() if not r['draft']]
    pending = set(commits) - set(published)
    matching = [t for t, sha in commits.items() if sha == commit]
    if len(matching) > 1 or pending - set(matching):
        raise ValueError('unexplained draft/tag collision; resume its exact source before a new release')
    tag = matching[0] if matching else None
    if tag:
        transaction['tag'] = tag
        existing_raw = source_manifest(api, tag, commit)
        if existing_raw != raw:
            raise ValueError('same complete tag has a different manifest; never replace it')
    if latest and any(Distribution.release_key(t) > Distribution.release_key(latest)
                      for t in published if t != tag):
        raise ValueError('published release is newer than latest; next dispatch rechecks the pointer; '
                         'owner recovery if it persists')
    if tag in published and (latest is None or Distribution.release_key(tag) >= Distribution.release_key(latest)):
        confirm_latest(api, releases[tag])
        if api.resolve_tag(tag) != commit:
            raise ValueError('release tag moved during latest confirmation')
        print('Source already published; no release or asset changes.')
        return 'unchanged'
    previous_raw = source_manifest(api, latest, commits[latest]) if latest else None
    if (previous_raw is not None and
            Distribution.content_hashes(previous_raw) == Distribution.content_hashes(raw)):
        # Source identity, not the previous ZIP, decides no-op. Existing asset
        # damage still needs owner recovery and cannot authorize replacement.
        confirm_latest(api, releases[latest])
        if api.resolve_tag(latest) != commits[latest]:
            raise ValueError('release tag moved during latest confirmation')
        print('Manifest files unchanged; no release. Previous assets were not checked or changed.')
        if pending:
            print('Existing tag/draft retained; resolve it before dispatching a different source.')
        return 'unchanged'
    if tag is None:
        today = [Distribution.release_key(t)[1] for t in commits if Distribution.release_date(t) == clock]
        sequence = max(today, default=0) + 1
        tag = day if sequence == 1 else day + '-' + str(sequence)
        Distribution.release_key(tag)
        transaction['tag'] = tag
    release = by_tag(api, tag)
    if (release is not None and tag not in releases) or (tag in releases and
            (release is None or release['id'] != releases[tag]['id'])):
        raise ValueError('release inventory changed; collision requires owner review')
    if latest and Distribution.release_key(latest) >= Distribution.release_key(tag):
        raise ValueError('release identity does not follow latest published identity: ' + latest)
    expected = build(raw, files, commit, tag)
    body = ('<!-- section11-release-v1 commit=' + commit + ' -->\nRelease date: ' + tag +
            ' (UTC)\n\n' + notes(files))
    if release is not None:
        if release['body'] != body or not release['draft']:
            raise ValueError('existing release identity/notes or draft state differ; no changes')
        assets_readback(api, release['id'], expected, allow_missing=True)
    workflow_gate(api, commit)
    ensure_tag(api, tag, commit)
    if release is None:
        try:
            release = api.write('POST', '/releases',
                                {'tag_name': tag, 'target_commitish': commit, 'name': tag,
                                 'body': body, 'draft': True, 'prerelease': False})
        except Exception as exc:
            raise RuntimeError('draft creation failed/unknown; no retry') from exc
    if release['body'] != body or release.get('prerelease'):
        raise ValueError('existing release identity/notes differ')
    if not release['draft']:
        raise ValueError('release already published; no re-publication or asset changes')
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
        except Exception as exc:
            # Readback can diagnose accepted bytes, but never authorizes this
            # run to continue to another write after an uncertain upload.
            assets_readback(api, release['id'], expected, allow_missing=True)
            raise RuntimeError('asset upload failed/unknown; draft retained; no blind retry: ' + name) from exc
    assets_readback(api, release['id'], expected)
    workflow_gate(api, commit)
    if api.resolve_tag(tag) != commit:
        raise ValueError('tag moved before publish')
    try:
        api.write('PATCH', '/releases/' + str(release['id']), {'draft': False, 'make_latest': 'true'})
    except Exception as exc:
        raise RuntimeError('publication failed/unknown; no retry') from exc
    fresh = api.get('/releases/' + str(release['id']))
    if (fresh['draft'] or fresh.get('prerelease') or fresh['body'] != body or
            fresh['tag_name'] != tag or fresh['id'] != release['id'] or api.resolve_tag(tag) != commit):
        raise ValueError('publication readback differs')
    assets_readback(api, release['id'], expected)
    confirm_latest(api, fresh)
    if api.resolve_tag(tag) != commit:
        raise ValueError('release tag moved during latest confirmation')
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
    publish(api, args.commit, raw, files)


if __name__ == '__main__':
    from distribution import run_cli
    run_cli(main)
