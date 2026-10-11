"""Package the public project page and the verified walkthrough allowlist.

Usage: python scripts/build_site.py --out /path/to/new/export
Add --require-published-code immediately before deploying the export.
Existing output files outside the manifest cause a failure, never deletion.
"""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess

parser=argparse.ArgumentParser()
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--require-published-code', action='store_true')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
out=args.out.resolve()
if out==root or root in out.parents:
    raise ValueError('Use a separate export directory outside the repository')
release=json.loads((root/'walkthrough/release-manifest.json').read_text())
if args.require_published_code:
    remote=subprocess.check_output(['git','ls-remote','https://github.com/bentang18/MAPA.git','refs/heads/main'],text=True).split()[0]
    if remote!=release['code_commit']:
        raise ValueError('Publish the pinned MAPA commit before publishing this website')
files={Path('index.html'),Path('.nojekyll'),Path('walkthrough/release-manifest.json')}
for directory in ['static','representations']:
    files.update(p.relative_to(root) for p in (root/directory).rglob('*') if p.is_file())
for name,sha in release['files'].items():
    f=Path('walkthrough')/name
    if hashlib.sha256((root/f).read_bytes()).hexdigest()!=sha:
        raise ValueError(f'Stale walkthrough asset: {f}')
    files.add(f)
if out.exists():
    extras={p.relative_to(out) for p in out.rglob('*') if p.is_file()}-files-{Path('build-manifest.json')}
    if extras: raise ValueError(f'Choose a fresh export directory; unexpected files: {extras}')
for f in sorted(files):
    target=out/f
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(root/f,target)
checksums={str(f):hashlib.sha256((out/f).read_bytes()).hexdigest() for f in sorted(files)}
(out/'build-manifest.json').write_text(json.dumps(checksums,indent=2)+'\n')
print(f'Packaged {len(files)} files in {out}; code {release["code_commit"]}')
