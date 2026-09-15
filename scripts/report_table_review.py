"""Re-retrieve original evidence and repair missing report table cells during review."""
import re
import copy

ALIASES={'매출총이익':['매출총손익'],'법인세차감전순이익':['법인세비용차감전순이익','법인세비용차감전계속사업이익','세전이익'],'당기순이익':['당기순손익','당기순이익(손실)','당기순손실'],'금융비용':['이자비용','이자비용및금융비용']}
ALIASES.update({'영업활동으로인한현금흐름':['영업활동으로 인한 현금흐름','영업활동현금흐름'],
 '투자활동으로인한현금흐름':['투자활동으로 인한 현금흐름','투자활동현금흐름'],
 '재무활동으로인한현금흐름':['재무활동으로 인한 현금흐름','재무활동현금흐름'],
 '기말 현금및현금성자산':['기말의현금및현금성자산','기말현금및현금성자산']})

def sections(draft):return draft.get('sections',[draft])

def missing(draft):
    cells={}
    for si,s in enumerate(sections(draft)):
        for ti,t in enumerate(s.get('tables',[])):
            if t.get('needs_evidence'):continue
            if t.get('semantic_review_completed'):continue
            if not t.get('columns'):continue
            if any('매출처' in str(c) for c in t.get('columns',[])):continue # Restored from original XLSX cell coordinates.
            template=t.get('template_id','')
            for ri,row in enumerate(t.get('rows',[])):
                for ci,value in enumerate(row[1:],1):
                    label=row[0];period=t['columns'][ci];kind='number'
                    if template=='summary2_subsidiaries':
                        if row[0]=='합계' and ci!=4:continue
                        label=str(row[0]);kind='number' if ci in (3,4) else 'text'
                    elif template=='summary2_financials':
                        if ci<2:continue
                        label=t['columns'][ci];period=str(row[1]);
                    elif template=='summary2_products':
                        if row[0]=='합계' and ci not in (4,5):continue
                        kind='number' if ci in (4,5) else 'text'
                    elif template=='summary2_sales' and ci<2:continue
                    if not row[0]:continue
                    if value is None or value in ('','—','-') or value==-1 and template in ('summary2_sales','summary2_orders'):
                        cells[f'T{si}_{ti}_{ri}_{ci}']={'section':si,'table':ti,'row':ri,'column':ci,'label':label,'period':period,'basis':t.get('caption',''),'value_type':kind,'field':t['columns'][ci]}
    return cells

def terms(draft):
    result=[]
    for c in missing(draft).values():
        result.extend([re.sub(r'\s+','',str(c['label'])),str(c['period'])[:4]])
        result.extend(ALIASES.get(c['label'],[]))
    return list(dict.fromkeys(result))

def retrieve(store,draft,manifest):
    found={}
    labels=list(dict.fromkeys(c['label'] for c in missing(draft).values()))
    for label in labels:
        aliases=[re.sub(r'\s+','',x) for x in [label]+ALIASES.get(label,[])]
        # Search each missing measure independently; common years must not crowd it out.
        for source in store.select(aliases,manifest,budget=12000,limit=8):found[source['id']]=source
    # Include nearby table headers so period order and monetary unit are available.
    for source in list(found.values()):
        for header in store.get(source['document_id'])['sources']:
            same=source.get('page') is not None and header.get('page') is not None and 0<=source['page']-header['page']<=2
            same=same or source.get('sheet') is not None and header.get('sheet')==source['sheet']
            if same and re.search(r'단위\s*:',header['text']) and re.search(r'20\d{2}',header['text']):
                found.setdefault(header['id'],{**header,'metadata':source.get('metadata',{})})
    return list(found.values())

def add_schema(schema,draft,evidence):
    if draft.get('semantic_table_review'):return
    cells=missing(draft)
    if not cells:return
    props={'cell_id':{'type':'string','enum':list(cells)},'value':{'type':['number','string','null']},'source_ids':{'type':'array','items':{'type':'string','enum':[s['id'] for s in evidence]}},'reason':{'type':'string'}}
    schema['properties']['table_cell_reviews']={'type':'array','minItems':len(cells),'maxItems':len(cells),'items':{'type':'object','properties':props,'required':list(props),'additionalProperties':False}}
    schema['required'].append('table_cell_reviews')

def apply(result,response,evidence):
    if result.get('semantic_table_review'):return
    cells=missing(result)
    if not cells:return
    reviews=response.get('table_cell_reviews',[])
    if len(reviews)!=len(cells) or {x['cell_id'] for x in reviews}!=set(cells):raise ValueError('표 검토에서 일부 빈 셀이 누락되거나 중복되었습니다.')
    sources={s['id']:s for s in evidence};audit=[]
    for change in reviews:
        c=cells[change['cell_id']];ids=change['source_ids']
        if not set(ids)<=sources.keys():raise ValueError('표 보완 근거 ID 오류')
        # Resolve units from the same original table's page/sheet header.
        for sid in list(ids):
            src=sources[sid]
            for header in evidence:
                same=src.get('page') is not None and header.get('page') is not None and 0<=src['page']-header['page']<=2
                same=same or src.get('sheet') is not None and header.get('sheet')==src['sheet']
                if header.get('document_id')==src.get('document_id') and same and re.search(r'단위\s*:',header['text']) and re.search(r'20\d{2}',header['text']):
                    if header['id'] not in ids:ids.append(header['id'])
        value=change['value'];t=sections(result)[c['section']]['tables'][c['table']]
        if t.get('template_id') in ('summary2_sales','summary2_orders') and t['rows'][c['row']][c['column']]==-1:
            t['rows'][c['row']][c['column']]=None
        accepted=value is not None and bool(ids)
        raw='\n'.join(sources[x]['text'] for x in ids)
        aliases=[c['label']]+ALIASES.get(c['label'],[])
        measure_lines=[line for line in raw.splitlines() if any(re.search(r'(?:^|=|[Ⅰ-Ⅹ.])\s*'+r'\s*'.join(re.escape(x) for x in re.sub(r'\s+','',label))+r'(?:\([^)]*\))?(?:\s|\||$)',line) for label in aliases)]
        values=[float(x.replace(',','')) for x in re.findall(r'(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?',' '.join(measure_lines))]
        factors=[1]
        if '백만원' in t.get('caption',''):
            if '억원' in raw:factors.append(100)
            if '천원' in raw:factors.append(.001)
            if re.search(r'(?:^|\n)\s*\(?단위\s*:\s*원',raw):factors.append(.000001)
        if c['value_type']=='text':
            accepted=accepted and isinstance(value,str) and re.sub(r'\s+','',value) in re.sub(r'\s+','',raw) and re.sub(r'\s+','',c['label']) in re.sub(r'\s+','',raw)
        elif not isinstance(value,(int,float)) or isinstance(value,bool):accepted=False
        elif accepted and not any(abs(value-n*f)<(.500001 if f!=1 and float(value).is_integer() else 1e-6) for n in values for f in factors):accepted=False
        if accepted:
            t['rows'][c['row']][c['column']]=value
            t['source_ids']=list(dict.fromkeys(t.get('source_ids',[])+ids))
            paras=sections(result)[c['section']].get('paragraphs',[])
            if paras:
                p=paras[max(0,min(t.get('after_paragraph_index',0),len(paras)-1))]
                p['sources']=list({s['id']:s for s in p.get('sources',[])+[copy.deepcopy(sources[x]) for x in ids]}.values())
        audit.append({**c,'value':value if accepted else None,'source_ids':ids,'status':'filled' if accepted else 'unresolved','reason':change['reason'] if accepted or value is None else '제시 수치의 원문 연결 재확인 필요'})
    result['table_review']=audit
