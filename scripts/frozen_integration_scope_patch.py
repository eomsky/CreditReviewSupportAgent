"""Keep all current claims and their original support in final integration."""
import ast

HELPER='''
def integration_sources(draft,evidence,assessment,manifest):
    ids=set()
    for section in draft.get('sections',[draft]):
        for paragraph in section.get('paragraphs',[]):
            ids.update(s['id'] for s in paragraph.get('sources',[]))
        for table in section.get('tables',[]):
            ids.update(table.get('source_ids',[]))
            binding=table.get('source_binding',{})
            if binding.get('source_id'):ids.add(binding['source_id'])
            ids.update(c['source_id'] for c in table.get('materialized_cells',[]) if c.get('source_id'))
    for row in assessment.get('facts',[])+assessment.get('numeric_evidence',[]):
        ids.update(row.get('source_ids',[]))
    chosen={s['id']:s for s in evidence if s['id'] in ids}
    if ids-set(chosen):raise ValueError('Final integration lacks cited original evidence')
    documents={s['document_id'] for s in chosen.values()}
    for document in manifest:
        if document.get('required') and document['id'] not in documents:
            for source in evidence:
                if source['document_id']==document['id']:
                    chosen[source['id']]=source;documents.add(document['id']);break
    return list(chosen.values())

'''

def patch(source):
    marker='def run(api,payload,folder,state,manifest,outline,generated,check_cancel,cancel_event):'
    assert source.count(marker)==1
    source=source.replace(marker,HELPER+marker)
    marker="    memory={'draft':assembled,'evidence':evidence,'compressed_sources':api.review_refinement.compact_sources(evidence,assembled),'documents':manifest,'prompt':prompt,'prepared_context':evidence_quality.merge(assessments)}"
    assert source.count(marker)==1
    source=source.replace(marker,"""    integration_assessment=evidence_quality.merge(assessments)
    original_evidence_count=len(evidence)
    evidence=integration_sources(assembled,evidence,integration_assessment,manifest)
    app.dump(folder/'report.integration-source-scope.json',{'original_count':original_evidence_count,'included_count':len(evidence),'source_ids':[s['id'] for s in evidence],'rule':'All current paragraph/table citations, numerical/fact ledger sources and required-document coverage. Earlier detailed review evidence retained on disk.'})
    memory={'draft':assembled,'evidence':evidence,'compressed_sources':api.review_refinement.compact_sources(evidence,assembled),'documents':manifest,'prompt':prompt,'prepared_context':integration_assessment}""")
    ast.parse(source)
    return source
