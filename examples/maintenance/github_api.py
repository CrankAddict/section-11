"""Bounded GitHub transport. Mutations are never automatically retried."""
import base64
import os
import re
from urllib.parse import quote

import requests

from distribution import Distribution, DistributionError


class APIError(RuntimeError):
    def __init__(self, status, message):
        self.status = status
        super().__init__(str(status) + ': ' + message)


class GitHub:
    def __init__(self, repo, token=None):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
            raise ValueError('invalid repository')
        self.repo = repo
        self.prefix = '/repos/' + repo
        self.token = token if token is not None else os.environ.get('GITHUB_TOKEN', '')

    def request(self, method, path, **kwargs):
        if not path.startswith(self.prefix + '/'):
            raise ValueError('cross-repository API path')
        headers = {'Accept': 'application/vnd.github+json'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        response = requests.request(method, Distribution.API + path, headers=headers,
                                    timeout=kwargs.pop('timeout', 60), allow_redirects=False, **kwargs)
        if not 200 <= response.status_code < 300:
            raise APIError(response.status_code, response.text[:2000])
        return response.json() if response.content else None

    def get(self, suffix, *, timeout=None):
        options = {} if timeout is None else {'timeout': timeout}
        return self.request('GET', self.prefix + suffix, **options)

    def write(self, method, suffix, body):
        return self.request(method, self.prefix + suffix, json=body)

    def metadata(self):
        # The bare repo endpoint is intentionally separate from suffix paths.
        headers = {'Accept': 'application/vnd.github+json'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        response = requests.get(Distribution.API + self.prefix, headers=headers,
                                timeout=60, allow_redirects=False)
        if response.status_code != 200:
            raise APIError(response.status_code, response.text[:2000])
        return response.json()

    def pages(self, suffix):
        result = []
        for page in range(1, 11):
            separator = '&' if '?' in suffix else '?'
            items = self.get(suffix + separator + 'per_page=100&page=' + str(page))
            if not isinstance(items, list):
                raise ValueError('invalid paginated response')
            result.extend(items)
            if len(items) < 100:
                return result
        raise ValueError('pagination bound exceeded; cannot prove complete discovery')

    def resolve_tag(self, tag):
        obj = self.get('/git/ref/tags/' + quote(tag, safe=''))['object']
        for _ in range(4):
            if obj['type'] == 'commit' and re.fullmatch('[0-9a-f]{40}', obj['sha']):
                return obj['sha']
            if obj['type'] != 'tag':
                break
            obj = self.get('/git/tags/' + obj['sha'])['object']
        raise ValueError('unresolved tag')

    def tree(self, commit):
        if not re.fullmatch('[0-9a-f]{40}', commit):
            raise ValueError('expected exact commit SHA')
        value = self.get('/git/trees/' + commit + '?recursive=1')
        if value.get('truncated'):
            raise ValueError('truncated Git tree')
        return {e['path']: e for e in value['tree'] if e['type'] != 'tree'}

    def blob(self, sha):
        value = self.get('/git/blobs/' + sha)
        if value.get('encoding') != 'base64' or value['size'] > Distribution.MAX_BYTES:
            raise ValueError('invalid/oversized Git blob')
        return base64.b64decode(value['content'])

    def asset(self, asset_id):
        response = requests.get(Distribution.API + self.prefix + '/releases/assets/' + str(int(asset_id)),
                                headers={'Accept': 'application/octet-stream',
                                         'Authorization': 'Bearer ' + self.token} if self.token else
                                        {'Accept': 'application/octet-stream'},
                                timeout=60, stream=True)
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > Distribution.MAX_BYTES:
                raise ValueError('asset exceeds limit')
            chunks.append(chunk)
        return b''.join(chunks)

    def release_metadata(self, tag=None):
        suffix = '/releases/tags/' + quote(tag, safe='') if tag else '/releases/latest'
        try:
            release = self.get(suffix)
        except APIError as exc:
            if exc.status == 404 and tag is None:
                raise ValueError('no published date release is available; verify the repository and first release') from exc
            raise
        if (release.get('draft') or release.get('prerelease') or
                (tag is not None and release['tag_name'] != tag)):
            raise ValueError('not the requested stable published release')
        tag = release['tag_name']
        Distribution.release_date(tag)
        return release

    def manifest_at(self, commit):
        entry = self.tree(commit)['manifest.json']
        if entry.get('mode') != '100644':
            raise ValueError('commit manifest is not an ordinary file')
        raw = self.blob(entry['sha'])
        Distribution.manifest(raw)
        return raw

    def release(self, tag=None):
        release = self.release_metadata(tag)
        tag = release['tag_name']
        commit = self.resolve_tag(tag)
        assets = [a for a in release['assets'] if a['name'] == 'section11-' + tag + '.zip']
        if len(assets) != 1:
            raise ValueError('canonical asset missing or ambiguous')
        raw, files = Distribution.archive(self.asset(assets[0]['id']))
        if self.manifest_at(commit) != raw:
            raise ValueError('commit manifest differs from asset')
        if self.resolve_tag(tag) != commit:
            raise ValueError('release tag moved')
        return raw, files, {'tag': tag, 'commit': commit, 'url': release['html_url'], 'repository': self.repo}
