"""Review only unfinished tables; unresolved unchanged rows do not abort an area."""
import ast


def patch(source):
    old="if not t.get('needs_evidence') and not t.get('source_binding')]"
    assert source.count(old)==1
    source=source.replace(old,"if not t.get('needs_evidence') and not t.get('source_binding') and (not t.get('semantic_review_completed') or t.get('quality_version')!=evidence_quality.VERSION)]")
    old="            if any(isinstance(v,(int,float)) for v in values) and not row['source_ids']:raise ValueError('표 수치의 원문 근거 누락')"
    new="""            if any(isinstance(v,(int,float)) for v in values) and not row['source_ids']:
                # Never accept a new unsupported value. Retain the original
                # result and its provenance, explicitly leaving it unverified.
                values=copy.deepcopy(t['rows'][ri])
                row['source_ids']=[reverse[sid] for sid in t.get('source_ids',[]) if sid in reverse]
                gap={'row':ri,'label':str(values[0]),'reason':'이번 검토에서 행 수치의 원문 대응 미확인. 기존 값과 출처를 보존했으며 확인 완료로 간주하지 않음.'}
                t.setdefault('verification_gaps',[]).append(gap)
                candidate['unresolved'].append(gap['label']+': '+gap['reason'])
                row['verification_status']='unresolved_original_retained'
"""
    assert source.count(old)==1
    source=source.replace(old,new.rstrip())
    source=source.replace("        rows=[];cited=[]", "        t.pop('verification_gaps',None)\n        rows=[];cited=[]")
    source=source.replace('semantic_review_completed=True,quality_version=', "semantic_review_completed=not bool(t.get('verification_gaps')),quality_version=")
    marker="        layouts.append({'table_key':identity,**t['layout_review'],'caption':t.get('caption','')})"
    assert source.count(marker)==1
    source=source.replace(marker,"        if t.get('verification_gaps') and '일부 행 원문 확인 필요' not in t['caption']:t['caption']+=' · 일부 행 원문 확인 필요'\n"+marker)
    ast.parse(source)
    return source
