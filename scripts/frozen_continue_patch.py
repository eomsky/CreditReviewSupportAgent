"""Keep independent requested work running after a per-item failure."""
import ast


def patch(source):
    marker='        memories = {}'
    extra='''        successful_operations=set()
        failed_operations=[]
        def attempt(function,item,phase):
            key=item[1]
            try:
                function(item)
            except llm_stream.GenerationCancelled:
                raise
            except Exception as error:
                reason=str(error) if isinstance(error,(DocumentError,llm_recovery.CapacityError,ValueError)) else app.clean_error(error)
                with app.lock:
                    failed_operations.append({'phase':phase,'key':key,'error':reason})
                    state['run']['failed_steps']=copy.deepcopy(failed_operations)
                    app.dump(folder/'partial-failures.json',failed_operations)
                    persist_case(state)
            else:
                with app.lock:successful_operations.add((phase,key))
            finally:
                with app.lock:state['run']['completed_calls']=len(successful_operations)
'''
    assert source.count(marker)==1
    source=source.replace(marker,marker+'\n'+extra)
    source=source.replace('pool.map(draft_one,independent)','pool.map(lambda item:attempt(draft_one,item,"draft"),independent)')
    source=source.replace('            draft_one(item)','            attempt(draft_one,item,"draft")')
    source=source.replace('pool.map(review_one,list(enumerate(review_targets)))','pool.map(lambda item:attempt(review_one,item,"review"),list(enumerate(review_targets)))')
    old='            report_pipeline.run(sys.modules[__name__],payload,folder,state,manifest,outline,generated,check_cancel,cancel_event)'
    assert source.count(old)==1
    source=source.replace(old,'            attempt(lambda _:report_pipeline.run(sys.modules[__name__],payload,folder,state,manifest,outline,generated,check_cancel,cancel_event),(0,"report"),"report")')
    marker="            app.dump(folder/'result.json', state)"
    extra='''            if failed_operations:
                verified=sum(1 for phase,key in successful_operations if phase!='report')
                if ('report','report') in successful_operations:verified+=len(report_pipeline.groups(outline))*2+1
                state['run'].update(status='failed',stage='전체 시도 종료 · 일부 실패',completed_calls=verified,
                                    error='일부 항목 실패. 완료 산출물과 실패 항목을 보존했습니다.',failed_steps=copy.deepcopy(failed_operations))
'''
    assert source.count(marker)==1
    source=source.replace(marker,extra+marker)
    ast.parse(source)
    return source
