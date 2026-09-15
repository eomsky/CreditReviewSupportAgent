"""Five mandatory summary-II layouts taken from the user's 35929-35931 reference."""
import copy
from table_caption import format_caption

TEMPLATES=[
 {'id':'subsidiaries','topic':3,'caption':'연결대상 종속회사 현황','columns':['기업명','설립월','소재지','지분율(%)','장부가액','사업내용'],'widths':[25,12,13,12,15,23],'unit':'백만원, %'},
 {'id':'financials','topic':3,'caption':'주요 재무현황','columns':['구분','결산기준','자산총계','부채총계','자본총계','매출액','영업이익','순이익','이자비용'],'widths':[7,11,12,12,12,12,12,11,11],'unit':'백만원'},
 {'id':'products','topic':4,'caption':'주요 제품 등의 현황','columns':['사업부문','매출유형','품목','구체적 용도','매출액','비중(%)'],'widths':[15,12,18,27,16,12],'unit':'백만원, %'},
 {'id':'sales','topic':4,'caption':'제품별 내수·수출 매출실적','columns':['사업부문','구분']+['']*7,'widths':[15,9]+[76/7]*7,'unit':'백만원'},
 {'id':'orders','topic':4,'caption':'수주잔고 현황','columns':['사업부문']+['']*6,'widths':[22]+[13]*6,'unit':'억원'},
]

def obj(p):return {'type':'object','properties':p,'required':list(p),'additionalProperties':False}
def arr(item,low,high=None):return {'type':'array','minItems':low,'maxItems':low if high is None else high,'items':item}
def schema():
    text={'type':['string','null']};num={'type':['number','null']};ids={'type':'array','items':{'type':'string'}}
    basis={'type':'string','description':'실제 기준일과 연결/별도 범위. 확인되지 않은 범위는 추정하지 않음'}
    def row(props):return obj({**props,'source_ids':copy.deepcopy(ids)})
    common={'basis':basis,'status':{'type':'string','enum':['확인','확인 필요','해당 없음']}}
    return obj({
      'subsidiaries':obj({**common,'rows':arr(row({'company':text,'established':text,'location':text,'ownership':num,'carrying_amount':num,'business':text}),1,20),'total':row({'carrying_amount':num})}),
      'financials':obj({**common,'periods':arr(text,3),'consolidated':arr(row({'values':arr(num,7)}),2),'separate':arr(row({'values':arr(num,7)}),3)}),
      'products':obj({**common,'rows':arr(row({'business':text,'sales_type':text,'product':text,'use':text,'revenue':num,'share':num}),1,20),'total':row({'revenue':num,'share':num})}),
      'sales':obj({**common,'periods':arr(text,7),'rows':arr(row({'business':text,'export':arr(num,7),'domestic':arr(num,7),'total':arr(num,7)}),1,15),'total':row({'export':arr(num,7),'domestic':arr(num,7),'total':arr(num,7)})}),
      'orders':obj({**common,'periods':arr(text,6),'rows':arr(row({'business':text,'values':arr(num,6)}),1,15),'total':row({'values':arr(num,6)})})})

def configure(target):
    target['properties']['summary2_tables']=schema();target['required'].append('summary2_tables')
    return '\n종합의견2 고정 표 규칙: summary2_tables의 5개 표는 항상 필수이며 삭제하거나 다른 양식으로 바꾸지 않는다. 종속회사 현황과 주요 재무현황은 3. 지배구조 및 관계사, 주요 제품·내수수출 실적·수주잔고는 4. 영업현황에 고정 배치한다. 본문과 별도로 값만 반환한다. 재무현황 periods는 오래된 순 최근 3개년이며 consolidated는 최근 2개년, separate는 최근 3개년 순이다. values는 자산·부채·자본·매출·영업이익·순이익·이자비용 순 백만원이다. 금융비용 전체를 이자비용으로 대체하지 않는다. 매출실적 periods는 최근 7개년, 수주잔고 periods는 최근 6개년을 오래된 순으로 지정하며 확인되지 않는 연도의 값은 null이다. business별 행과 합계를 구분하며 합계는 원문값 또는 검증된 동일범위 합계만 쓴다. 종속회사 지분율·장부가액, 제품 매출액·비중, 실적 내수·수출은 별도 필드로 채운다. 사업부문·기업명은 현재 기업 원문에 있는 것만 사용한다. source_ids는 행별 원문 근거 ID다. 해당 없음은 원문에서 미해당이 확인된 경우만 허용하며 단순 미확인은 확인 필요와 null로 둔다. 모든 값이 미확인이어도 고정 표 자체를 생략하지 않는다.'

def set_aliases(node,aliases):
    if not isinstance(node,dict):return
    for key,value in node.items():
        if key=='source_ids':value['items']['enum']=list(aliases)
        elif isinstance(value,dict):set_aliases(value,aliases)
        elif isinstance(value,list):
            for x in value:set_aliases(x,aliases)

def apply(result,data,anchors):
    for t in TEMPLATES:
        d=data[t['id']];columns=list(t['columns']);rows=[];citations=[]
        def cite(item):citations.extend(item.get('source_ids',[]))
        if t['id']=='subsidiaries':
            for r in d['rows']:rows.append([r[k] for k in ['company','established','location','ownership','carrying_amount','business']]);cite(r)
            total=d.get('total',{});rows.append(['합계',None,None,None,total.get('carrying_amount'),None]);cite(total)
        elif t['id']=='financials':
            for group,periods in [('consolidated',d['periods'][1:]),('separate',d['periods'])]:
                for r,period in reversed(list(zip(d[group],periods))):rows.append(['연결' if group=='consolidated' else '별도',period]+r['values']);cite(r)
        elif t['id']=='products':
            for r in d['rows']:rows.append([r[k] for k in ['business','sales_type','product','use','revenue','share']]);cite(r)
            total=d.get('total',{});rows.append(['합계',None,None,None,total.get('revenue'),total.get('share')]);cite(total)
        elif t['id']=='sales':
            columns[2:]=d['periods']
            for r in d['rows']+[{'business':'합계',**d['total']}]:
                for k,label in [('export','수출'),('domestic','내수'),('total','합계')]:rows.append([r['business'],label]+r[k])
                cite(r)
        else:
            columns[1:]=d['periods']
            for r in d['rows']+[{'business':'합계',**d['total']}]:rows.append([r['business']]+r['values']);cite(r)
        if any(len(row)!=len(columns) for row in rows):raise ValueError('종합의견2 고정 표 열 불일치')
        anchor=anchors[t['topic']]
        title=t['caption']+' · '+d['basis']+' (단위: '+t['unit']+')'
        table={'template_id':'summary2_'+t['id'],'caption':format_caption(title),'columns':columns,'rows':rows,'after_paragraph_index':anchor,'report_template':True,'summary2_fixed_table':True,'column_widths':t['widths'],'source_ids':list(dict.fromkeys(citations)),'status':d['status']}
        result['tables'].append(table)
        p=result['paragraphs'][anchor];p['source_ids']=list(dict.fromkeys(p.get('source_ids',[])+citations))
