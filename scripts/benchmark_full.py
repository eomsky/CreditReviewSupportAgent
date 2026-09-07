"""Run the full production analysis/synthesis path on previously prepared sources."""
import argparse
import json
import os
import signal
import subprocess
import sys
import uuid
from datetime import date
from pathlib import Path
from time import monotonic

from credit_review.documents import from_json
from credit_review.harness import Harness
from credit_review.llm import ColabClient
from credit_review.grouped import analyse_grouped
from credit_review.parallel import Measurements, MeasuredClient, run_lease
from credit_review.registry import FACTORS
from credit_review.reporting import report_document, report_markdown
from credit_review.store import atomic_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source_run', type=Path)
    parser.add_argument('--hard-timeout', type=float, default=60)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--engine', choices=['queued','prepared'], default='queued')
    parser.add_argument('--concurrency', type=int, choices=range(1,5), default=2)
    args = parser.parse_args()
    if not args.worker:
        return supervise(args)
    state = json.loads((args.source_run/'state.json').read_text())
    artifact = next(args.source_run.glob('artifacts/sources_*.json'))
    sources = from_json(json.dumps(json.loads(artifact.read_text())['payload']).encode())
    client = ColabClient()
    client.check()
    metrics = Measurements()
    h = Harness.create(Path('workspace/benchmarks'), 'full', date.fromisoformat(state['review_date']),
                       sources, MeasuredClient(client, metrics))
    h.state.review_strategy = 'grouped'
    h.save()
    print('BENCHMARK_RUN', h.store.path, flush=True)
    last = monotonic()
    milestone_saved = False
    stage, error, first_token = 'analysis', None, None
    try:
        with run_lease(h):
            if args.engine == 'prepared':
                from credit_review.prepared import analyse_prepared
                engine = analyse_prepared
            else:
                engine = analyse_grouped
            for event in engine(h, list(FACTORS), concurrency=args.concurrency, metrics=metrics,
                                time_budget=args.hard_timeout-15 if args.engine=='prepared' else args.hard_timeout):
                if not milestone_saved and monotonic()-metrics.started >= 60:
                    atomic_json(h.store.path/'milestone_60.json', {
                        'elapsed_seconds':monotonic()-metrics.started,
                        'judgements':sum(bool(f.judgement) for f in h.state.factors.values()),
                        'metrics':metrics.snapshot(), 'stage':'analysis',
                        'note':'First analysis event at or after 60 seconds; excludes preflight and upload/OCR'})
                    milestone_saved = True
                if monotonic()-last >= 10:
                    print(json.dumps({'seconds':round(monotonic()-metrics.started,1),
                        'judgements':sum(bool(f.judgement) for f in h.state.factors.values()),
                        'calls':metrics.snapshot()['llm_calls'], 'active':event['active']}), flush=True)
                    last = monotonic()
            stage = 'synthesis'
            print('SYNTHESIS', round(monotonic()-metrics.started,1), flush=True)
            if args.engine != 'prepared': h.synthesize()
            stage = 'stream'
            client.set_deadline(metrics.started+args.hard_timeout)
            for chunk in (h.stream_synthesis() if args.engine=='prepared' else h.stream_narrative()):
                if first_token is None:
                    first_token = monotonic()-metrics.started
            stage = 'finished'
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
    finally:
        snapshot = metrics.snapshot()
        atomic_json(h.store.path/'performance.json', snapshot)
        summary = {'source_run':str(args.source_run), 'run':str(h.store.path), 'engine':args.engine,
            'model':client.model, 'source_revision':h.state.source_revision,
            'concurrency':args.concurrency,
            'preparation':'Saved PDF extraction reused; includes index construction, excludes upload/OCR and browser rendering',
            'elapsed_seconds':snapshot['elapsed_seconds'], 'first_report_seconds':snapshot['first_report_seconds'],
            'first_final_stream_token_seconds':first_token, 'llm_calls':snapshot['llm_calls'],
            'judgements':sum(bool(f.judgement) for f in h.state.factors.values()),
            'fulfilled':sum(f.status=='FULFILLED' for f in h.state.factors.values()),
            'stage':stage, 'error':error, 'factors':{k:{'status':f.status,'steps':f.steps,'error':f.error}
                for k,f in h.state.factors.items()}}
        quality_path=h.store.path/'quality_review.json'
        summary['quality_review']=json.loads(quality_path.read_text()) if quality_path.exists() else {'status':'NOT_COMPLETED'}
        summary['selective_thinking']=os.environ.get('CREDIT_REVIEW_THINKING','0')=='1'
        atomic_json(h.store.path/'benchmark_summary.json', summary)
        (h.store.path/'report.md').write_text(report_markdown(report_document(h)), encoding='utf-8')
        print('RESULT', json.dumps(summary), flush=True)


def supervise(args):
    """A process boundary also stops a stuck HTTP call or index preparation."""
    root = Path('workspace/benchmarks')
    root.mkdir(parents=True, exist_ok=True)
    name = 'watch_' + uuid.uuid4().hex
    log = root/(name+'.log')
    started = monotonic()
    with log.open('w', encoding='utf-8') as out:
        process = subprocess.Popen([sys.executable, __file__, str(args.source_run),
            '--worker', '--hard-timeout', str(args.hard_timeout), '--engine', args.engine,
            '--concurrency',str(args.concurrency)], stdout=out, stderr=subprocess.STDOUT,
            start_new_session=os.name != 'nt')
        print('WATCHDOG', log, 'limit', args.hard_timeout, flush=True)
        stopped = False
        try:
            process.wait(timeout=args.hard_timeout)
        except subprocess.TimeoutExpired:
            stopped = True
            if os.name == 'nt':
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
    text = log.read_text(encoding='utf-8')
    print(text, flush=True)
    run_line = next((line for line in text.splitlines() if line.startswith('BENCHMARK_RUN ')), None)
    result = {'status':'ABORTED_TIME_BUDGET' if stopped else 'PROCESS_FINISHED',
        'elapsed_seconds':monotonic()-started, 'limit_seconds':args.hard_timeout,
        'exit_code':process.returncode, 'process_stopped':process.poll() is not None,
        'log':str(log), 'report_completed':False}
    if run_line:
        run = Path(run_line.removeprefix('BENCHMARK_RUN '))
        result['run'] = str(run)
        if (run/'state.json').exists():
            state = json.loads((run/'state.json').read_text())
            result['judgements'] = sum(bool(f.get('judgement')) for f in state['factors'].values())
        if (run/'performance.json').exists():
            perf = json.loads((run/'performance.json').read_text())
            result['llm_calls_completed'] = perf['llm_calls']
        if (run/'benchmark_summary.json').exists():
            summary = json.loads((run/'benchmark_summary.json').read_text())
            result['report_completed'] = summary['stage'] == 'finished' and summary['judgements'] == len(FACTORS)
        if stopped:
            atomic_json(run/'benchmark_summary.json', result)
            (run/'.run.lock').unlink(missing_ok=True)  # only after worker exit was confirmed
    atomic_json(root/(name+'.json'), result)
    print('WATCHDOG_RESULT', json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
