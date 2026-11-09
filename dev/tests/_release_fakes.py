"""In-memory GitHub boundary for offline release transaction tests."""
import copy
from urllib.parse import unquote

from test_update_prototype import github_api, release_package


class ReleaseAPI:
    repo = 'example-owner/private-test'
    token = 'synthetic-only'

    def __init__(self):
        self.tags = {}
        self.objects = {}
        self.releases = {}
        self.manifests = {}
        self.assets = {}
        self.latest = None
        self.calls = []
        self.writes = []
        self.fail = None
        self.latest_reads = []

    def seed(self, tag, commit, raw, files, draft=False, assets=False):
        self.tags[tag] = commit
        self.manifests[commit] = raw
        release = self.new_release(tag, commit, files, draft)
        self.releases[tag] = release
        if not draft:
            self.latest = tag
        if assets:
            for name, data in release_package.build(raw, files, commit, tag).items():
                self.store_asset(release['id'], name, data)
        return release

    def new_release(self, tag, commit, files, draft):
        return dict(id=len(self.releases) + 1, tag_name=tag, draft=draft, prerelease=False,
                    published_at=None if draft else '2026-11-09T12:00:00Z', html_url='fixture/' + tag,
                    upload_url='unused', body='<!-- section11-release-v1 commit=' + commit +
                    ' -->\nRelease date: ' + tag + ' (UTC)\n\n' + release_package.notes(files))

    def get(self, path, **kwargs):
        self.calls.append(('GET', path, kwargs))
        if path.startswith('/git/ref/tags/'):
            name = path[len('/git/ref/tags/'):]
            if name in self.tags:
                sha = self.tags[name]
                return {'object': {'type': 'tag' if sha in self.objects else 'commit', 'sha': sha}}
        elif path.startswith('/git/tags/'):
            sha = path[len('/git/tags/'):]
            if sha in self.objects:
                return copy.deepcopy(self.objects[sha])
        elif path == '/releases/latest':
            if self.latest_reads:
                value = self.latest_reads.pop(0)
                if isinstance(value, Exception):
                    raise value
                return copy.deepcopy(value)
            if self.latest is not None:
                return copy.deepcopy(self.releases[self.latest])
        elif path == '/releases?per_page=100&page=1':
            return copy.deepcopy(sorted(self.releases.values(), key=lambda r: r['id'], reverse=True)[:100])
        elif path.startswith('/git/matching-refs/tags/') and path.endswith('?per_page=100&page=1'):
            prefix = path[len('/git/matching-refs/tags/'):].split('?', 1)[0]
            return [{'ref': 'refs/tags/' + t} for t in self.tags if t.startswith(prefix)][:100]
        elif path.startswith('/releases/tags/'):
            tag = unquote(path[len('/releases/tags/'):])
            if tag in self.releases:
                return copy.deepcopy(self.releases[tag])
        elif path.startswith('/releases/'):
            for release in self.releases.values():
                if path == '/releases/' + str(release['id']):
                    return copy.deepcopy(release)
        raise github_api.APIError(404, 'synthetic missing object')

    def pages(self, path):
        self.calls.append(('PAGES', path))
        for release in self.releases.values():
            if path == '/releases/' + str(release['id']) + '/assets':
                return [dict(id=i, name=a['name'], size=len(a['data']), state=a['state'])
                        for i, a in self.assets.items() if a['release'] == release['id']]
        raise AssertionError(path)

    def resolve_tag(self, tag):
        self.calls.append(('TAG', tag))
        return github_api.GitHub.resolve_tag(self, tag)

    def manifest_at(self, commit):
        self.calls.append(('MANIFEST', commit))
        if commit not in self.manifests:
            raise github_api.APIError(404, 'synthetic missing source')
        return self.manifests[commit]

    def asset(self, asset_id):
        self.calls.append(('ASSET', asset_id))
        return self.assets[asset_id]['data']

    def release(self, tag):
        raise AssertionError('publisher downloaded previous release ZIP')

    def write(self, method, path, body):
        self.writes.append((method, path, copy.deepcopy(body)))
        if self.fail == (method, path, 'before'):
            raise RuntimeError('synthetic lost write reply')
        result = None
        if path == '/git/refs':
            tag = body['ref'][len('refs/tags/'):]
            if tag in self.tags:
                raise github_api.APIError(422, 'tag exists')
            self.tags[tag] = body['sha']
        elif path == '/releases' and method == 'POST':
            if body['tag_name'] in self.releases:
                raise github_api.APIError(422, 'release exists')
            result = dict(body, id=len(self.releases) + 1, html_url='fixture', upload_url='unused', published_at=None)
            self.releases[body['tag_name']] = result
        elif method == 'DELETE':
            del self.assets[int(path.rsplit('/', 1)[1])]
        elif method == 'PATCH':
            result = next(r for r in self.releases.values() if path == '/releases/' + str(r['id']))
            result.update(body)
            if body.get('draft') is False:
                result['published_at'] = '2026-11-09T12:00:00Z'
                self.latest = result['tag_name']
        else:
            raise AssertionError((method, path))
        if self.fail == (method, path, 'after'):
            raise RuntimeError('synthetic lost write reply')
        return copy.deepcopy(result)

    def store_asset(self, release_id, name, data, state='uploaded'):
        number = max(self.assets, default=0) + 1
        self.assets[number] = dict(release=release_id, name=name, data=data, state=state)
        return number

    def upload(self, api, release, name, content):
        assert api is self
        self.writes.append(('UPLOAD', name, content))
        if self.fail == ('UPLOAD', name, 'before'):
            raise RuntimeError('synthetic upload failure')
        self.store_asset(release['id'], name, content)
        if self.fail == ('UPLOAD', name, 'after'):
            raise RuntimeError('synthetic lost upload reply')
