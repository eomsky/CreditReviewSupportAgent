"""Bounded live smoke benchmark on saved evidence; never modifies the source run."""
import argparse
import json
from pathlib import Path
from time import monotonic
from datetime import date

from credit_review.documents import from_json
from credit_review.harness import Harness
from credit_review.llm import ColabClient
from credit_review.grouped import group_context, apply_group_reply
from credit_review.parallel import MeasuredClient, Measurements
from credit_review.store import atomic_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source_run', type=Path)
    parser.add_argument('--targets', nargs='+', default=['F01','F02','F03'])
    parser.add_argument('--rounds', type=int, default=3)
    args = parser.parse_args()
    state = json.loads((args.source_run/'state.json').read_text())
    artifact = next(args.source_run.glob('artifacts/sources_*.json'))
    sources = from_json(json.dumps(json.loads(artifact.read_text())['payload']).encode())
    metrics = Measurements()
    h = Harness.create(Path('workspace/benchmarks'), 'grouped', date.fromisoformat(state['review_date']),
                       sources, MeasuredClient(ColabClient(), metrics))
    for fid in args.targets:
        h.prepare_evidence(fid)
    print('BENCHMARK_RUN', h.store.path, flush=True)
    for i in range(args.rounds):
        pending = [fid for fid in args.targets if not h.state.factors[fid].judgement]
        if not pending:
            break
        context = group_context(h, pending)
        parent = h.store.put('group_input', context)
        raw = h.client.next_actions(context)
        response = h.store.put('group_output', {'raw':raw}, [parent])
        apply_group_reply(h, pending, raw, response)
        h.save()
        completed = sum(bool(h.state.factors[f].judgement) for f in args.targets)
        if completed and metrics.first_report_seconds is None:
            metrics.first_report_seconds = monotonic()-metrics.started
        print(json.dumps({'round':i+1,'completed':completed,'total':len(args.targets),
                          'elapsed':round(monotonic()-metrics.started,2)}), flush=True)
    atomic_json(h.store.path/'performance.json', metrics.snapshot())
    print(json.dumps(metrics.snapshot()), flush=True)


if __name__ == '__main__':
    main()
