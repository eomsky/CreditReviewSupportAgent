"""Real Docker + synthetic JSON end-to-end verification; creates a demo run."""
from datetime import date
from credit_review.demo import DemoClient, demo_sources
from credit_review.harness import Harness

h = Harness.create('workspace', 'docker_smoke', date(2026,4,7), demo_sources(), DemoClient(), 'DEMO')
for _ in range(4):
    factor = h.step('F24')
    if factor.error:
        raise RuntimeError(factor.error)
assert factor.judgement
result = h.store.get(factor.calculation_ids[-1])['payload']['result']
assert result['cash_after_maturity'] == -50
assert abs(result['historical_cf_to_maturity'] - 4/3) < 1e-9
h.synthesize()
print('DOCKER_SMOKE_OK', h.state.run_id, result)
