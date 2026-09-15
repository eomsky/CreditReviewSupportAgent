"""C18: compute comparable changes from the exact displayed table before drafting."""
import ast

def patch(source):
    marker="    payload = {'model':app.config()['model'], 'messages':messages,"
    assert source.count(marker)==1
    extra='''    if packet.get('preparation_mode')=='combined_with_generation':
        import json
        from decimal import Decimal
        table_changes=[]
        for table_id,table in joint_tables.items():
            template=bases[int(table_id[1:])]
            periods=table['periods']
            for i,label in enumerate(template['labels']):
                values=table['r'+str(i)]
                if len(periods)>=2 and len(values)>=len(periods):
                    end=len(periods)-1
                    table_changes.append({'item':label,'from':periods[end-1],'to':periods[end],
                        'change':str(Decimal(str(values[end]))-Decimal(str(values[end-1]))),
                        'source_id':table['source_id']})
        app.dump(run_dir/(name+'.table-changes.json'),table_changes)
        messages[0]['content']+='\\n표와 본문은 같은 수치 기준이어야 한다. 아래는 표시할 고정표의 전기→당기 차액이다(단위는 해당 고정표와 동일). 동일 항목 증감을 서술할 때 이 표 기준으로 쓰고, 상세 원문 증감열이 다르면 기준 차이를 밝히거나 해당 세부증감 서술을 생략한다. 잔액 증가는 취득·매각·재평가·연결범위 등 여러 요인으로 발생하므로 취득 근거 없이 투자집행으로 확정하지 않는다. 회전기간의 단축은 회전속도의 변화까지만 판단하며 회수나 관리의 우수성을 단정하지 않는다. ' + json.dumps(table_changes,ensure_ascii=False)
'''
    source=source.replace(marker,extra+marker)
    ast.parse(source)
    return source
