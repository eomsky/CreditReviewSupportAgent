"""Isolated recorded-request trials; past/accepted steps cannot call the model again.

This tests one model call, not the downstream renderer or the full pipeline.
Quality decisions require separately recorded evidence, never just JSON success.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def initialize(folder, request, target, past_response=None):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    save(folder / 'request.json', read(request))
    state = dict(status='pending', target_seconds=target, attempts=[],
                 end_to_end=False, scope='single_model_call', retrieval_default='vector_db',
                 request_sha256=digest(folder / 'request.json'))
    if past_response:
        save(folder / 'preserved-response.json', read(past_response))
        state.update(status='past_preserved', quality='unassessed',
                     response_sha256=digest(folder / 'preserved-response.json'))
    save(folder / 'state.json', state)


def trial(folder, code, invoke=None, timeout=600):
    folder, code = Path(folder), Path(code)
    state = read(folder / 'state.json')
    if state['status'] in ('pass', 'past_preserved'):
        return {'reused': True, 'status': state['status']}
    if state['status'] not in ('pending', 'fail'):
        raise ValueError('Judge the current attempt before repeating this step')
    attempt = folder / f"attempt-{len(state['attempts']) + 1:03}"
    attempt.mkdir(exist_ok=False)
    request = read(folder / 'request.json')
    save(attempt / 'request.json', request)
    state['status'] = 'running'
    state['attempts'].append(attempt.name)
    save(folder / 'state.json', state)
    began = time.monotonic()
    result = {'end_to_end': False, 'scope': 'single_model_call',
              'request_sha256': digest(attempt / 'request.json')}
    try:
        if invoke is None:
            sys.path[:0] = [str(code / 'code/scripts'), str(code / 'harness')]
            import llm_stream
            result['transport_sha256'] = digest(Path(llm_stream.__file__))
            last_snapshot = [0.0]
            def record_progress(delta, text):
                now = time.monotonic()
                if now-last_snapshot[0] >= 1:
                    last_snapshot[0] = now
                    save(attempt / 'progress.json', {'elapsed_seconds':round(now-began,3),
                         'received_characters':len(text),'status':'streaming','complete':False})
                    (attempt / 'partial-response.txt').write_text(text,encoding='utf-8')
            response = llm_stream.complete(read(ROOT / 'workspace/llm_connection.json'),
                                           request, record_progress, timeout=timeout)
        else:
            response = invoke(request)
        save(attempt / 'response.json', response)
        finish = response['choices'][0].get('finish_reason')
        result.update(finish_reason=finish, usage=response.get('usage'))
        if finish != 'stop':
            raise ValueError('Incomplete model response')
        result['status'] = 'awaiting_quality_review'
    except Exception as exc:
        # Transport errors may contain endpoint credentials. Record only type.
        result.update(status='fail', error_type=type(exc).__name__)
        cause=exc.__cause__
        if cause is not None:result['cause_type']=type(cause).__name__
        message=str(exc)
        for prefix,code in [('응답 스트림이 완료되기 전에','stream_missing_finish'),('모델 응답 대기시간 초과','stream_idle_or_deadline'),('모델 연결이 응답 전에','connection_before_response'),('모델 응답 연결 중단','connection_during_response')]:
            if message.startswith(prefix):result['transport_error_code']=code;break
    result['elapsed_seconds'] = round(time.monotonic() - began, 3)
    result['time_target_met'] = result['elapsed_seconds'] <= state['target_seconds']
    result['time_status'] = ('fail' if result['status'] == 'fail' else 'pass' if result['time_target_met'] else 'provisional_pass' if result['elapsed_seconds'] <= state['target_seconds'] + 40 else 'fail')
    save(attempt / 'result.json', result)
    state['status'] = result['status']
    save(folder / 'state.json', state)
    return result


def judge(folder, passed, evidence):
    folder, evidence = Path(folder), Path(evidence)
    state = read(folder / 'state.json')
    if state['status'] != 'awaiting_quality_review':
        raise ValueError('Only a completed, unjudged attempt can be assessed')
    if not evidence.is_file() or not evidence.read_text(encoding='utf-8').strip():
        raise ValueError('A written source-grounded quality assessment is required')
    attempt = folder / state['attempts'][-1]
    result = read(attempt / 'result.json')
    if passed and result['elapsed_seconds'] > state['target_seconds'] + 40:
        raise ValueError('Time target plus 40-second tolerance missed')
    (attempt / 'quality-evidence.md').write_text(evidence.read_text(encoding='utf-8'), encoding='utf-8')
    state['time_status'] = 'pass' if result['time_target_met'] else 'provisional_pass' if result['elapsed_seconds'] <= state['target_seconds'] + 40 else 'fail'
    state.update(status='pass' if passed else 'fail', quality='pass' if passed else 'fail')
    save(folder / 'state.json', state)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('folder'); init.add_argument('request')
    init.add_argument('--target', type=float, required=True)
    init.add_argument('--past-response')
    run = sub.add_parser('run')
    run.add_argument('folder'); run.add_argument('--code', required=True)
    assessment = sub.add_parser('judge')
    assessment.add_argument('folder'); assessment.add_argument('--evidence', required=True)
    assessment.add_argument('--passed', action='store_true')
    args = parser.parse_args()
    if args.command == 'init': initialize(args.folder, args.request, args.target, args.past_response)
    elif args.command == 'run': print(json.dumps(trial(args.folder, args.code), ensure_ascii=False))
    else: judge(args.folder, args.passed, args.evidence)
