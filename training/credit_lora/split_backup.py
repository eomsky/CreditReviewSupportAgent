"""Split large private checkpoints for the connector's 100 MiB transfer limit."""
import argparse
import hashlib
import json
from pathlib import Path


def split(source, target, part_bytes=40*1024*1024):
    source, target = Path(source), Path(target)
    target.mkdir(parents=True, exist_ok=True)
    whole = hashlib.sha256(); parts = []; size = 0
    with source.open('rb') as handle:
        while data := handle.read(part_bytes):
            name = f'{source.name}.part{len(parts)+1:03}'
            (target/name).write_bytes(data)
            whole.update(data); size += len(data)
            parts.append({'name':name, 'bytes':len(data), 'sha256':hashlib.sha256(data).hexdigest()})
    manifest = {'filename':source.name, 'bytes':size, 'sha256':whole.hexdigest(), 'parts':parts}
    (target/f'{source.name}.parts.json').write_text(json.dumps(manifest, indent=2))
    return manifest


def join(manifest_path, destination):
    manifest_path, destination = Path(manifest_path), Path(destination)
    manifest = json.loads(manifest_path.read_text())
    if destination.exists():
        raise FileExistsError(destination)
    temporary = destination.with_suffix(destination.suffix+'.joining')
    whole = hashlib.sha256(); size = 0
    with temporary.open('xb') as handle:
        for part in manifest['parts']:
            if Path(part['name']).name != part['name']:
                raise ValueError('Invalid part filename')
            data = (manifest_path.parent/part['name']).read_bytes()
            if len(data) != part['bytes'] or hashlib.sha256(data).hexdigest() != part['sha256']:
                raise ValueError('Part verification failed: '+part['name'])
            handle.write(data); whole.update(data); size += len(data)
    if size != manifest['bytes'] or whole.hexdigest() != manifest['sha256']:
        raise ValueError('Whole archive verification failed')
    temporary.replace(destination)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['split','join'])
    parser.add_argument('source', type=Path); parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(json.dumps((split if args.operation=='split' else join)(args.source,args.destination), indent=2))
