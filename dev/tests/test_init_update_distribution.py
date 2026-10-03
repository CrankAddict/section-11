"""
Tests for what --init installs and how --update treats folders it does not manage.

Origin: written for sync.py v3.138, which makes --init install exactly the files
the archive's own manifest.json lists, drops the repository-root dev/ folder from
the manifest, and offers a recoverable move for .github and dev/ left in
section11/ by an older --init. Behaviour is validated against the current sync.py.

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
  * do_update gets its manifest from a patched _fetch_upstream_manifest and its
    answers from a patched input(), which is how Enter, y, EOF and Ctrl+C are
    told apart;
  * whether standard input is a terminal is stated through sync.py's
    _stdin_is_interactive helper: True for a person at a terminal, False for a
    yes pipe or redirected input. No terminal is created;
  * the Git-checkout test is replaced through sync.py's _is_git_checkout helper,
    and a symlinked folder through Path.is_symlink. No test creates a .git
    directory or a real symlink;
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
        with working_directory(data_dir), mock.patch.object(requests, "get", get), \
                contextlib.redirect_stdout(output):
            sync_mod.do_init()
        return InitResult(snapshot(outer), output.getvalue(), get)


# ── --init: the manifest decides ─────────────────────────────────────────────

class TestInitInstallsManifestFiles(unittest.TestCase):

    def test_installs_exactly_the_listed_files_plus_manifest(self):
        manifest = manifest_for(MANAGED)
        result = run_init(repo_archive(manifest))
        expected = dict(MANAGED)
        expected["manifest.json"] = manifest_bytes(manifest)
        self.assertEqual(result.installed, expected,
                         "--init must install the manifest's files and manifest.json, byte for byte, and nothing else")

    def test_unlisted_repository_content_is_not_installed(self):
        result = run_init(repo_archive())
        for path in UNLISTED:
            self.assertNotIn(path, result.installed, f"{path} is not manifest-managed and must not be installed")
        self.assertIn("examples/tools/dev/notes.md", result.installed,
                      "a nested folder named dev is managed; only the repository-root dev/ is excluded")

    def test_nothing_is_written_outside_section11(self):
        result = run_init(repo_archive())
        outside = [p for p in result.files if not p.startswith("data/section11/")]
        self.assertEqual(outside, [], "a successful --init removes the bootstrap and writes nowhere else")

    def test_unlisted_members_are_never_read_from_the_archive(self):
        read_names = []
        real_read = zipfile.ZipFile.read

        def recording_read(zf, name, *args, **kwargs):
            read_names.append(name.filename if isinstance(name, zipfile.ZipInfo) else name)
            return real_read(zf, name, *args, **kwargs)

        with mock.patch.object(zipfile.ZipFile, "read", recording_read):
            run_init(repo_archive())
        self.assertEqual(sorted(read_names), sorted(f"{ROOT}/{p}" for p in list(MANAGED) + ["manifest.json"]),
                         "unlisted archive members must not even be read, so they cannot reach a staging folder")

    def test_one_archive_request_and_no_other_network_call(self):
        result = run_init(repo_archive())
        self.assertEqual(result.get.call_count, 1, "--init must not fetch the manifest or files separately")
        self.assertIn("archive/refs/heads/main.zip", result.get.call_args.args[0])
        self.assertEqual(result.get.call_args.kwargs.get("timeout"), 60)

    def test_bootstrap_is_removed_only_after_a_verified_install(self):
        result = run_init(repo_archive())
        self.assertNotIn("data/sync.py", result.files)
        self.assertIn("Setup complete", result.output)

    def test_bootstrap_stays_when_the_manifest_does_not_install_sync_py(self):
        files = {p: d for p, d in MANAGED.items() if p != "examples/sync.py"}
        result = run_init(repo_archive(manifest_for(files), files=files))
        self.assertEqual(result.files.get("data/sync.py"), BOOTSTRAP,
                         "without an installed examples/sync.py the bootstrap is the only copy and must stay")

    def test_existing_section11_is_left_alone_without_a_download(self):
        existing = {"README.md": b"my existing install\n", ".github/old.yml": b"old\n"}
        result = run_init(repo_archive(), existing=existing)
        self.assertEqual(result.installed, existing, "an existing section11/ must never be overwritten")
        self.assertEqual(result.get.call_count, 0)
        self.assertEqual(result.files.get("data/sync.py"), BOOTSTRAP)

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
        self.assertRegex(result.output, r"failed verification|extraction failed", label)
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
        self.assertEqual(sorted(result.installed), sorted(list(MANAGED) + ["manifest.json"]),
                         "entries declared as regular files, with any permission bits, are the normal case")

    def test_entries_without_a_declared_type_are_installed(self):
        archive = repo_archive()
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            declared = {info.filename: (info.external_attr >> 16) & 0o170000 for info in zf.infolist()}
        self.assertEqual(set(declared.values()), {0}, "this fixture must carry no declared file type at all")
        result = run_init(archive)
        self.assertEqual(sorted(result.installed), sorted(list(MANAGED) + ["manifest.json"]),
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
        self.assertEqual(sorted(result.installed), sorted(list(json.loads(raw)["files"]) + ["manifest.json"]),
                         "a fresh install must hold exactly the generator's file list plus manifest.json")


# ── --update on an installation left by an older --init ──────────────────────

GITHUB = {
    "section11/.github/workflows/pages.yml": b"old workflow\n",
    "section11/.github/site/build.cjs": b"old site build\n",
    "section11/.github/notes-i-added.txt": b"a file the user added\n",
}
DEV = {
    "section11/dev/README.md": b"developer notes, edited locally\n",
    "section11/dev/tests/test_example.py": b"# old maintainer test\n",
}
OTHER = {
    "section11/.gitignore": b"__pycache__/\n",
    "section11/.cache/state.bin": b"\x00\x01",
    "latest.json": b'{"synthetic": true}\n',
    "DOSSIER.md": b"private\n",
    ".sync_config.json": b"{}\n",
}
ORPHAN = {"section11/old-guide.md": b"removed upstream\n"}


def legacy_install(extra=None, github=True, dev=True):
    files = {f"section11/{path}": data for path, data in MANAGED.items()}
    files["section11/manifest.json"] = manifest_bytes(manifest_for(MANAGED))
    files.update(OTHER)
    if github:
        files.update(GITHUB)
    if dev:
        files.update(DEV)
    files.update(extra or {})
    return files


class UpdateResult:
    def __init__(self, files, output, prompts):
        self.files, self.output, self.prompts = files, output, prompts


def run_update(files, answers, manifest=None, git_checkout=False, patches=(), interactive=True):
    """Run do_update on a synthetic installation whose managed files are already current.

    interactive states what sync.py's _stdin_is_interactive reports, so a terminal
    session and piped or redirected input are both simulated without a terminal.
    """
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
            stack.enter_context(working_directory(data_dir))
            stack.enter_context(mock.patch.object(sync_mod, "_fetch_upstream_manifest",
                                                  return_value=manifest or manifest_for(MANAGED)))
            stack.enter_context(mock.patch.object(sync_mod, "_is_git_checkout", return_value=git_checkout))
            stack.enter_context(mock.patch.object(sync_mod, "_stdin_is_interactive", return_value=interactive))
            stack.enter_context(mock.patch("builtins.input", fake_input))
            for patch in patches:
                stack.enter_context(patch)
            stack.enter_context(contextlib.redirect_stdout(output))
            sync_mod.do_update()
        return UpdateResult({p[len("data/"):]: d for p, d in snapshot(outer).items()}, output.getvalue(), prompts)


def moved(files, source_prefix, backup_name):
    """The files under source_prefix as they should appear inside backup_name."""
    return {backup_name + path[len(source_prefix):]: data for path, data in files.items()
            if path.startswith(source_prefix + "/")}


class TestLegacyMoveConsent(unittest.TestCase):

    def test_typed_move_relocates_both_folders_byte_for_byte(self):
        before = legacy_install()
        result = run_update(before, ["move"])
        expected = {p: d for p, d in before.items() if p not in GITHUB and p not in DEV}
        expected.update(moved(GITHUB, "section11/.github", "section11-legacy-github"))
        expected.update(moved(DEV, "section11/dev", "section11-legacy-dev"))
        self.assertEqual(result.files, expected,
                         "move must relocate complete folders, including added and edited files, and touch nothing else")
        self.assertEqual(len(result.prompts), 1)

    def test_move_is_case_and_whitespace_tolerant(self):
        result = run_update(legacy_install(), ["  MoVe \n"])
        self.assertNotIn("section11/dev/README.md", result.files)
        self.assertIn("section11-legacy-dev/README.md", result.files)

    def test_anything_but_the_typed_word_keeps_everything(self):
        before = legacy_install()
        for answer in ["", "y", "yes", "Y", "n", "remove", "delete", "mv", "move it", "moved"]:
            with self.subTest(answer=answer):
                result = run_update(before, [answer])
                self.assertEqual(result.files, before, f"{answer!r} is not consent to move anything")
                self.assertIn("Kept.", result.output)

    def test_y_at_every_prompt_in_a_terminal_keeps_legacy_folders(self):
        before = legacy_install()
        result = run_update(before, "y")  # a person answering y to everything
        self.assertEqual(result.files, before, "y is not the typed word, so nothing moves and nothing is deleted")
        self.assertEqual(len(result.prompts), 1, "with dev protected there is nothing left for the orphan prompt")

    def test_yes_pipe_is_never_asked_and_keeps_legacy_folders(self):
        before = legacy_install()
        result = run_update(before, "y", interactive=False)  # `yes | sync.py --update`
        self.assertEqual(result.files, before, "a yes pipe must neither move nor delete .github or dev")
        self.assertEqual(result.prompts, [], "piped input must not be read for the move question")
        self.assertIn("Kept section11/.github/, section11/dev/", result.output)

    def test_piped_input_containing_move_does_not_move_anything(self):
        # The word is available on standard input, but standard input is not a terminal.
        before = legacy_install(extra=ORPHAN)
        result = run_update(before, "move", interactive=False)
        self.assertEqual(result.files, before,
                         "the move must be typed in an interactive session; piped input saying move is not consent")
        self.assertFalse(any('Type "move"' in prompt for prompt in result.prompts),
                         "the move question must not consume non-interactive input at all")
        self.assertEqual(len(result.prompts), 1, "the ordinary orphan prompt still runs and gets the piped line")
        self.assertIn("Remove 1 orphaned item?", result.prompts[0])
        self.assertIn("Run --update in a terminal", result.output)

    def test_non_interactive_yes_keeps_dev_out_of_the_orphan_step(self):
        before = legacy_install(extra=ORPHAN)
        result = run_update(before, ["y"], interactive=False)
        expected = {p: d for p, d in before.items() if p not in ORPHAN}
        self.assertEqual(result.files, expected,
                         "non-interactive: both folders stay byte for byte; only the ordinary orphan is removed")
        self.assertNotIn("dev", result.output.split("Orphaned items")[1],
                         "a dev folder kept by a non-interactive run must not fall through into orphan deletion")

    def test_interactivity_check_fails_closed(self):
        class Stream:
            def __init__(self, answer):
                self.answer = answer

            def isatty(self):
                if isinstance(self.answer, BaseException):
                    raise self.answer
                return self.answer

        cases = [(Stream(True), True), (Stream(False), False), (Stream(ValueError("closed file")), False),
                 (Stream(OSError("bad descriptor")), False), (None, False), (object(), False)]
        for stream, expected in cases:
            with self.subTest(stream=type(stream).__name__, expected=expected):
                with mock.patch.object(sys, "stdin", stream):
                    self.assertIs(sync_mod._stdin_is_interactive(), expected,
                                  "only a real terminal counts as interactive; any doubt must keep the folders")

    def test_eof_and_interrupt_keep_everything_without_ending_the_update(self):
        before = legacy_install(extra=ORPHAN)
        for signal in (EOFError, KeyboardInterrupt):
            with self.subTest(signal=signal.__name__):
                result = run_update(before, [signal, "n"])
                self.assertEqual(result.files, before)
                self.assertEqual(len(result.prompts), 2, "the orphan step must still run after a non-interactive legacy prompt")

    def test_closed_input_keeps_everything(self):
        before = legacy_install(extra=ORPHAN)
        for interactive in (True, False):
            with self.subTest(interactive=interactive):
                result = run_update(before, EOFError, interactive=interactive)
                self.assertEqual(result.files, before)

    def test_prompt_names_the_folders_and_backup_targets(self):
        result = run_update(legacy_install(), [""])
        self.assertIn("section11/.github/  (3 files)  ->  section11-legacy-github/", result.output)
        self.assertIn("section11/dev/  (2 files)  ->  section11-legacy-dev/", result.output)
        self.assertIn('Type "move"', result.prompts[0])

    def test_no_legacy_folders_means_no_prompt(self):
        before = legacy_install(github=False, dev=False)
        result = run_update(before, [])
        self.assertEqual(result.files, before)
        self.assertEqual(result.prompts, [])

    def test_declined_update_stops_before_the_legacy_offer(self):
        newer = dict(MANAGED)
        newer["README.md"] = b"newer upstream readme\n"
        before = legacy_install()
        result = run_update(before, ["n"], manifest=manifest_for(newer))
        self.assertEqual(result.files, before)
        self.assertEqual(len(result.prompts), 1)
        self.assertIn("Pull 1 update", result.prompts[0])


class TestLegacyMoveProtections(unittest.TestCase):

    def test_existing_backup_names_are_never_overwritten(self):
        taken = {
            "section11-legacy-github/keep.txt": b"an earlier backup\n",
            "section11-legacy-dev": b"a file that happens to have this name\n",
            "section11-legacy-dev-2/keep.txt": b"another earlier backup\n",
        }
        before = legacy_install(extra=taken)
        result = run_update(before, ["move"])
        for path, data in taken.items():
            self.assertEqual(result.files.get(path), data, f"{path} existed before and must be untouched")
        self.assertEqual(result.files.get("section11-legacy-github-2/workflows/pages.yml"),
                         GITHUB["section11/.github/workflows/pages.yml"])
        self.assertEqual(result.files.get("section11-legacy-dev-3/README.md"), DEV["section11/dev/README.md"])
        self.assertNotIn("section11/dev/README.md", result.files)

    def test_failed_rename_keeps_the_original_state(self):
        before = legacy_install(extra=ORPHAN)
        refuse = mock.patch.object(sync_mod.os, "rename", side_effect=OSError("cross-device link"))
        result = run_update(before, ["move", "y"], patches=[refuse])
        expected = {p: d for p, d in before.items() if p not in ORPHAN}
        self.assertEqual(result.files, expected,
                         "a failed rename must leave both folders in place; only the ordinary orphan is removed")
        self.assertIn("could not move it", result.output)

    def test_partial_rename_failure_keeps_and_protects_the_folder_that_stayed(self):
        real_rename = os.rename

        def rename(src, dst):
            if Path(src).name == "dev":
                raise OSError("permission denied")
            return real_rename(src, dst)

        before = legacy_install(extra=ORPHAN)
        result = run_update(before, ["move", "y"], patches=[mock.patch.object(sync_mod.os, "rename", rename)])
        for path, data in DEV.items():
            self.assertEqual(result.files.get(path), data, "dev could not be moved, so it must stay complete")
        self.assertIn("section11-legacy-github/workflows/pages.yml", result.files)
        self.assertNotIn("section11/old-guide.md", result.files)

    def test_git_checkout_is_never_offered_or_cleaned(self):
        before = legacy_install(extra=ORPHAN)
        result = run_update(before, ["y"], git_checkout=True)
        expected = {p: d for p, d in before.items() if p not in ORPHAN}
        self.assertEqual(result.files, expected, "a developer checkout keeps .github and dev; only the ordinary orphan goes")
        self.assertEqual(len(result.prompts), 1)
        self.assertNotIn('Type "move"', result.prompts[0])
        self.assertNotIn("dev", result.output.split("Orphaned items")[1])

    def test_git_checkout_helper_looks_for_dot_git_without_following_it(self):
        with mock.patch.object(sync_mod.os.path, "lexists", return_value=True) as lexists:
            self.assertTrue(sync_mod._is_git_checkout(Path("/data/section11")))
        self.assertEqual(Path(lexists.call_args.args[0]), Path("/data/section11/.git"))
        with mock.patch.object(sync_mod.os.path, "lexists", return_value=False):
            self.assertFalse(sync_mod._is_git_checkout(Path("/data/section11")))

    def test_symlinked_folder_is_left_alone(self):
        def is_symlink(path):
            return path.name == "dev"

        before = legacy_install()
        result = run_update(before, ["move"], patches=[mock.patch.object(Path, "is_symlink", is_symlink)])
        for path, data in DEV.items():
            self.assertEqual(result.files.get(path), data, "a symlinked dev must not be moved or followed")
        self.assertIn("Kept section11/dev: not an ordinary folder", result.output)
        self.assertIn("section11-legacy-github/workflows/pages.yml", result.files)

    def test_plain_file_named_like_a_legacy_folder_is_left_alone(self):
        before = legacy_install(github=False, extra={"section11/.github": b"a file, not a folder\n"})
        result = run_update(before, ["move"])
        self.assertEqual(result.files.get("section11/.github"), b"a file, not a folder\n")
        self.assertIn("Kept section11/.github: not an ordinary folder", result.output)
        self.assertIn("section11-legacy-dev/README.md", result.files)

    def test_dev_is_not_offered_while_the_upstream_manifest_still_lists_it(self):
        managed = dict(MANAGED)
        managed.update({p[len("section11/"):]: d for p, d in DEV.items()})
        before = legacy_install()
        result = run_update(before, ["move"], manifest=manifest_for(managed))
        for path, data in DEV.items():
            self.assertEqual(result.files.get(path), data, "a folder the manifest still manages must not be moved")
        self.assertNotIn("section11/dev/", result.output.split('Type "move"')[0].split("does not manage")[1])
        self.assertIn("section11-legacy-github/workflows/pages.yml", result.files)

    def test_only_the_exact_root_folders_are_considered(self):
        nested = {"section11/examples/dev/notes.md": b"nested\n", "section11/examples/.github/x.yml": b"nested hidden\n",
                  "dev/outside.md": b"data-dir dev folder\n", ".github/outside.yml": b"data-dir .github\n"}
        manifest = manifest_for(dict(MANAGED, **{"examples/dev/notes.md": b"nested\n"}))
        before = legacy_install(github=False, dev=False, extra=nested)
        result = run_update(before, ["move"], manifest=manifest)
        self.assertEqual(result.files, before, "nested or data-directory folders with these names are not legacy roots")
        self.assertEqual(result.prompts, [])


class TestRetainedDevIsNotAnOrphan(unittest.TestCase):

    def test_declined_move_then_yes_to_orphans_keeps_dev(self):
        before = legacy_install(extra=ORPHAN)
        result = run_update(before, ["", "y"])
        expected = {p: d for p, d in before.items() if p not in ORPHAN}
        self.assertEqual(result.files, expected,
                         "declining the move must not let the orphan prompt delete dev; the ordinary orphan still goes")
        listing = result.output.split("Orphaned items")[1]
        self.assertIn("old-guide.md", listing)
        self.assertNotIn("dev", listing, "retained dev files must not even be listed as orphans")
        self.assertIn("Remove 1 orphaned item?", result.prompts[1])

    def test_yes_pipe_with_an_ordinary_orphan_removes_only_that_orphan(self):
        before = legacy_install(extra=ORPHAN)
        result = run_update(before, "y")
        expected = {p: d for p, d in before.items() if p not in ORPHAN}
        self.assertEqual(result.files, expected)

    def test_empty_directories_inside_retained_dev_are_not_offered(self):
        with tempfile.TemporaryDirectory() as outer:
            data_dir = Path(outer) / "data"
            write_tree(data_dir, legacy_install())
            (data_dir / "section11" / "dev" / "empty" / "deeper").mkdir(parents=True)
            (data_dir / "section11" / "stale-empty").mkdir()
            prompts = []

            def fake_input(prompt=""):
                prompts.append(prompt)
                return "" if len(prompts) == 1 else "y"

            with working_directory(data_dir), contextlib.redirect_stdout(io.StringIO()), \
                    mock.patch.object(sync_mod, "_fetch_upstream_manifest", return_value=manifest_for(MANAGED)), \
                    mock.patch.object(sync_mod, "_is_git_checkout", return_value=False), \
                    mock.patch.object(sync_mod, "_stdin_is_interactive", return_value=True), \
                    mock.patch("builtins.input", fake_input):
                sync_mod.do_update()
            self.assertTrue((data_dir / "section11" / "dev" / "empty" / "deeper").is_dir(),
                            "empty folders under a retained dev must survive the orphan cleanup")
            self.assertFalse((data_dir / "section11" / "stale-empty").exists(),
                             "an ordinary empty folder is still removed")
            self.assertIn("Remove 1 orphaned item?", prompts[1])

    def test_ordinary_orphan_behaviour_is_unchanged(self):
        before = legacy_install(github=False, dev=False, extra=ORPHAN)
        kept = run_update(before, ["n"])
        self.assertEqual(kept.files, before)
        removed = run_update(before, ["y"])
        self.assertEqual(removed.files, {p: d for p, d in before.items() if p not in ORPHAN})

    def test_dev_listed_upstream_is_still_handled_by_the_normal_rules(self):
        managed = dict(MANAGED)
        managed["dev/README.md"] = DEV["section11/dev/README.md"]
        before = legacy_install(github=False)
        result = run_update(before, ["y"], manifest=manifest_for(managed))
        self.assertNotIn("section11/dev/tests/test_example.py", result.files,
                         "while upstream manages dev, a dev file it dropped is an ordinary orphan, as before")
        self.assertIn("section11/dev/README.md", result.files)


if __name__ == "__main__":
    unittest.main()
