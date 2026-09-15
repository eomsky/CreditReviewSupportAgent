"""Join accepted report areas with collision-free citation identities."""
import copy,hashlib,json,time
from pathlib import Path

def main():
 root=Path(__file__).resolve().parents[1];out=root/'outputs/step_trials/C20.33-step16-review';out.mkdir(exist_ok=False);start=time.perf_counter()
 read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
 save=lambda p,d:p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
 runs=['C20.30.3.1-step13-replay','C20.31-step14-input','C20.32.2-step15-repair']
 sources=[];known={};sections=[];lineage=[];used_ids=set()
 for run in runs:
  folder=root/'outputs/step_trials'/run;gate=read(folder/'step-result.json');assert gate['quality_status']=='pass'
  for n,h in gate['artifact_sha256'].items():assert hashlib.sha256((folder/n).read_bytes()).hexdigest()==h
  body=read(folder/'materialized-artifact.json');mapping={}
  for source in body['sources']:
   key=(source.get('document_id'),source.get('page'),source['text'])
   if key not in known:
    mapped=copy.deepcopy(source);mapped['id']=f'S{len(sources)+1}';known[key]=mapped['id'];sources.append(mapped)
   mapping[source['id']]=known[key]
  source_map={s['id']:s for s in sources}
  for original in body['sections']:
   section=copy.deepcopy(original)
   for p in section['paragraphs']:
    assert p['id'] not in used_ids;used_ids.add(p['id'])
    p['source_ids']=list(dict.fromkeys(mapping[s] for s in p['source_ids']))
    p['sources']=[source_map[s] for s in p['source_ids']]
   for t in section['tables']:t['source_ids']=list(dict.fromkeys(mapping[s] for s in t['source_ids']))
   sections.append(section)
  lineage.append({'run':run,'sha256':hashlib.sha256((folder/'materialized-artifact.json').read_bytes()).hexdigest(),'source_id_map':mapping})
 expected=['업체개요','사업성','수익성','재무안정','상환능력','채권보전','종합 심사의견']
 assert [s['title'] for s in sections]==expected
 report={'sections':sections,'sources':sources,'draft':True}
 save(out/'materialized-artifact.json',report);save(out/'assembly-lineage.json',lineage)
 candidates=[{'section':s['title'],'id':p['id'],'text':p['text']} for s in sections for p in s['paragraphs'] if any(term in p['text'] for term in ['미확인','확인되지','자료가 부족','근거가 부족'])]
 save(out/'new-evidence-impact-candidates.json',candidates)
 save(out/'assembly-audit.json',{'elapsed_seconds':time.perf_counter()-start,'sections':len(sections),'paragraphs':len(used_ids),'tables':sum(len(s['tables']) for s in sections),'sources':len(sources),'all_parents_accepted':True,'text_table_values_preserved':True,'end_to_end':False,'quality_status':'requires_cross_area_review'})
 print(json.dumps(read(out/'assembly-audit.json')))
 print(json.dumps(candidates,ensure_ascii=False))

if __name__=='__main__':main()
