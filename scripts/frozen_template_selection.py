"""Retrieve relevant layout examples; free source-grounded layout design remains."""
import hashlib,json,threading,re

LOCK=threading.RLock()


def select(bases,outline,vector):
    if vector is None or not outline or len(bases)<=6:return bases,{'mode':'unchanged'}
    from qdrant_client import models
    fingerprint=hashlib.sha256(json.dumps([bases,vector.info.get('model_file_hashes',{})],ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:24]
    collection='template_'+fingerprint
    with LOCK:
        if not vector.client.collection_exists(collection):
            profiles=[' '.join([t.get('title',''),t.get('use',''),' '.join(t.get('columns',[])),' '.join(t.get('rows',[]) or t.get('label_rows',[]))]) for t in bases]
            vectors=list(vector.model.embed(profiles,batch_size=16))
            vector.client.create_collection(collection,vectors_config=models.VectorParams(size=384,distance=models.Distance.COSINE))
            vector.client.upsert(collection,points=[models.PointStruct(id=i,vector=v.tolist(),payload={'index':i}) for i,v in enumerate(vectors)])
        selected=[];rankings=[]
        for section in outline:
            query=section['title']+' '+section.get('description','')
            embedding=list(vector.model.query_embed(query))[0].tolist()
            hits=vector.client.query_points(collection,query=embedding,limit=len(bases)).points
            compact=lambda s:re.sub(r'\s+','',s)
            needle=compact(section['title'])
            pairs=lambda s:{s[i:i+2] for i in range(len(s)-1)}
            query_pairs=pairs(needle)
            def relevance(hit):
                item=bases[hit.payload['index']]
                labels=[compact(item.get(k,'')) for k in ('title','use')]
                exact=bool(needle) and any(needle in label for label in labels)
                overlap=max((len(query_pairs & pairs(label))/max(1,len(query_pairs)) for label in labels),default=0)
                return hit.score+2.5*exact+1.2*overlap+(.2 if item.get('industry')=='common' else 0)
            ranking=[h.payload['index'] for h in sorted(hits,key=relevance,reverse=True)[:6]];rankings.append(ranking)
            for index in ranking[:2]:
                if index not in selected:selected.append(index)
        limit=max(6,len(outline)*2)
        for rank in range(2,6):
            for ranking in rankings:
                if rank<len(ranking) and ranking[rank] not in selected:selected.append(ranking[rank])
                if len(selected)>=limit:break
            if len(selected)>=limit:break
    choices=[bases[i] for i in selected]
    return choices,{'mode':'hybrid_layout_examples','collection':collection,'total_templates':len(bases),'selected':[t.get('id',t.get('title')) for t in choices],'custom_layouts_allowed':True}
