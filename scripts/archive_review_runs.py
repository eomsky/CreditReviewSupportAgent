"""Deduplicated private case archive, with hash-verified restore into a new folder."""
import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
import zipfile


def pack(root,archive,case_id=None):
    root=Path(root).resolve(); archive=Path(archive).resolve()
    cases=root/'cases'
    if case_id is not None:
        if not re.fullmatch(r'[A-Za-z0-9_-]+',case_id):
            raise ValueError('Invalid case identifier')
        cases=cases/case_id
    if not cases.is_dir():
        raise ValueError('Archive root must contain the selected cases directory')
    files=list(cases.rglob('*'))+list(root.glob('watch_*.json'))+list(root.glob('watch_*.log'))
    active={p.parent for p in cases.rglob('.run.lock')}
    files=[p for p in files if p.is_file() and not p.is_symlink() and not any(a in p.parents for a in active)]
    if not files:
        raise ValueError('No completed files to archive')
    entries=[]; stored=set()
    archive.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(files):
            if not path.is_file() or path.is_symlink() or any(p in path.parents for p in active):
                continue
            data=path.read_bytes(); digest=hashlib.sha256(data).hexdigest()
            entry={'path':path.relative_to(root).as_posix(),'sha256':digest,'bytes':len(data)}
            entries.append(entry)
            if digest not in stored:
                z.writestr('objects/'+digest,data); stored.add(digest)
        manifest={'format':'credit-review-archive-v1','files':entries,
                  'skipped_active_runs':[p.relative_to(root).as_posix() for p in sorted(active)]}
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    return {'archive':str(archive),'files':len(entries),'unique_objects':len(stored),
            'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
            'skipped_active_runs':manifest['skipped_active_runs']}


def restore(archive,target):
    target=Path(target).resolve()
    if target.exists() and any(target.iterdir()):
        raise ValueError('Restore target must be new or empty')
    with zipfile.ZipFile(archive) as z:
        manifest=json.loads(z.read('manifest.json'))
        if manifest.get('format')!='credit-review-archive-v1':
            raise ValueError('Unsupported archive format')
        checked=[]; seen=set()
        for entry in manifest['files']:
            relative=PurePosixPath(entry['path'])
            if relative.is_absolute() or '..' in relative.parts or '\\' in entry['path'] or ':' in entry['path']:
                raise ValueError('Unsafe archive path')
            destination=(target/Path(*relative.parts)).resolve()
            if not destination.is_relative_to(target) or destination in seen:
                raise ValueError('Duplicate or unsafe archive path')
            seen.add(destination)
            data=z.read('objects/'+entry['sha256'])
            if len(data)!=entry['bytes'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:
                raise ValueError('Archive content hash mismatch')
            checked.append((destination,entry['sha256']))
        # Validate all objects before writing any restored files.
        for destination,digest in checked:
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(z.read('objects/'+digest))
    return {'restored_files':len(checked),'target':str(target)}


def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest='action',required=True)
    create=sub.add_parser('pack'); create.add_argument('root',type=Path); create.add_argument('archive',type=Path)
    create.add_argument('--case',dest='case_id',help='Archive one case under ROOT/cases')
    read=sub.add_parser('restore'); read.add_argument('archive',type=Path); read.add_argument('target',type=Path)
    a=p.parse_args()
    print(json.dumps(pack(a.root,a.archive,a.case_id) if a.action=='pack' else restore(a.archive,a.target),ensure_ascii=False))


if __name__=='__main__': main()
