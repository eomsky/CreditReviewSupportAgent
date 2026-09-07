"""Read-only report projection; never loads an LLM or rebuilds a PDF index."""
import json
from types import SimpleNamespace
from .models import ReviewState
from .store import identifier
from .reporting import report_document, report_markdown


class ReadOnlyArtifacts:
    def __init__(self, path):
        self.path = path

    def get(self, aid):
        return json.loads((self.path/'artifacts'/f'{identifier(aid)}.json').read_text(encoding='utf-8'))


def latest_snapshot(root):
    paths = list((root/'benchmarks'/'cases'/'full'/'runs').glob('run_*/state.json'))
    if not paths:
        return None
    path = max(paths, key=lambda p:p.parent.stat().st_mtime_ns)
    state = ReviewState.model_validate_json(path.read_text(encoding='utf-8'))
    h = SimpleNamespace(state=state, store=ReadOnlyArtifacts(path.parent))
    summary_path = path.parent/'benchmark_summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8')) if summary_path.exists() else {}
    active = (path.parent/'.run.lock').exists() and not summary
    finished = summary.get('report_completed') or summary.get('stage') == 'finished'
    return {'run_id':state.run_id, 'active':active, 'finished':bool(finished),
            'report':report_markdown(report_document(h)),
            'opinions':sum(bool(f.judgement) for f in state.factors.values())}
