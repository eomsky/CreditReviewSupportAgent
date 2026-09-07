"""Bounded diagnostic for source-bound financial preparation, without a report."""
import argparse
from datetime import date
import json
from pathlib import Path
from time import monotonic

from credit_review.documents import from_json
from credit_review.harness import Harness
from credit_review.llm import ColabClient
from credit_review.models import Action
from credit_review.prepared import NUMERIC_INPUTS, PreparedDataset, foundation_context
from credit_review.store import atomic_json


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('source_run',type=Path)
    parser.add_argument('--seconds',type=float,default=45)
    args=parser.parse_args()
    start=monotonic()
    client=ColabClient(); client.check(); client.set_deadline(start+args.seconds)
    source=json.loads(next(args.source_run.glob('artifacts/sources_*.json')).read_text())['payload']
    state=json.loads((args.source_run/'state.json').read_text())
    h=Harness.create(Path('workspace/benchmarks'),'foundation',date.fromisoformat(state['review_date']),
                     from_json(json.dumps(source).encode()),client)
    context=foundation_context(h,NUMERIC_INPUTS)
    parent=h.store.put('prepared_foundation_input',context)
    error=None
    try:
        raw=client.prepare_financial(context)
        output=h.store.put('prepared_foundation_output',{'raw':raw},[parent])
        for item in json.loads(raw)['datasets']:
            item=PreparedDataset.model_validate(item)
            h.apply('F13',Action(action='dataset',reason='Financial preparation diagnostic',
                                dataset=item.dataset,after_dataset=item.after_dataset),output)
    except Exception as exc:
        error=str(exc)
    h.save()
    result={'run':str(h.store.path),'seconds':monotonic()-start,'model':client.model,
            'datasets':h.state.factors['F13'].dataset_ids,'calculations':h.state.factors['F13'].calculation_ids,
            'error':error}
    atomic_json(h.store.path/'diagnostic.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__': main()
