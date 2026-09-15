"""Canonicalize unescaped JSON string controls without changing parsed values."""
import ast


def patch(source):
    old="        if response is not None and response['choices'][0].get('finish_reason')!='length':return response"
    new="""        if response is not None and response['choices'][0].get('finish_reason')!='length':
            content=response['choices'][0]['message']['content']
            try:
                json.loads(content)
            except json.JSONDecodeError as error:
                if error.msg.startswith('Invalid control character'):
                    parsed=json.loads(content,strict=False)
                    response=copy.deepcopy(response)
                    response['choices'][0]['message']['content']=json.dumps(parsed,ensure_ascii=False)
                    notify('JSON 문자열 제어문자 이스케이프 복구')
                elif transport_retries<1:
                    notify('JSON 형식 오류: 현재 응답 한 번 재요청')
                    return run(req,depth,transport_retries+1)
                else:
                    raise
            return response"""
    assert source.count(old)==1
    source=source.replace(old,new)
    ast.parse(source)
    return source
