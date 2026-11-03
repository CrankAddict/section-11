"""
Tests for manifest-scoped --init installation and shared distribution fixtures.

Standard library only: unittest and unittest.mock, no third-party test packages,
no real athlete data, no network. Importing sync.py does require `requests`, its
normal runtime dependency, so these tests must run under the interpreter or
virtual environment that already runs sync.py.

Run from the repository root:

    python3 -m unittest discover dev/tests

Seams:
  * every archive is a synthetic zip built in memory, shaped like GitHub's
    (one top-level folder), and handed to do_init through a patched requests.get;
  * every installation lives in a TemporaryDirectory nested one level down, so a
    write that escaped the data directory would show up in the outer snapshot;
  * do_update receives a patched verified release and input() answers;
  * the Git-checkout test is replaced through sync.py's _is_git_checkout helper.
    No test creates a .git directory;
  * file types other than regular exist only as the mode an in-memory zip entry
    declares. No FIFO, device, socket or symlink is ever created.

Nothing here runs a real --init, --update, sync or cleanup against a user folder.
"""

import contextlib
import hashlib
import io
import json
import os
import stat
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest import mock

from _harness import (NetworkBlocked, SYNC_PATH, install_verb_guard,
                      load_module_by_path, restore_verb_guard)
from _local_timer_fakes import fake_timers

sync_mod = load_module_by_path("s11_sync_distribution", SYNC_PATH)
requests = sync_mod.requests

# Same verb seam as the other sync.py modules. Installed in setUpModule, never at
# import time, for the reason given in _harness.
_ORIGINAL_VERBS = {}


def setUpModule():
    global _ORIGINAL_VERBS
    _ORIGINAL_VERBS = install_verb_guard(requests)


def tearDownModule():
    restore_verb_guard(requests, _ORIGINAL_VERBS)


# ── fixtures ─────────────────────────────────────────────────────────────────

ROOT = "section-11-main"
BOOTSTRAP = b"# bootstrap copy of sync.py\n"

# What an athlete installation should hold. One path sits in a nested folder named
# dev, which must stay managed: only the repository-root dev/ is excluded.
MANAGED = {
    "README.md": b"readme\n",
    "SECTION_11.md": b"protocol\n",
    "examples/sync.py": b"# repository sync.py\n",
    "examples/maintenance/CUSTOM_README.md": (SYNC_PATH.parent / "maintenance/CUSTOM_README.md").read_bytes(),
    "examples/tools/dev/notes.md": b"nested dev folder, still managed\n",
}
# Present in a full repository archive, never installed.
UNLISTED = {
    ".github/workflows/pages.yml": b"workflow\n",
    ".github/site/build.cjs": b"site build\n",
    ".gitignore": b"__pycache__/\n",
    "dev/README.md": b"developer notes\n",
    "dev/tests/test_example.py": b"# maintainer test\n",
    "docs/.hidden": b"hidden file\n",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def manifest_for(files, scope="synthetic"):
    return {"scope": scope, "files": {path: {"hash": sha(data)} for path, data in files.items()}}


def manifest_bytes(manifest):
    return (json.dumps(manifest, indent=2) + "\n").encode("utf-8")


def build_zip(members):
    """members: list of (archive name, bytes) or (archive name, bytes, unix mode)."""
    buffer = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # the duplicate-member case is deliberate
        with zipfile.ZipFile(buffer, "w") as zf:
            for member in members:
                name, data = member[0], member[1]
                info = zipfile.ZipInfo(name)
                if len(member) == 3:
                    info.external_attr = member[2] << 16
                zf.writestr(info, data)
    return buffer.getvalue()


def repo_archive(manifest=None, files=None, extra=(), omit=(), root=ROOT, raw_manifest=None, modes=None):
    """A GitHub-shaped archive of the synthetic repository.

    modes maps a repository path to the Unix mode the archive declares for it. A
    path without one is written with no declared type at all (external_attr 0).
    """
    tree = dict(MANAGED if files is None else files)
    tree.update(UNLISTED)
    modes = modes or {}

    def member(path, data):
        return (f"{root}/{path}", data) + ((modes[path],) if path in modes else ())

    if raw_manifest is None and manifest is not False:
        raw_manifest = manifest_bytes(manifest_for(MANAGED) if manifest is None else manifest)
    members = [(f"{root}/", b"")]
    if raw_manifest is not None:
        members.append(member("manifest.json", raw_manifest))
    members += [member(path, data) for path, data in tree.items() if path not in omit]
    members += list(extra)
    return build_zip(members)


def snapshot(directory):
    """Every file under directory as {relative posix path: bytes}. Links are not followed."""
    found = {}
    for root, dirs, files in os.walk(directory):
        for name in files:
            path = Path(root) / name
            found[path.relative_to(directory).as_posix()] = path.read_bytes()
    return found


def write_tree(directory, files):
    for rel, data in files.items():
        path = Path(directory).joinpath(*rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


@contextlib.contextmanager
def working_directory(path):
    previous = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None


class InitResult:
    def __init__(self, files, output, get):
        self.files, self.output, self.get = files, output, get

    @property
    def installed(self):
        return {p[len("data/section11/"):]: d for p, d in self.files.items() if p.startswith("data/section11/")}


def run_init(archive=None, error=None, existing=None, bootstrap=True):
    """Run do_init in a fresh data directory and return what the outer directory then holds."""
    with tempfile.TemporaryDirectory() as outer:
        data_dir = Path(outer) / "data"
        data_dir.mkdir()
        if bootstrap:
            (data_dir / "sync.py").write_bytes(BOOTSTRAP)
        if existing is not None:
            write_tree(data_dir / "section11", existing)
        get = mock.Mock(side_effect=error) if error else mock.Mock(return_value=FakeResponse(archive))
        output = io.StringIO()
        def verified_release():
            response = get("https://example.invalid/pinned-release.zip", timeout=60)
            response.raise_for_status()
            raw, files = sync_mod.Distribution.archive(response.content, source_archive=True)
            return raw, files, {"commit": "a" * 40, "tag": "2026.10.23"}
        with working_directory(data_dir), mock.patch.object(sync_mod, "_fetch_verified_release", verified_release), \
                mock.patch.object(sync_mod, 'LocalTimers', fake_timers(sync_mod.LocalTimers)), \
                mock.patch('builtins.input', return_value='y'), \
                contextlib.redirect_stdout(output):
            sync_mod.do_init()
        return InitResult({p: b for p, b in snapshot(outer).items() if "/.section11-state/" not in p}, output.getvalue(), get)


# ── --init: the manifest decides ─────────────────────────────────────────────

class TestInitInstallsManifestFiles(unittest.TestCase):

    def test_installs_exactly_the_listed_files_plus_manifest(self):
        manifest = manifest_for(MANAGED)
        result = run_init(repo_archive(manifest))
        expected = dict(MANAGED)
        expected["manifest.json"] = manifest_bytes(manifest)
        expected[sync_mod.Distribution.RECEIPT] = sync_mod.Distribution.receipt(
            expected["manifest.json"], {"commit": "a" * 40, "tag": "2026.10.23"})
        self.assertEqual(result.installed, expected,
                         "--init must install the manifest's files and manifest.json, byte for byte, and nothing else")

    def test_unlisted_repository_content_is_not_installed(self):
        result = run_init(repo_archive())
        for path in UNLISTED:
            self.assertNotIn(path, result.installed, f"{path} is not manifest-managed and must not be installed")
        self.assertIn("examples/tools/dev/notes.md", result.installed,
                      "a nested folder named dev is managed; only the repository-root dev/ is excluded")

    def test_only_absent_custom_directory_is_initialized_outside_section11(self):
        result = run_init(repo_archive())
        outside = [p for p in result.files if not p.startswith("data/section11/")]
        self.assertEqual(outside, ["data/custom/README.md"])

    def test_unlisted_members_are_never_read_from_the_archive(self):
        read_names = []
        real_read = zipfile.ZipFile.read

        def recording_read(zf, name, *args, **kwargs):
            # The downloaded release uses BytesIO; recovery ZIPs use local paths.
            # Observe every release read, including any unlisted member.
            if zf.filename is None:
                read_names.append(name.filename if isinstance(name, zipfile.ZipInfo) else name)
            return real_read(zf, name, *args, **kwargs)

        with mock.patch.object(zipfile.ZipFile, "read", recording_read):
            run_init(repo_archive())
        self.assertEqual(sorted(read_names), sorted(f"{ROOT}/{p}" for p in list(MANAGED) + ["manifest.json"]),
                         "unlisted archive members must not even be read, so they cannot reach a staging folder")

    def test_one_archive_request_and_no_other_network_call(self):
        result = run_init(repo_archive())
        self.assertEqual(result.get.call_count, 1, "--init must not fetch the manifest or files separately")
        self.assertIn("pinned-release.zip", result.get.call_args.args[0])
        self.assertEqual(result.get.call_args.kwargs.get("timeout"), 60)

    def test_bootstrap_is_removed_after_a_verified_install(self):
        result = run_init(repo_archive())
        self.assertNotIn("data/sync.py", result.files)
        self.assertIn("Setup complete", result.output)

    def test_bootstrap_stays_when_the_manifest_does_not_install_sync_py(self):
        files = {p: d for p, d in MANAGED.items() if p != "examples/sync.py"}
        result = run_init(repo_archive(manifest_for(files), files=files))
        self.assertEqual(result.files.get("data/sync.py"), BOOTSTRAP,
                         "without an installed examples/sync.py the bootstrap is the only copy and must stay")

    def test_existing_section11_uses_the_same_accepted_installer(self):
        existing = {"README.md": b"my existing install\n", ".github/old.yml": b"old\n"}
        result = run_init(repo_archive(), existing=existing)
        self.assertEqual(result.installed['README.md'], MANAGED['README.md'])
        self.assertNotIn('.github/old.yml', result.installed)
        self.assertEqual(result.get.call_count, 1)
        self.assertNotIn('data/sync.py', result.files)
        self.assertIn(sync_mod.CONVERSION_WARNING, result.output)

    def test_download_failure_installs_nothing(self):
        result = run_init(error=requests.exceptions.ConnectionError("offline"))
        self.assertEqual(result.files, {"data/sync.py": BOOTSTRAP})
        self.assertIn("download failed", result.output)

    def test_unguarded_network_call_is_refused(self):
        with self.assertRaises(NetworkBlocked):
            requests.get("https://example.invalid/")


class TestInitRejectsInconsistentArchives(unittest.TestCase):
    """Every case must install nothing, write nothing elsewhere and keep the bootstrap."""

    def assert_nothing_installed(self, archive, label):
        result = run_init(archive)
        self.assertEqual(result.files, {"data/sync.py": BOOTSTRAP},
                         f"{label}: a rejected archive must leave only the bootstrap sync.py")
        self.assertNotIn("Setup complete", result.output, label)
        self.assertRegex(result.output, r"download failed or installation stopped", label)
        return result

    def test_missing_or_malformed_manifest(self):
        cases = {
            "manifest missing": repo_archive(manifest=False),
            "manifest not JSON": repo_archive(raw_manifest=b"{not json"),
            "manifest not UTF-8": repo_archive(raw_manifest=b"\xff\xfe\x00"),
            "manifest is a list": repo_archive(raw_manifest=b"[]"),
            "files missing": repo_archive(raw_manifest=b'{"scope": "x"}'),
            "files empty": repo_archive(manifest={"scope": "x", "files": {}}),
            "files is a list": repo_archive(manifest={"scope": "x", "files": ["README.md"]}),
            "entry is not an object": repo_archive(manifest={"files": {"README.md": sha(MANAGED["README.md"])}}),
            "hash missing": repo_archive(manifest={"files": {"README.md": {"description": "x"}}}),
            "hash too short": repo_archive(manifest={"files": {"README.md": {"hash": "abc123"}}}),
            "hash not hex": repo_archive(manifest={"files": {"README.md": {"hash": "z" * 64}}}),
            "hash upper case": repo_archive(manifest={"files": {"README.md": {"hash": sha(MANAGED["README.md"]).upper()}}}),
            "hash not a string": repo_archive(manifest={"files": {"README.md": {"hash": 5}}}),
        }
        for label, archive in cases.items():
            with self.subTest(label):
                self.assert_nothing_installed(archive, label)

    def test_unsafe_manifest_paths_write_nowhere(self):
        payload = b"escape attempt\n"
        unsafe = ["/abs.md", "../escape.md", "docs/../../escape.md", "docs\\file.md", "C:/file.md",
                  "C:file.md", "", ".", "..", "docs//file.md", "./file.md", "docs/./file.md",
                  "docs/", " lead.md", "trail.md ", "bad\nname.md", "manifest.json"]
        for path in unsafe:
            with self.subTest(path=path):
                manifest = manifest_for(MANAGED)
                manifest["files"][path] = {"hash": sha(payload)}
                # Offer the member wherever a naive join would look for it, so only
                # the path check stands between the manifest and a write.
                extra = [(f"{ROOT}/{path}", payload)] if path and not path.endswith("/") and path != "manifest.json" else []
                self.assert_nothing_installed(repo_archive(manifest, extra=extra), repr(path))

    def test_safe_path_predicate(self):
        for path in ["README.md", "examples/sync.py", "examples/tools/dev/notes.md", "a b/c d.md", "v1.2/file-name_x.md"]:
            self.assertTrue(sync_mod._safe_manifest_path(path), path)
        for path in [None, 5, "", "/a", "a/../b", "a\\b", "C:/a", "a/", "a//b", ".", "..", "a/.", " a", "a\x00b", "a\x7fb"]:
            self.assertFalse(sync_mod._safe_manifest_path(path), repr(path))

    def test_hash_mismatch_is_a_clear_failure(self):
        manifest = manifest_for(MANAGED)
        manifest["files"]["README.md"]["hash"] = sha(b"some other content\n")
        result = self.assert_nothing_installed(repo_archive(manifest), "hash mismatch")
        self.assertIn("hash mismatch for README.md", result.output,
                      "a stale or broken release must be named, not silently installed")

    def test_listed_file_missing_from_archive(self):
        result = self.assert_nothing_installed(repo_archive(omit=("SECTION_11.md",)), "missing member")
        self.assertIn("missing from the archive: SECTION_11.md", result.output)

    def test_listed_path_is_a_directory(self):
        manifest = manifest_for(MANAGED)
        manifest["files"]["examples"] = {"hash": sha(b"")}
        self.assert_nothing_installed(repo_archive(manifest, extra=[(f"{ROOT}/examples/", b"")]), "listed directory")

    def test_listed_path_is_a_symlink(self):
        files = dict(MANAGED)
        target = b"../../outside.txt"
        files["link.md"] = target
        archive = repo_archive(manifest_for(files), omit=("link.md",),
                               extra=[(f"{ROOT}/link.md", target, stat.S_IFLNK | 0o777)])
        result = self.assert_nothing_installed(archive, "symlink member")
        self.assertIn("not a regular file: link.md", result.output,
                      "a symlink entry must be refused even when its bytes match the manifest hash")

    # Every type the archive can declare other than a regular file. Each is only a
    # mode recorded in an in-memory zip entry; no special file is ever created.
    NON_REGULAR = {"directory": stat.S_IFDIR, "symlink": stat.S_IFLNK, "FIFO": stat.S_IFIFO,
                   "character device": stat.S_IFCHR, "block device": stat.S_IFBLK, "socket": stat.S_IFSOCK}

    def test_listed_member_declared_as_any_non_regular_type(self):
        for label, file_type in self.NON_REGULAR.items():
            with self.subTest(label):
                # The bytes match the manifest hash, so only the declared type can refuse it.
                archive = repo_archive(modes={"README.md": file_type | 0o644})
                result = self.assert_nothing_installed(archive, label)
                self.assertIn("not a regular file: README.md", result.output,
                              f"a listed member declared as a {label} must be refused")

    def test_manifest_declared_as_any_non_regular_type(self):
        for label, file_type in self.NON_REGULAR.items():
            with self.subTest(label):
                archive = repo_archive(modes={"manifest.json": file_type | 0o644})
                result = self.assert_nothing_installed(archive, label)
                self.assertIn("not a regular file: manifest.json", result.output,
                              f"manifest.json declared as a {label} must be refused before it is trusted")

    def test_declared_regular_files_are_installed(self):
        modes = {path: stat.S_IFREG | 0o644 for path in MANAGED}
        modes["examples/sync.py"] = stat.S_IFREG | 0o755
        modes["manifest.json"] = stat.S_IFREG | 0o644
        result = run_init(repo_archive(modes=modes))
        self.assertEqual(sorted(result.installed), sorted(list(MANAGED) + ["manifest.json", sync_mod.Distribution.RECEIPT]),
                         "entries declared as regular files, with any permission bits, are the normal case")

    def test_entries_without_a_declared_type_are_installed(self):
        archive = repo_archive()
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            declared = {info.filename: (info.external_attr >> 16) & 0o170000 for info in zf.infolist()}
        self.assertEqual(set(declared.values()), {0}, "this fixture must carry no declared file type at all")
        result = run_init(archive)
        self.assertEqual(sorted(result.installed), sorted(list(MANAGED) + ["manifest.json", sync_mod.Distribution.RECEIPT]),
                         "a zip whose creator recorded no Unix type holds ordinary files and must still install")

    def test_duplicate_archive_member(self):
        archive = repo_archive(extra=[(f"{ROOT}/README.md", MANAGED["README.md"])])
        result = self.assert_nothing_installed(archive, "duplicate member")
        self.assertIn("duplicate archive member", result.output)

    def test_ambiguous_or_missing_archive_root(self):
        good_manifest = manifest_bytes(manifest_for(MANAGED))
        cases = {
            "two top-level folders": repo_archive(extra=[("other-root/README.md", b"x")]),
            "file at the archive root": repo_archive(extra=[("stray.md", b"x")]),
            "no top-level folder": build_zip([("manifest.json", good_manifest)] + list(MANAGED.items())),
            "empty archive": build_zip([]),
            "not a zip": b"this is not a zip archive",
        }
        for label, archive in cases.items():
            with self.subTest(label):
                self.assert_nothing_installed(archive, label)

    def test_listed_paths_that_cannot_coexist(self):
        files = dict(MANAGED)
        files["README.md/inner.md"] = b"cannot live under a file\n"
        archive = repo_archive(manifest_for(files), files=MANAGED,
                               extra=[(f"{ROOT}/README.md/inner.md", files["README.md/inner.md"])])
        self.assert_nothing_installed(archive, "file used as a directory")


# ── manifest generator ───────────────────────────────────────────────────────

def run_generator(tree, existing_manifest=None):
    with tempfile.TemporaryDirectory() as directory:
        write_tree(directory, tree)
        if existing_manifest is not None:
            (Path(directory) / "manifest.json").write_bytes(manifest_bytes(existing_manifest))
        with working_directory(directory), contextlib.redirect_stdout(io.StringIO()):
            sync_mod.do_generate_manifest()
        return (Path(directory) / "manifest.json").read_bytes()


class TestGeneratorScope(unittest.TestCase):

    def full_tree(self):
        tree = dict(MANAGED)
        tree.update(UNLISTED)
        tree["node_modules/pkg/index.js"] = b"dependency\n"
        tree["examples/__pycache__/sync.cpython-312.pyc"] = b"cache\n"
        return tree

    def test_only_the_repository_root_dev_folder_is_excluded(self):
        manifest = json.loads(run_generator(self.full_tree()))
        self.assertEqual(sorted(manifest["files"]), sorted(MANAGED),
                         "root dev/, .github, hidden paths and dependency or cache folders are excluded; a nested dev folder is listed")
        self.assertEqual(manifest["files"]["README.md"]["hash"], sha(MANAGED["README.md"]))

    def test_scope_text_names_the_exclusions(self):
        scope = json.loads(run_generator(self.full_tree()))["scope"]
        self.assertEqual(scope, "Files installed by sync.py --init and managed by --update; excludes .github, hidden paths, "
                                "the repository-root dev folder, and generated dependency/cache directories.")

    def test_descriptions_are_preserved(self):
        previous = {"scope": "old", "files": {"README.md": {"hash": "0" * 64, "description": "Entry point"},
                                               "dev/README.md": {"hash": "0" * 64, "description": "Developer notes"}}}
        manifest = json.loads(run_generator(self.full_tree(), previous))
        self.assertEqual(manifest["files"]["README.md"].get("description"), "Entry point")
        self.assertNotIn("dev/README.md", manifest["files"])

    def test_init_installs_exactly_what_the_generator_lists(self):
        tree = self.full_tree()
        raw = run_generator(tree)
        members = [(f"{ROOT}/", b""), (f"{ROOT}/manifest.json", raw)]
        members += [(f"{ROOT}/{path}", data) for path, data in tree.items()]
        result = run_init(build_zip(members))
        self.assertEqual(sorted(result.installed), sorted(list(json.loads(raw)["files"]) + ["manifest.json", sync_mod.Distribution.RECEIPT]),
                         "a fresh install must hold exactly the generator's file list plus manifest.json")




class UpdateResult:
    def __init__(self, files, output, prompts):
        self.files, self.output, self.prompts = files, output, prompts


def run_update(files, answers, manifest=None, git_checkout=False, patches=(), release_files=None):
    """Run do_update on a synthetic installation for distribution/report tests."""
    with tempfile.TemporaryDirectory() as outer:
        data_dir = Path(outer) / "data"
        write_tree(data_dir, files)
        prompts = []
        queue = list(answers) if isinstance(answers, (list, tuple)) else None

        def fake_input(prompt=""):
            prompts.append(prompt)
            answer = queue.pop(0) if queue is not None else answers
            if isinstance(answer, type) and issubclass(answer, BaseException):
                raise answer()
            return answer

        output = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(sync_mod, 'LocalTimers', fake_timers(sync_mod.LocalTimers)))
            stack.enter_context(working_directory(data_dir))
            stack.enter_context(mock.patch.object(sync_mod, '__file__', str(data_dir / 'section11/examples/sync.py')))
            target_files = dict(MANAGED if release_files is None else release_files)
            target_manifest = manifest or manifest_for(target_files)
            for path in target_manifest["files"]:
                if path not in target_files and "section11/" + path in files:
                    target_files[path] = files["section11/" + path]
            stack.enter_context(mock.patch.object(sync_mod, "_fetch_verified_release",
                return_value=(manifest_bytes(target_manifest), target_files, {"commit": "a" * 40, "tag": "2026.10.23"})))
            stack.enter_context(mock.patch.object(sync_mod, "_is_git_checkout", return_value=git_checkout))
            stack.enter_context(mock.patch("builtins.input", fake_input))
            for patch in patches:
                stack.enter_context(patch)
            stack.enter_context(contextlib.redirect_stdout(output))
            sync_mod.do_update()
        return UpdateResult({p[len("data/"):]: d for p, d in snapshot(outer).items() if "/.section11-state/" not in p}, output.getvalue(), prompts)


if __name__ == "__main__":
    unittest.main()
