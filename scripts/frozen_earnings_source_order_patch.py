"""C20.3: prioritize complete original earnings excerpts without dropping sources."""
import ast

def patch(source):
    marker="    payload = {'model':app.config()['model'], 'messages':messages,"
    extra='''    if packet.get('preparation_mode')=='combined_with_generation':
        for message in messages:
            if message.get('role')!='user':continue
            try:body=app.json.loads(message['content'])
            except (ValueError,TypeError):continue
            original=body.get('sources')
            if not isinstance(original,list):continue
            def earnings_priority(item):
                text=str(item.get('text',''))
                return bool(re.search(r'법인세|income tax|tax expense',text,re.I)) and bool(re.search(r'차감전|세전|before tax|pretax|pre-tax',text,re.I))
            body['sources']=sorted(original,key=lambda item:not earnings_priority(item))
            app.dump(run_dir/(name+'.source-order.json'),{'before':[s['id'] for s in original],'after':[s['id'] for s in body['sources']], 'all_original_sources_preserved':True})
            message['content']=app.json.dumps(body,ensure_ascii=False)
'''
    assert source.count(marker)==1
    source=source.replace(marker,extra+marker)
    ast.parse(source)
    return source
