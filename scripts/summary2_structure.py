"""Topic-complete summary II, flattened to the existing report UI contract."""
import re
import copy
import summary2_fixed_tables
from pathlib import Path

TOPICS=['평가 개요','1. 업체개요','2. 경영현황','3. 지배구조 및 관계사','4. 영업현황','5. 우발적 재무위험','6. 종합의견']
GROUPS=[['감사의견','신용평가사유','대출신청'],['회사의개요','설립일','주요연혁'],['대표이사','경영진','임원현황'],['최대주주','주주현황'],['연결대상종속회사','종속기업의현황','주요종속','소재지'],['요약연결재무정보','요약별도재무정보'],['주요제품','사업부문별'],['매출실적','내수','수출'],['수주잔고','수주상황'],['소송','제재','입찰'],['지급보증','우발상황','약정사항']]
def rules():
    return (Path(__file__).resolve().parents[1]/'prompts/summary2_depth.txt').read_text(encoding='utf-8')

def configure(schema, paragraph, planned=False):
    item={'type':'object','properties':{
        'paragraphs':{'type':'array','minItems':1,'items':copy.deepcopy(paragraph)},
        'tables':{'type':'array','items':{'type':'object','properties':{
            'caption':{'type':'string'},'columns':{'type':'array','minItems':1,'items':{'type':'string'}},
            'rows':{'type':'array','minItems':1,'items':{'type':'array','items':{'type':['string','number','null']}}},
            'after_paragraph_index':{'type':'integer','minimum':0}},
            'required':['caption','columns','rows','after_paragraph_index'],'additionalProperties':False}}},
        'required':['paragraphs','tables'],'additionalProperties':False}
    schema['properties'].pop('paragraphs',None)
    schema['required']=[k for k in schema['required'] if k!='paragraphs']+['topics']
    schema['properties']['topics']={'type':'object','properties':{f't{i}':copy.deepcopy(item) for i in range(len(TOPICS))},'required':[f't{i}' for i in range(len(TOPICS))],'additionalProperties':False}
    subtopics=[['','평가 사유 및 신청조건','점검사항','외부감사 및 신용등급'],['','기업 기본사항','주요 연혁','사업장 및 생산기반'],['','대표자 및 경영진','경영체제','경영권 변동 및 사업 연속성'],['','주요 주주 및 지배구조','연결대상 종속회사','관계사 재무현황 및 지원 부담','주요 재무현황'],['','사업개요','주요 제품 및 판매구조','제품별 매출실적','주요 고객 및 매출집중','수주잔고 및 전망'],['','소송 및 제재','보증 및 약정 부담','기타 우발위험'],['','주요 심사쟁점','상환재원 및 확인조건']]
    for i,topic in enumerate(schema['properties']['topics']['properties'].values()):
        if 'heading' in topic['properties']['paragraphs']['items']['properties']:topic['properties']['paragraphs']['items']['properties']['heading']={'type':'string','enum':subtopics[i]}
        topic['properties'].pop('tables');topic['required'].remove('tables')
    table_rules='' if planned else summary2_fixed_tables.configure(schema)
    return table_rules+'\n'+rules()+'\nJSON 출력: topics의 t0~t6은 위 7개 목차 순서이며 모두 필수다. 각 paragraphs는 세부 논점별 문단이고 heading은 세부 제목이다. 한 목차를 하나의 요약 문단으로 압축하지 말고 업체 기본사항과 주요 연혁, 주주구조와 관계사 현황 및 노출, 제품과 매출 변동 및 고객 구조와 수주 전망, 소송과 약정 부담을 각각 독립 논점으로 작성한다. 자료가 부족하면 근거 없는 문단을 늘리지 않는다. 표는 JSON 스키마에 정의된 표 필드에 작성한다. anchor_topic이 있으면 표 내용과 연결되는 목차 번호를 선택하고 after_paragraph_index는 그 목차 안에서 표 바로 앞 문단의 0부터 시작하는 번호다. 관계사 표는 관계사 논점에, 영업 표는 해당 영업 논점에 배치하며 모든 표를 평가 개요에 몰아넣지 않는다.'

def set_aliases(schema, aliases):
    if 'summary2_tables' in schema['properties']:summary2_fixed_tables.set_aliases(schema['properties']['summary2_tables'],aliases)
    subtopics=[['','평가 사유 및 신청조건','점검사항','외부감사 및 신용등급'],['','기업 기본사항','주요 연혁','사업장 및 생산기반'],['','대표자 및 경영진','경영체제','경영권 변동 및 사업 연속성'],['','주요 주주 및 지배구조','연결대상 종속회사','관계사 재무현황 및 지원 부담','주요 재무현황'],['','사업개요','주요 제품 및 판매구조','제품별 매출실적','주요 고객 및 매출집중','수주잔고 및 전망'],['','소송 및 제재','보증 및 약정 부담','기타 우발위험'],['','주요 심사쟁점','상환재원 및 확인조건']]
    for i,topic in enumerate(schema['properties']['topics']['properties'].values()):
        if 'heading' in topic['properties']['paragraphs']['items']['properties']:topic['properties']['paragraphs']['items']['properties']['heading']={'type':'string','enum':subtopics[i]}
        topic['properties']['paragraphs']['items']['properties']['source_ids']['items']['enum']=list(aliases)

def flatten(result):
    topics=result.pop('topics');paragraphs=[];tables=[];anchors={}
    for i,title in enumerate(TOPICS):
        topic=topics[f't{i}'];rows=topic['paragraphs']
        if not rows:raise ValueError('종합의견2 필수 목차 누락')
        start=len(paragraphs)
        for j,p in enumerate(rows):
            sub=re.sub(r'^(?:[가-하]|\d+)[.)]\s*','',p.get('heading','').strip())
            p['topic_title']=title;p['topic_index']=i;p['subheading']=sub
            bare=title.split('. ',1)[-1]
            p['subheading']='' if sub in (title,bare) else sub
            p['heading']=title+(' · '+sub if sub and sub not in (title,bare) else '') if j==0 else sub
            paragraphs.append(p)
        anchors[i]=len(paragraphs)-1
        for table in topic.get('tables',[]):
            if any(len(row)!=len(table['columns']) for row in table['rows']):raise ValueError('종합의견2 표 열 불일치')
            before=table.pop('after_paragraph_index')
            # An out-of-range placement must not discard an otherwise complete report.
            before=max(0,min(before,len(rows)-1))
            table['after_paragraph_index']=start+before
            tables.append(table)
    result['paragraphs']=paragraphs;result['tables']=tables
    fixed=result.pop('summary2_tables',None)
    if fixed is not None:summary2_fixed_tables.apply(result,fixed,anchors)
