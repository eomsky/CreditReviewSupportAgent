"""Content-addressed reuse of approved normalization artifacts (never draft text)."""
import hashlib
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

FILES = ('numeric.sqlite', 'sql-facts.json',
         'normalization-trial/attempt-001/response.json')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cache_key(request, raw, source_hash, normalizer_hash):
    contract = {'policy': 1, 'request': request, 'raw': raw,
                'source_hash': source_hash, 'normalizer_hash': normalizer_hash}
    return hashlib.sha256(json.dumps(contract, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def validate(folder):
    folder = Path(folder)
    response = json.loads((folder / FILES[2]).read_text(encoding='utf-8-sig'))
    choice = response['choices'][0]
    if choice['finish_reason'] != 'stop':
        raise ValueError('Incomplete normalization')
    verdict = json.loads(choice['message']['content'])
    if (verdict['decision'] != 'approve' or verdict['issues'] or
            'unknown' in verdict['row_units'].values() or
            'unknown' in verdict['column_roles'].values()):
        raise ValueError('Normalization not approved')
    expected = json.loads((folder / FILES[1]).read_text(encoding='utf-8-sig'))
    with sqlite3.connect((folder / FILES[0]).resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        actual = [dict(r) for r in db.execute('SELECT * FROM approved_facts ORDER BY id')]
    if not actual or actual != expected:
        raise ValueError('SQL artifact mismatch')
    if any(r['review_hash'] != digest(folder / FILES[2]) for r in actual):
        raise ValueError('Approval provenance mismatch')


def publish(cache, key, folder, elapsed_seconds):
    cache, folder = Path(cache), Path(folder)
    validate(folder)
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / key
    if target.exists():
        return
    temporary = Path(tempfile.mkdtemp(prefix='.pending-', dir=cache))
    try:
        for name in FILES:
            dest = temporary / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(folder / name, dest)
        manifest = {'key': key, 'origin': str(folder.resolve()),
                    'initial_elapsed_seconds': elapsed_seconds,
                    'hashes': {n: digest(temporary / n) for n in FILES}}
        (temporary / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        temporary.rename(target)
    finally:
        if temporary.exists():
            if temporary.resolve().parent != cache.resolve():
                raise ValueError('Cache cleanup outside cache directory')
            shutil.rmtree(temporary)


def restore(cache, key, folder):
    source, folder = Path(cache) / key, Path(folder)
    if not source.exists():
        return None
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['key'] != key or set(manifest['hashes']) != set(FILES):
        raise ValueError('Cache manifest mismatch')
    if any(digest(source / n) != manifest['hashes'][n] for n in FILES):
        raise ValueError('Cached artifact changed')
    validate(source)
    for name in FILES:
        dest = folder / name
        if dest.exists():
            raise ValueError('Cannot overwrite trial artifact')
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, dest)
    return manifest
