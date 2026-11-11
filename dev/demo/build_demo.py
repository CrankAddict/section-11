"""Assemble the one fictional demo's owner files from a sealed release source."""
import argparse
import hashlib
import importlib.util
import re
import shutil
from pathlib import Path


def load(name, relative):
    # Use this builder's reviewed validators, never execute code from --source.
    path = Path(__file__).resolve().parents[2] / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SEAL = load('demo_seal', 'examples/maintenance/seal_pins.py')
GATE = load('demo_gate', 'dev/hosted_gate.py')
WORKFLOW = 'examples/json-auto-sync/auto-sync.yml'
DEMO_STEP = '''      - name: Generate clearly fictional daily data
        id: sync
        if: steps.prepare.outputs.run_sync == 'true'
        timeout-minutes: 3
        env:
          RUNTIME_TAG: ${{ steps.select.outputs.tag }}
          RUNTIME_COMMIT: ${{ steps.select.outputs.commit }}
          RUNTIME_DIGEST: ${{ steps.bootstrap.outputs.manifest_sha256 }}
          APPLICATION_TAG: ${{ steps.prepare.outputs.application_tag }}
          APPLICATION_COMMIT: ${{ steps.prepare.outputs.application_commit }}
          APPLICATION_DIGEST: ${{ steps.prepare.outputs.application_sha256 }}
        shell: bash
        run: |
          python -I -B "$RUNNER_TEMP/section11-deadline.py" 30 python -I -B demo/generate.py
          exec python -I -B "$RUNNER_TEMP/section11-deadline.py" 90 python -I -B "$RUNNER_TEMP/section11-gate.py" finalize-export --tag "$RUNTIME_TAG" --commit "$RUNTIME_COMMIT" --wrapper-api 2 --manifest-sha256 "$RUNTIME_DIGEST" --application-tag "$APPLICATION_TAG" --application-commit "$APPLICATION_COMMIT" --application-sha256 "$APPLICATION_DIGEST"
'''


def replace_steps(text, names, following, replacement):
    """Refuse changed boundaries instead of silently dropping a new step."""
    anchors = ['      - name: ' + name + '\n' for name in (*names, following)]
    if any(text.count(anchor) != 1 for anchor in anchors):
        raise ValueError('demo workflow step contract changed')
    start, end = text.index(anchors[0]), text.index(anchors[-1])
    if tuple(re.findall(r'^      - name: (.+)$', text[start:end], re.M)) != names:
        raise ValueError('demo workflow step order changed')
    return text[:start] + replacement + text[end:]


def require_phase_contract(text):
    """The demo's finalization must use the same identity contract as validation."""
    anchor = '      - name: Verify generated data\n'
    if text.count(anchor) != 1:
        raise ValueError('demo workflow validation step changed')
    validate = text.split(anchor, 1)[1].split('      - name: ', 1)[0]
    environment = DEMO_STEP.split('        env:\n', 1)[1].split('        shell:', 1)[0]
    command = DEMO_STEP.splitlines()[-1].strip().replace('section11-gate.py" finalize-export ',
                                                       'section11-gate.py" validate ')
    guard = '          cat > "$RUNNER_TEMP/section11-deadline.py" <<\'SECTION11_DEADLINE\'\n'
    if ('        env:\n' + environment + '        run: ' + command + '\n' not in validate
            or text.count(guard) != 1):
        raise ValueError('demo workflow identity or deadline contract changed')


def sync_workflow(source):
    try:
        data = SEAL.ordinary(source.absolute(), WORKFLOW)
        if any(marker in data for marker in (b'UNSEALED', b'BOOTSTRAP_BLOB', b'BOOTSTRAP_SHA256')):
            raise ValueError('legacy or unsealed workflow')
        SEAL.embedded_gate(data)
        files = GATE.manifest(SEAL.ordinary(source.absolute(), 'manifest.json'))
        if WORKFLOW not in files or hashlib.sha256(data).hexdigest() != files[WORKFLOW]['hash']:
            raise ValueError('workflow differs from release manifest')
    except (OSError, ValueError) as exc:
        raise ValueError('demo requires the published sealed workflow: ' + str(exc)) from exc
    text = data.decode('utf-8')
    require_phase_contract(text)
    text = replace_steps(text, ('Prepare slow cache staging', 'Restore slow sources', 'Run sync'),
                         'Verify generated data', DEMO_STEP)
    text = replace_steps(text, ('Prepare changed slow sources for saving', 'Save changed slow sources'),
                         'Eligible update maintenance', '')
    # Owner decision 96b requests daily data; the rest of the wrapper is unchanged.
    if re.findall(r'^    - cron: .+$', text, re.M) != ["    - cron: '7,37 * * * *'"]:
        raise ValueError('demo workflow schedule contract changed')
    return text.replace("- cron: '7,37 * * * *'", "- cron: '7 5 * * *'")


def build(source, output):
    source, output = Path(source), Path(output)
    workflow = sync_workflow(source)  # Refuse unsealed input before any output.
    output.mkdir(parents=True, exist_ok=False)
    templates = source / 'dev/demo/templates'
    shutil.copyfile(templates / 'SETUP_DEMO.md', output / 'SETUP_DEMO.md')
    repo = output / 'repo'
    repo.mkdir()
    # Only repository files go here. First Sync creates the standard README
    # through the verified installer's ordinary release-template rendering.
    for name in ('DOSSIER.md', 'demo/ABOUT_THIS_DEMO.md'):
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(templates / name, target)
    shutil.copyfile(source / 'dev/demo/generate.py', repo / 'demo/generate.py')
    (repo / 'custom').mkdir()
    shutil.copyfile(source / 'examples/maintenance/CUSTOM_README.md', repo / 'custom/README.md')
    workflows = repo / '.github/workflows'
    workflows.mkdir(parents=True)
    (workflows / 'auto-sync.yml').write_text(workflow)
    print('Demo repository files prepared at', repo)
    print('Owner instructions:', output / 'SETUP_DEMO.md')
    print('Follow SETUP_DEMO.md; first Sync installs the verified official release.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output)
