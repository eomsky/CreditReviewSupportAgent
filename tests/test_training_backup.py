import importlib.util
import json
from pathlib import Path
import pytest

path = Path(__file__).parents[1]/'training/credit_lora/split_backup.py'
spec = importlib.util.spec_from_file_location('split_backup', path)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def test_backup_roundtrip_and_corruption(tmp_path):
    original = tmp_path/'original.zip'; original.write_bytes(bytes(range(256))*3)
    pieces = tmp_path/'pieces'
    manifest = backup.split(original, pieces, part_bytes=100)
    restored = tmp_path/'restored.zip'
    backup.join(pieces/'original.zip.parts.json', restored)
    assert restored.read_bytes() == original.read_bytes()
    assert len(manifest['parts']) == 8
    (pieces/manifest['parts'][0]['name']).write_bytes(b'corrupted')
    with pytest.raises(ValueError, match='Part verification failed'):
        backup.join(pieces/'original.zip.parts.json', tmp_path/'bad.zip')
    assert not (tmp_path/'bad.zip').exists()


def test_backup_refuses_path_escape(tmp_path):
    manifest = {'parts':[{'name':'../outside', 'bytes':1, 'sha256':'bad'}]}
    source = tmp_path/'parts.json'; source.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='Invalid part filename'):
        backup.join(source, tmp_path/'bad.zip')
