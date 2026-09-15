"""The model chooses and fills approved layouts; rendering owns their structure."""
from table_caption import format_caption
import json
import re
from pathlib import Path

CATALOG=json.loads((Path(__file__).resolve().parents[1]/'prompts/report_table_catalog.json').read_text(encoding='utf-8'))

def configure(schema, outline, aliases, context=None):
    keywords={'platform':['핀테크','플랫폼','간편결제'],'resort':['리조트','호텔','회원권'],'pf':['분양','책임준공','PF'],'project':['수주','미청구공사','플랜트'],'semiconductor':['반도체','웨이퍼']}
    industries={k for k,words in keywords.items() if context is not None and any(w in context for w in words)}
    candidates=[t for t in CATALOG if context is None or t['industry']=='common' or t['industry'] in industries]
    alternatives=[]
    for t in candidates:
        fixed=bool(t.get('rows'));labels=t.get('rows') or t.get('label_rows');width=len(t['columns'])-int(bool(labels))
        values={'type':'array','minItems':len(labels) if labels else t.get('min_rows',2),'maxItems':len(labels) if labels else t.get('max_rows',8),'items':{'type':'array','minItems':width,'maxItems':width,'items':{'type':['number','null'] if fixed else ['string','number','null']}}}
        props={'template_id':{'type':'string','enum':[t['id']]},'section_title':{'type':'string','enum':[x['title'] for x in outline]},'after_paragraph_index':{'type':'integer','minimum':0},'basis':{'type':'string'},'values':values,'source_ids':{'type':'array','minItems':1,'items':{'type':'string','enum':list(aliases)}}}
        props['row_evidence']={'type':'array','minItems':values['minItems'],'maxItems':values['maxItems'],'items':{'type':'string','enum':list(aliases)}}
        if t.get('periods'):props['periods']={'type':'array','minItems':3,'maxItems':3,'items':{'type':'string'}}
        alternatives.append({'type':'object','properties':props,'required':list(props),'additionalProperties':False})
    schema['properties']['report_tables']={'type':'array','minItems':len(outline),'maxItems':len(outline)*2,'items':{'anyOf':alternatives}}
    schema['required']=list(schema['required'])+['report_tables']
    schema['properties']['sections']['items']['properties'].pop('tables',None)
    bank=[{k:v for k,v in t.items() if k not in ('reference','presentation','column_guidance')} for t in candidates]
    return '\n사전 정의 표 양식: '+json.dumps(bank,ensure_ascii=False)+'\n현재 기업의 원문 사업구조에 적합한 industry의 표 또는 common 표를 선택한다. report_tables에는 중분류(section_title)마다 최소 1개, 필요하면 2개의 표를 반드시 배치한다. 기업개요에는 company_profile, 사업성에는 business_structure 또는 업종 특화표, 종합 심사의견에는 assessment_matrix 등 정성 표도 활용한다. required_labels는 가능한 한 각 행으로 포함하고 미확인은 명시한다. 최소 2개 이상의 실질 행으로 구성하며 수치가 없다고 모든 중분류를 무표로 작성하지 않는다. sections 안에 tables를 직접 작성하지 않는다. 수치 근거가 부족하면 해당 중분류의 정성 표를 선택하여 원문에서 확인되는 구조·조건을 정리한다. 확보한 근거가 없는 내용을 임의로 만들지 않는다. 선택한 template_id의 행·열·단위를 바꾸지 않는다. rows가 있는 표의 values는 행명 제외 숫자만 순서대로 채운다. label_rows가 있는 정성 표도 고정 행명은 제외하고 확인 내용·기준 비고만 각 행 순서대로 채운다. 결측값은 null이며 0으로 대체하지 않는다. row_evidence는 values와 동일한 행 순서로 해당 행을 뒷받침하는 원문 자료의 ID(S1 등)를 선택한다. 문구를 작성하지 않는다. 선택한 자료에 실제로 확인되는 항목·수치만 기재한다. 미확인 항목은 확인 불가로 명시하며 추정하지 않는다. 서로 다른 지표를 짜맞추거나 합계를 부문별로 임의 배분하지 않는다. periods에는 실제 대응하는 결산기 3개, basis에는 연결/별도와 기준일을 적는다. 원문 금액은 표의 단위로 정확히 환산하며 다른 기준의 값을 혼합하지 않는다. after_paragraph_index는 해당 목차에서 표 바로 앞 문단의 0부터 시작하는 번호다. 표를 생성했으면 해당 지표를 본문에서 해석한다. 표로 지면만 채우지 않는다. 다른 영역에서 쓴 표를 반복하지 않는다. template_id와 내부 필드명은 본문·basis·셀 내용에 노출하지 않는다.'


def grounded_rows(item, template, aliases):
    """Fail closed for unsupported row excerpts/numbers, retaining real zero."""
    compact=lambda s:re.sub(r'\s+','',s)
    sources=[compact(aliases[s].get('text','')) for s in item['source_ids']]
    output=[]
    for index,row in enumerate(item['values']):
        quotes=item.get('row_evidence',[])
        quote=quotes[index] if index<len(quotes) else ''
        if quote in item['source_ids']:
            quote=aliases[quote].get('text','')
        valid=bool(quote.strip()) and any(compact(quote) in source for source in sources)
        numbers=[float(n.replace(',','')) for n in re.findall(r'(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?',quote)] if valid else []
        # Supported unit conversions: KRW, thousand KRW, million KRW, 100m KRW.
        factors=[1]
        if '백만원' in template['unit']:
            cited=' '.join(aliases[s].get('text','') for s in item['source_ids'])
            if '억원' in cited:factors.append(100)
            if '천원' in cited:factors.append(.001)
            if '단위: 원' in cited or '단위 : 원' in cited:factors.append(.000001)
        def check(v):
            numeric=v
            if isinstance(v,str) and re.fullmatch(r'[-+]?\d[\d,]*(?:\.\d+)?%?',v.strip()):numeric=float(v.strip().rstrip('%').replace(',',''))
            if isinstance(numeric,(float,int)) and not any(abs(numeric-n*f)<1e-6 for n in numbers for f in factors):return None
            return v
        checked=[check(v) for v in row]
        if template.get('rows') or template.get('label_rows'):output.append(checked if valid else [None]*len(row))
        elif valid and any(v is not None for v in checked[1:]):output.append(checked)
    return output

def set_aliases(schema, aliases):
    for option in schema['properties']['report_tables']['items']['anyOf']:
        option['properties']['source_ids']['items']['enum']=list(aliases)
        option['properties']['row_evidence']['items']['enum']=list(aliases)

def apply(result, aliases):
    seen=set();catalog={t['id']:t for t in CATALOG}
    for item in result.pop('report_tables',[]):
        t=catalog[item['template_id']]
        if t['id'] in seen:continue
        seen.add(t['id'])
        item['source_ids']=list(dict.fromkeys(item['source_ids']+[x for x in item.get('row_evidence',[]) if x in aliases]))
        if not set(item['source_ids'])<=set(aliases):raise ValueError('보고서 표 원문 근거 오류')
        section=next(s for s in result['sections'] if s['title']==item['section_title'])
        if not section.get('paragraphs'):raise ValueError('보고서 표 해석 문단 누락')
        fixed=bool(t.get('rows'));values=grounded_rows(item,t,aliases)
        if not values:continue
        labels=t.get('rows') or t.get('label_rows')
        width=len(t['columns'])-int(bool(labels))
        if any(len(row)!=width for row in values):raise ValueError('보고서 표 열 불일치')
        if fixed and len(values)!=len(t['rows']):raise ValueError('보고서 표 행 불일치')
        columns=list(t['columns'])
        if t.get('periods'):columns[1:]=item['periods']
        rows=[[labels[i]]+row for i,row in enumerate(values)] if labels else values
        index=max(0,min(item['after_paragraph_index'],len(section['paragraphs'])-1))
        section.setdefault('tables',[]).append({'template_id':t['id'],'caption':t['title']+' · '+item['basis']+(' (단위: '+t['unit']+')' if t['unit'] not in ('해당 없음','없음','-','') else ''),'columns':columns,'rows':rows,'after_paragraph_index':index,'source_ids':[aliases[x]['id'] for x in item['source_ids']],'report_template':True,'column_widths':t.get('presentation',{}).get('column_widths'),'row_source_ids':[aliases[x]['id'] if x in aliases else None for x in item.get('row_evidence',[])]})
        section['tables'][-1]['caption']=format_caption(section['tables'][-1]['caption'])
        paragraph=section['paragraphs'][index]
        paragraph['source_ids']=list(dict.fromkeys(paragraph['source_ids']+item['source_ids']))
    for section in result['sections']:
        if section.get('tables'):continue
        # Keep data-connection diagnostics out of the report's substantive tables.
        section['tables']=[]
        section['table_gap']={'reason':'표 작성에 필요한 원문 연결을 확보하지 못함','needs_evidence':True}
