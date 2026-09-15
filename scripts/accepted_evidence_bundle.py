"""Lossless citation deduplication for accepted section reuse, without a model call."""
import copy,hashlib,json
from pathlib import Path
RUNS=['C20.13.1s-step2-replay','C20.18.1s-step4-r1','C20.24s-step6-r1','C20.25.2s-step8-replay','C20.27.1.1s-step10-replay']
def build(root, initial_sources, runs=RUNS):
 sources=copy.deepcopy(initial_sources);sections=[];audit=[]
 def key(s):return (s.get('document_id'),s.get('page'),s.get('text'))
 seen={key(s):s['id'] for s in sources}
 for run in runs:
  folder=Path(root)/'outputs/step_trials'/run
  gate=json.loads((folder/'step-result.json').read_text(encoding='utf-8-sig'))
  if gate['quality_status']!='pass':raise ValueError('Unaccepted section: '+run)
  for name,digest in gate.get('artifact_sha256',{}).items():
   if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=digest:raise ValueError('Accepted artifact changed: '+run)
  path=folder/'reviewed-artifact.json';body=json.loads(path.read_text(encoding='utf-8-sig'));paragraphs=[]
  for para in body['paragraphs']:
   ids=[]
   for original in para.get('sources',[]):
    if not original.get('text') or not original.get('document_id'):raise ValueError('Missing evidence identity')
    k=key(original)
    if k not in seen:
     new=copy.deepcopy(original);new['id']='S'+str(len(sources)+1);sources.append(new);seen[k]=new['id']
    ids.append(seen[k])
   if not ids:raise ValueError('No paragraph evidence: '+run)
   paragraphs.append({'heading':para.get('heading',''),'text':para['text'],'source_ids':list(dict.fromkeys(ids))})
  sections.append({'title':body['title'],'paragraphs':paragraphs,'status':'accepted_interpretation_not_primary_source'})
  audit.append({'run':run,'artifact_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'paragraph_count':len(paragraphs),'gate_hashes_available':bool(gate.get('artifact_sha256'))})
 return sources,sections,audit
