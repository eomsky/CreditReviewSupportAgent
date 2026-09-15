"""Focused CF mapping trial. Fixture-specific inputs; never an end-to-end benchmark."""
import json
import sys
from pathlib import Path
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import llm_stream


def main():
    out=ROOT/'outputs/frozen_candidates'/('structured-selection-replay'+(sys.argv[1] if len(sys.argv)>1 else ''))
    out.mkdir(exist_ok=False)
    root=ROOT/'outputs/frozen_candidates/structured-pdf-probe'
    cells=json.loads((root/'frame/cells.json').read_text(encoding='utf-8'))
    # Two physical CF pages are selected for this fixture, not a general retriever.
    selected=[c for c in cells if c['physical_table_id'] in ['P0012_T001','P0013_T001'] and c['raw_value']!='']
    aliases={f'C{i}':c for i,c in enumerate(selected)}
    master=json.loads((root/'MASTER.json').read_text(encoding='utf-8'))
    heading='\n'.join(b['text'] for b in master['raw_document']['pages'][11]['blocks'][:6])
    fields={}
    for row in ['영업활동현금흐름','투자활동현금흐름','재무활동현금흐름','기말현금']:
        for year in [2023,2024,2025]:
            fields[f'{row}_{year}']={'anyOf':[{'type':'string','enum':list(aliases)},{'type':'null'}]}
    schema={'type':'object','properties':fields,'required':list(fields),'additionalProperties':False}
    request={'model':json.loads((ROOT/'workspace/llm_connection.json').read_text(encoding='utf-8')).get('model','google/gemma-4-31B-it'),
        'messages':[{'role':'system','content':'원문 헤더의 기간과 행/열 의미를 검토하여 요청된 현금흐름 표 칸에 해당하는 원문 셀 ID만 선택한다. 숫자를 재작성하지 않는다. 자료가 없는 연도는 null. 당기/전기는 표 위 기간 설명과 대응한다. 중간 유입/유출 소계 대신 영업/투자/재무 순현금흐름을 선택한다. 파서 REVIEW_REQUIRED 자료이므로 행열과 실제 값을 대조한다.'},
        {'role':'user','content':json.dumps({'period_context':heading,
          'tables':{c['physical_table_id']:{'units':c['units'],'parser_status':c['parser_status']} for c in selected},
          'cell_fields':['table','row','column','raw'],
          'cells':{k:[c['physical_table_id'],c['row_path'],c['column_path'],c['raw_value']] for k,c in aliases.items()}},ensure_ascii=False,separators=(',',':'))}],
        'temperature':0,'max_tokens':1800,'chat_template_kwargs':{'enable_thinking':False},'structured_outputs':{'json':schema}}
    def save(name,data): (out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    save('request.json',request);save('aliases.json',aliases)
    start=perf_counter()
    response=llm_stream.complete(json.loads((ROOT/'workspace/llm_connection.json').read_text(encoding='utf-8')),request,lambda d,t:(out/'stream.txt').write_text(t,encoding='utf-8'),timeout=240)
    save('response.json',response)
    choice=response['choices'][0]
    result={'elapsed_seconds':perf_counter()-start,'usage':response.get('usage'),'finish_reason':choice['finish_reason'],'end_to_end':False}
    if choice['finish_reason']!='length':
        mapping=json.loads(choice['message']['content'])
        restored={k:aliases[v] if v is not None else None for k,v in mapping.items()}
        save('selected-cells.json',restored)
        result['missing_2023_preserved']=all(v is None for k,v in restored.items() if k.endswith('2023'))
        expected=json.loads((root/'cashflow-check.json').read_text(encoding='utf-8'))['checks']
        result['eight_source_cells_match']=set(c['cell_id'] for c in restored.values() if c)==set(c['cell_id'] for c in expected)
        # Fixture oracle checks row/year assignment as well as the unordered set.
        rows=['영업활동현금흐름','투자활동현금흐름','재무활동현금흐름','기말현금']
        oracle={f'{rows[i//2]}_{2025 if i%2==0 else 2024}':c['cell_id'] for i,c in enumerate(expected)}
        result['row_year_assignments_match']=all(restored[k] and restored[k]['cell_id']==cid for k,cid in oracle.items())
    save('result.json',result);print(json.dumps(result))


if __name__=='__main__':main()
