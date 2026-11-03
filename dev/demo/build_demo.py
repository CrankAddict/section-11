"""Assemble the one fictional demo's owner files from a sealed release source."""
import argparse
import re
import shutil
from pathlib import Path


def sync_workflow(source):
    text = (source / 'examples/json-auto-sync/auto-sync.yml').read_text()
    for name, size in (('BOOTSTRAP_BLOB', 40), ('BOOTSTRAP_SHA256', 64)):
        if len(re.findall(r'^      ' + name + r': [0-9a-f]{' + str(size) + r'}$', text, re.M)) != 1:
            raise ValueError('demo requires the published sealed workflow')
    start = text.index('      - name: Prepare slow cache staging\n')
    end = text.index('      - name: Verify generated data\n', start)
    text = text[:start] + ('      - name: Generate clearly fictional daily data\n'
                          "        if: steps.prepare.outputs.run_sync == 'true'\n"
                          '        run: |\n'
                          '          python demo/generate.py\n'
                          '          python "$RUNNER_TEMP/section11-trusted-source/examples/maintenance/hosted.py" finalize-export --wrapper-api 2\n') + text[end:]
    start = text.index('      - name: Prepare changed slow sources for saving\n')
    end = text.index('      - name: Eligible update maintenance\n', start)
    text = text[:start] + text[end:]
    # Owner decision 96b requests daily data; the rest of the wrapper is unchanged.
    return text.replace("- cron: '7,37 * * * *'", "- cron: '7 5 * * *'")


def build(source, output):
    source, output = Path(source), Path(output)
    workflow = sync_workflow(source)  # Refuse unsealed input before any output.
    output.mkdir(parents=True, exist_ok=False)
    templates = source / 'dev/demo/templates'
    for path in templates.rglob('*'):
        if path.is_file():
            target = output / path.relative_to(templates)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    (output / 'demo').mkdir()
    shutil.copyfile(source / 'dev/demo/generate.py', output / 'demo/generate.py')
    shutil.copyfile(source / 'LICENSE', output / 'LICENSE')
    (output / 'custom').mkdir()
    shutil.copyfile(source / 'examples/maintenance/CUSTOM_README.md', output / 'custom/README.md')
    workflows = output / '.github/workflows'
    workflows.mkdir(parents=True)
    (workflows / 'auto-sync.yml').write_text(workflow)
    print('Demo owner files prepared at', output)
    print('Follow SETUP_DEMO.md; first Sync installs the verified official release.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output)
