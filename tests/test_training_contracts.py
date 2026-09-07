import runpy
from pathlib import Path

ROOT=Path(__file__).parents[1]
prepare=runpy.run_path(str(ROOT/'training/credit_lora/prepare_data.py'))
tokenize=runpy.run_path(str(ROOT/'training/credit_lora/tokenize_data.py'))

def test_numeric_audit_excludes_ids_but_detects_invented_amount():
    audit=prepare['unsupported_numbers']
    assert audit({'source':'S01','amount':100,'year':2026},{'factor_id':'F01','amount':999})==[999.0]
    assert audit({'amount':100},'금액 100.0, 담보는 2차 회수수단')==[]

def test_stratification_preserves_group_identity_and_is_deterministic():
    rows=[{'archetype_id':str(g),'record_id':f'{g}-{i}'} for g in range(4) for i in range(8)]
    selected=tokenize['stratified'](rows,8,42)
    assert selected==tokenize['stratified'](rows,8,42)
    assert all(sum(r['archetype_id']==str(g) for r in selected)==2 for g in range(4))

class CharTokenizer:
    def apply_chat_template(self,messages,tokenize,add_generation_prompt,enable_thinking):
        return ''.join(m['role']+':'+m['content']+';' for m in messages)+('assistant:' if add_generation_prompt else '')
    def __call__(self,text,**kwargs):
        return {'input_ids':[ord(x) for x in text],'offset_mapping':[(i,i+1) for i in range(len(text))]}

def test_completion_mask_never_trains_on_prompt_and_does_not_truncate():
    r={'record_id':'x','case_id':'c','archetype_id':'a','stage':'bundle','messages':[
        {'role':'user','content':'source facts'},{'role':'assistant','content':'grounded answer'}]}
    encoded,error=tokenize['encode_record'](CharTokenizer(),r,1000)
    assert error is None
    trained=''.join(chr(x) for x in encoded['labels'] if x!=-100)
    assert trained=='grounded answer;'
    encoded,error=tokenize['encode_record'](CharTokenizer(),r,10)
    assert encoded is None and error['reason']=='overlength'

def test_gemma_empty_thought_prefix_is_not_a_supervised_target():
    class GemmaTokenizer(CharTokenizer):
        def apply_chat_template(self,messages,tokenize,add_generation_prompt,enable_thinking):
            text=super().apply_chat_template(messages,tokenize,add_generation_prompt,enable_thinking)
            return text+('<|channel>thought\n<channel|>' if add_generation_prompt else '')
    r={'record_id':'x','case_id':'c','archetype_id':'a','stage':'bundle','messages':[
        {'role':'user','content':'facts'},{'role':'assistant','content':'answer'}]}
    encoded,error=tokenize['encode_record'](GemmaTokenizer(),r,1000)
    assert error is None
    assert ''.join(chr(x) for x in encoded['labels'] if x!=-100)=='answer;'
