"""Run the full production analysis/synthesis path on previously prepared sources."""
import argparse
import json
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
    args = parser.parse_args()
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
    stage, error, first_token = 'analysis', None, None
    try:
        with run_lease(h):
            for event in analyse_grouped(h, list(FACTORS), concurrency=2, metrics=metrics):
                if monotonic()-last >= 30:
                    print(json.dumps({'seconds':round(monotonic()-metrics.started,1),
                        'judgements':sum(bool(f.judgement) for f in h.state.factors.values()),
                        'calls':metrics.snapshot()['llm_calls'], 'active':event['active']}), flush=True)
                    last = monotonic()
            stage = 'synthesis'
            print('SYNTHESIS', round(monotonic()-metrics.started,1), flush=True)
            h.synthesize()
            stage = 'stream'
            for chunk in h.stream_narrative():
                if first_token is None:
                    first_token = monotonic()-metrics.started
            stage = 'finished'
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
    finally:
        snapshot = metrics.snapshot()
        atomic_json(h.store.path/'performance.json', snapshot)
        summary = {'source_run':str(args.source_run), 'run':str(h.store.path),
            'model':client.model, 'source_revision':h.state.source_revision,
            'preparation':'Saved PDF extraction reused; includes index construction, excludes upload/OCR and browser rendering',
            'elapsed_seconds':snapshot['elapsed_seconds'], 'first_report_seconds':snapshot['first_report_seconds'],
            'first_final_stream_token_seconds':first_token, 'llm_calls':snapshot['llm_calls'],
            'judgements':sum(bool(f.judgement) for f in h.state.factors.values()),
            'fulfilled':sum(f.status=='FULFILLED' for f in h.state.factors.values()),
            'stage':stage, 'error':error, 'factors':{k:{'status':f.status,'steps':f.steps,'error':f.error}
                for k,f in h.state.factors.items()}}
        atomic_json(h.store.path/'benchmark_summary.json', summary)
        (h.store.path/'report.md').write_text(report_markdown(report_document(h)), encoding='utf-8')
        print('RESULT', json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
