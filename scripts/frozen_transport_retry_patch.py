"""Route transient connection failures through the existing bounded retry."""
import ast

def patch(source):
    source=source.replace('from urllib.error import HTTPError','from urllib.error import HTTPError,URLError\nfrom http.client import RemoteDisconnected,IncompleteRead')
    marker='    with opened as response:'
    assert source.count(marker)==1
    source=source.replace(marker,"    except (URLError,RemoteDisconnected,TimeoutError,ConnectionResetError,IncompleteRead) as error:\n        raise IncompleteStreamError('모델 연결이 응답 전에 중단됨: '+type(error).__name__) from error\n"+marker)
    marker='            result=_read(response,config,progress,cancel_event)'
    # The outer deadline wrapper already distinguishes user cancellation.
    assert source.count(marker)==1
    source=source.replace(marker,"            try:\n                result=_read(response,config,progress,cancel_event)\n            except (URLError,RemoteDisconnected,TimeoutError,ConnectionResetError,IncompleteRead) as error:\n                raise IncompleteStreamError('모델 응답 연결 중단: '+type(error).__name__) from error")
    ast.parse(source)
    return source
