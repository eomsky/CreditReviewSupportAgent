"""Actual-source retrieval and patch probes, not a full report run."""
import ast,copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'outputs/frozen_candidates/C7/code/scripts'
sys.path.insert(0,str(BASE))
from review_documents import DocumentStore
from frozen_page_vector_sources import PageVectorStore
from frozen_template_selection import select
from frozen_primary_scope_patch import patch as primary
from frozen_template_selection_patch import patch as templates
from frozen_filled_retrieval_patch import patch as filled,business
import report_tables
frozen=ROOT/'outputs/experiments/20260914/frozen'
payload=json.loads((frozen/'baseline_run/input.json').read_text(encoding='utf-8'))['payload']
store=PageVectorStore(DocumentStore(ROOT/'workspace/review_documents'),payload['documents'],frozen,ROOT/'outputs/frozen_candidates/page-vector-index')
result={'end_to_end':False}
try:
    code=business(templates(primary((BASE/'business_report_test.py').read_text(encoding='utf-8'))))
    ast.parse(code)
    module={};exec(filled((BASE/'report_table_review.py').read_text(encoding='utf-8')),module)
    state=json.loads((ROOT/'outputs/frozen_candidates/C7/state.json').read_text(encoding='utf-8'))
    draft=json.loads((ROOT/'outputs/frozen_candidates/C7/run/summary_2.memory.json').read_text(encoding='utf-8'))['draft']
    fresh=module['retrieve'](store,draft,store.manifest(payload['documents']))
    result['filled_table_retrieval']={'count':len(fresh),'characters':sum(len(s['text']) for s in fresh),'connected_income_found':any('2,093,051,380,661' in s['text'] for s in fresh),'sources':[s['id'] for s in fresh]}
    request=json.loads((ROOT/'outputs/frozen_candidates/C7/calls/036.request.json').read_text(encoding='utf-8'))
    body=json.loads(request['messages'][1]['content'])
    outline=body.get('sections',[])
    if not outline:
        print('request keys',list(body))
        outline=[{'title':x['title']} for x in payload.get('report_outline',[])]
    chosen,info=select(report_tables.CATALOG,outline,store.vector)
    result['templates']={**info,'outline':outline,'selected_titles':[x['title'] for x in chosen]}
    from frozen_exact_template_source import ensure_exact_sources
    from frozen_primary_scope import primary_ids
    from review_documents import PRIORITIES
    import fixed_review_tables
    result['primary_scope']={}
    for view,layouts in fixed_review_tables.TEMPLATES.items():
        evidence=ensure_exact_sources(store,layouts,store.manifest(payload['documents']),[],PRIORITIES)
        result['primary_scope'][view]=list(primary_ids(layouts,evidence,PRIORITIES))
    assert all(len(result['primary_scope'][key])==1 for key in ('financial_accounts','profitability','financial_stability'))
    import urllib.request
    cfg=json.loads((ROOT/'workspace/llm_connection.json').read_text(encoding='utf-8'))
    endpoint=cfg['base_url'].rstrip('/').removesuffix('/v1')+'/tokenize'
    modified=copy.deepcopy(request['messages'])
    body['base_templates']=chosen
    modified[1]['content']=json.dumps(body,ensure_ascii=False)
    modified[0]['content']+='\n'+json.dumps([[t['id'],t['title'],t.get('use','')] for t in report_tables.CATALOG],ensure_ascii=False,separators=(',',':'))
    counts=[]
    for messages in (request['messages'],modified):
        req=urllib.request.Request(endpoint,data=json.dumps({'model':cfg['model'],'messages':messages,'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':False}}).encode(),headers={'Authorization':'Bearer '+cfg['api_key'],'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=30) as response:counts.append(json.load(response)['count'])
    result['template_input_tokens']={'before':counts[0],'after':counts[1],'reclaimed':counts[0]-counts[1]}
    result['patch_ast_passed']=True
    print(json.dumps(result,ensure_ascii=False))
    (ROOT/'outputs/frozen_candidates/C8-preflight.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
finally:store.vector.client.close()
