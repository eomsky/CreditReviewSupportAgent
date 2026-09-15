"""Focused replay of a saved review request, explicitly not an end-to-end run."""
import copy
import json
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
source_id=sys.argv[1]
number=int(sys.argv[2])
source=ROOT/'outputs/frozen_candidates'/source_id
out=ROOT/'outputs/frozen_candidates'/f'F8-audit-replay-{source_id}-{number:03}'
out.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(source/'code/scripts'))
import llm_stream

def write(name,value):
    (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

request=json.loads((source/'calls'/f'{number:03}.request.json').read_text(encoding='utf-8'))
request=copy.deepcopy(request)
checks=request['structured_outputs']['json']['properties']['quality_checks']['properties']
for item in checks.values():
    item['properties']['reason'].update(maxLength=400,description='핵심 대조 결과만 1~3문장으로 기록. 수치 목록이나 같은 결론을 반복하지 않는다. 상세한 설명은 수정 본문에 작성한다.')
write('request.json',request)
write('scope.json',{'source_candidate':source_id,'source_call':number,'end_to_end':False,
                    'change':'Internal quality-check reason maxLength 400. All body fields, input evidence and paragraph coverage unchanged.'})
config=json.loads((ROOT/'workspace/llm_connection.json').read_text(encoding='utf-8'))
started=time.monotonic()
def progress(delta,text):
    (out/'stream.txt').write_text(text,encoding='utf-8')
try:
    response=llm_stream.complete(config,request,progress,timeout=600)
    write('response.json',response)
    choice=response['choices'][0]
    result={'status':'completed' if choice['finish_reason']!='length' else 'truncated',
            'elapsed_seconds':round(time.monotonic()-started,2),'usage':response.get('usage'),
            'end_to_end':False,'finish_reason':choice['finish_reason']}
    if choice['finish_reason']!='length':
        parsed=json.loads(choice['message']['content'])
        result['reason_lengths']={k:len(v['reason']) for k,v in parsed['quality_checks'].items()}
        result['reason_bound_passed']=all(n<=400 for n in result['reason_lengths'].values())
        user=json.loads(request['messages'][-1]['content']);draft=user['draft']
        paragraphs=[p for s in draft.get('sections',[draft]) for p in s['paragraphs']]
        ids={p['id'] for p in paragraphs}
        result['paragraph_coverage_passed']=(len(parsed['revisions'])==len(ids) and {r['paragraph_id'] for r in parsed['revisions']}==ids)
        by_id={r['paragraph_id']:r for r in parsed['revisions']}
        final=[by_id[p['id']].get('text','') if by_id[p['id']]['action']=='revise' else p['text'] for p in paragraphs]
        (out/'reviewed-body.txt').write_text('\n\n'.join(final),encoding='utf-8')
    write('results.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)
except Exception as error:
    write('results.json',{'status':'failed','elapsed_seconds':round(time.monotonic()-started,2),
                          'error_type':type(error).__name__,'end_to_end':False})
    raise
