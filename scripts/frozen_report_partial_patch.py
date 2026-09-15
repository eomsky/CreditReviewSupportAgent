"""Preserve and review successful report groups after another group fails."""
import ast


def patch(source):
    marker='    def draft_area(item):'
    helper='''    area_failures=[]
    def attempt_area(function,item,phase):
        try:return function(item)
        except api.llm_stream.GenerationCancelled:raise
        except Exception as error:
            i,part=item
            with app.lock:
                area_failures.append({'phase':phase,'area':i,'titles':[p['title'] for p in part],'error':type(error).__name__})
                app.dump(folder/'report.area-failures.json',area_failures)
            if phase=='draft':return i,{'sections':[]},{},[],[]
            titles={p['title'] for p in part}
            return i,{'sections':[copy.deepcopy(s) for s in assembled['sections'] if s['title'] in titles]},[]
'''
    assert source.count(marker)==1
    source=source.replace(marker,helper+marker)
    source=source.replace('pool.map(draft_area,','pool.map(lambda item:attempt_area(draft_area,item,"draft"),')
    source=source.replace('pool.map(review_area,','pool.map(lambda item:attempt_area(review_area,item,"review"),')
    marker='    evidence=list(collected.values())'
    position=source.index(marker)
    source=source[:position]+"    if not assembled['sections']:raise ValueError('모든 보고서 영역 생성 실패: 기록 보존')\n"+source[position:]
    marker="        search_terms=report_table_review.terms(area)"
    source=source.replace(marker,"        if not area['sections']:return i,area,[]\n"+marker)
    marker="    if not layout['target_met']:integration+="
    source=source.replace(marker,"    if area_failures:integration+='\\n일부 영역은 생성 또는 상세검토에 실패했다. 실패 영역을 검토 완료로 간주하지 말고, 현재 확보된 영역만 통합 점검한다. 실패 기록: '+app.json.dumps(area_failures,ensure_ascii=False)\n"+marker)
    source+="\n    if area_failures:raise ValueError('보고서 일부 영역 실패: 나머지 영역 검토 및 산출물 보존 완료')\n"
    ast.parse(source)
    return source
