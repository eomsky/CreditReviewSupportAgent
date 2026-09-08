import importlib.util
import json
from pathlib import Path
import zipfile
import pytest

spec=importlib.util.spec_from_file_location('review_archive',Path(__file__).parents[1]/'scripts/archive_review_runs.py')
archive=importlib.util.module_from_spec(spec); spec.loader.exec_module(archive)


def test_private_archive_roundtrip_deduplicates_and_skips_active(tmp_path):
    root=tmp_path/'bench'; root.mkdir()
    for name in ('one','two','active'):
        run=root/'cases'/'case'/'runs'/name; run.mkdir(parents=True)
        (run/'state.json').write_text('{"status":"draft"}')
    (run/'.run.lock').write_text('active')
    (root/'llm_connection.json').write_text('must not be archived')
    output=tmp_path/'out.zip'
    result=archive.pack(root,output)
    assert result['files']==2 and result['unique_objects']==1
    restored=tmp_path/'restored'; archive.restore(output,restored)
    assert len(list(restored.rglob('state.json')))==2
    assert not (restored/'llm_connection.json').exists()
    with pytest.raises(ValueError,match='new or empty'):
        archive.restore(output,restored)


def test_archive_rejects_traversal_before_write(tmp_path):
    output=tmp_path/'bad.zip'
    with zipfile.ZipFile(output,'w') as z:
        z.writestr('manifest.json',json.dumps({'format':'credit-review-archive-v1','files':[
            {'path':'../outside','sha256':'anything','bytes':0}]}))
    with pytest.raises(ValueError,match='Unsafe'):
        archive.restore(output,tmp_path/'restored')


def test_wrong_root_cannot_create_false_empty_backup(tmp_path):
    root=tmp_path/'case'; root.mkdir()
    output=tmp_path/'out.zip'
    with pytest.raises(ValueError,match='cases directory'):
        archive.pack(root,output)
    assert not output.exists()
    (root/'cases').mkdir()
    with pytest.raises(ValueError,match='No completed files'):
        archive.pack(root,output)
    assert not output.exists()


def test_single_case_archive_preserves_restore_layout(tmp_path):
    for case in ('selected','other'):
        folder=tmp_path/'cases'/case/'runs'/'one'; folder.mkdir(parents=True)
        (folder/'state.json').write_text(case)
    output=tmp_path/'out.zip'
    result=archive.pack(tmp_path,output,'selected')
    assert result['files']==1
    archive.restore(output,tmp_path/'restored')
    assert (tmp_path/'restored/cases/selected/runs/one/state.json').read_text()=='selected'
    assert not (tmp_path/'restored/cases/other').exists()
    with pytest.raises(ValueError,match='Invalid case'):
        archive.pack(tmp_path,tmp_path/'bad.zip','../other')
