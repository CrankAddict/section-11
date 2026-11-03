"""Prepare the exact default-branch infrastructure overlay, without Git writes.

Run on the reviewed candidate. The owner commits this overlay on the old main.
It leaves examples/sync.py, manifest.json and every user guide untouched there.
The staging branch removes the temporary hidden runtime when adding the candidate.
"""
import argparse
from pathlib import Path
import json

FILES = ('examples/sync.py', 'examples/maintenance/distribution.py',
         'examples/maintenance/github_api.py', 'examples/maintenance/publish_release.py',
         'examples/maintenance/release_package.py', 'examples/maintenance/seal_pins.py')
# distribution.py loads sync.py for the publisher's manifest/archive verifier.
# This hidden runtime copy is necessary for P, but is no longer a workflow pin target.


def build(source, output):
    source, output = Path(source).absolute(), Path(output).absolute()
    if any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('overlay path must not contain symlinks')
    if output == source or source in output.parents or output in source.parents:
        raise ValueError('use a separate new overlay directory')
    source_names = (*FILES, '.github/workflows/release.yml')
    contents = {}
    for name in source_names:
        path = source / name
        if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError('expected ordinary reviewed source')
        dest = name if name.startswith('.github/workflows/') else '.github/release-runtime/' + name
        contents[dest] = path.read_bytes()
    output.mkdir(parents=False, exist_ok=False)
    for name, data in contents.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if target.read_bytes() != data:
            raise ValueError('infrastructure readback differs')
    return sorted(contents)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({'files': build(args.source, args.output)}, indent=2))
