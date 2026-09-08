import importlib.util
import json
from pathlib import Path
import sys
import pytest

directory=Path(__file__).parents[1]/'training/credit_lora'
sys.path.insert(0,str(directory))
spec=importlib.util.spec_from_file_location('serve_adapter',directory/'serve_adapter.py')
serving=importlib.util.module_from_spec(spec); spec.loader.exec_module(serving)
sys.path.remove(str(directory))


def make_adapter(path):
    path.mkdir()
    (path/'adapter_config.json').write_text(json.dumps({'base_model_name_or_path':serving.BASE,'r':16}))
    (path/'adapter_manifest.json').write_text(json.dumps({'base_revision':serving.REVISION,'merged':False}))
    (path/'adapter_model.safetensors').write_bytes(b'test placeholder')


def test_base_and_adapter_command_separation(tmp_path):
    assert serving.adapter_arguments([])==[]
    folder=tmp_path/'adapter'; make_adapter(folder)
    flags=serving.adapter_arguments([f'credit-sft={folder}'])
    assert '--enable-lora' in flags
    item=json.loads(flags[-1])
    assert item=={'name':'credit-sft','path':str(folder.resolve()),'base_model_name':serving.BASE}
    with pytest.raises(ValueError,match='distinct'):
        serving.adapter_arguments([f'credit-sft={folder}',f'credit-sft={folder}'])


def test_adapter_revision_must_match(tmp_path):
    folder=tmp_path/'adapter'; make_adapter(folder)
    (folder/'adapter_manifest.json').write_text(json.dumps({'base_revision':'wrong','merged':False}))
    with pytest.raises(ValueError,match='revision mismatch'):
        serving.adapter_arguments([f'credit-sft={folder}'])


def test_recovery_pins_actual_base_and_tokenizer_before_loading_adapter():
    old=['vllm','serve',serving.BASE]
    restored=serving.pinned_base_command(old)
    assert restored[restored.index('--revision')+1] == serving.REVISION
    assert restored[restored.index('--tokenizer-revision')+1] == serving.REVISION
    assert old==['vllm','serve',serving.BASE]
    assert serving.pinned_base_command(restored)==restored
    with pytest.raises(ValueError,match='revision mismatch'):
        serving.pinned_base_command(old+['--revision','different'])
    with pytest.raises(ValueError,match='revision mismatch'):
        serving.pinned_base_command(old+['--tokenizer-revision','different'])
    with pytest.raises(ValueError,match='pinned base'):
        serving.pinned_base_command(['vllm','serve','other-model'])


def test_compact_json_setting_is_an_engine_option_not_request_option():
    original=['vllm','serve',serving.BASE]
    command=serving.compact_structured_command(original)
    assert original==['vllm','serve',serving.BASE]
    value=json.loads(command[command.index('--structured-outputs-config')+1])
    assert value=={'backend':'xgrammar','disable_any_whitespace':True}
    assert serving.compact_structured_command(command)==command
