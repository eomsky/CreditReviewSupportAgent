import pytest
from test_harness import make
from credit_review.demo import DemoClient
from credit_review.models import Action, DatasetCalculation


def dataset_action(h):
    h.step('F24')
    action = Action.model_validate_json(DemoClient().next_action(h.context('F24')))
    action.after_dataset = DatasetCalculation(purpose='Cash coverage',
        code="result = {'coverage': float(df.iloc[0]['cash']/df.iloc[0]['maturing_debt'])}")
    return action


def test_inline_plan_uses_validated_saved_data(tmp_path):
    h = make(tmp_path)
    action = dataset_action(h)
    calls = []
    class CaptureExecutor:
        def execute(self, plan, datasets):
            calls.append((plan, datasets))
            return {'status':'EXECUTED', 'result':{'coverage':0.5}}
    h.executor = CaptureExecutor()
    aid = h.apply('F24', action, 'request')
    plan, datasets = calls[0]
    assert plan.dataset_ids == [aid]
    assert plan.code.startswith('df = dfs[' + repr(aid) + ']\n')
    assert datasets[aid] == h.store.get(aid)['payload']
    assert len(h.state.factors['F24'].calculation_ids) == 1
    assert h.state.factors['F24'].judgement is None


def test_invalid_units_never_reach_inline_executor(tmp_path):
    h = make(tmp_path)
    action = dataset_action(h)
    action.dataset.columns[1].unit = None
    class NeverExecutor:
        def execute(self, *args):
            pytest.fail('Invalid inputs must not execute')
    h.executor = NeverExecutor()
    with pytest.raises(ValueError, match='unit'):
        h.apply('F24', action, 'request')
    assert not h.state.factors['F24'].dataset_ids


def test_inline_failure_retains_dataset_for_repair(tmp_path):
    h = make(tmp_path)
    action = dataset_action(h)
    class FailedExecutor:
        def execute(self, *args):
            raise RuntimeError('bad arithmetic')
    h.executor = FailedExecutor()
    with pytest.raises(ValueError, match='Dataset preserved'):
        h.apply('F24', action, 'request')
    assert len(h.state.factors['F24'].dataset_ids) == 1
    assert not h.state.factors['F24'].calculation_ids


def test_dataframe_only_plan_exports_real_computed_values_and_nulls(tmp_path):
    import json
    import pandas as pd
    import numpy as np
    h = make(tmp_path)
    action = dataset_action(h)
    action.after_dataset.code = "df['computed'] = df['cash'] * 2; df['undefined'] = np.inf"
    class FixtureExecutor:
        def execute(self, plan, datasets):
            namespace = {'pd':pd,'np':np,'dfs':{k:pd.DataFrame(v['rows']) for k,v in datasets.items()}}
            exec(plan.code,namespace)
            rows=namespace['result']
            assert rows[0]['computed']==rows[0]['cash']*2
            assert rows[0]['undefined'] is None
            json.dumps(rows,allow_nan=False)
            return {'status':'EXECUTED','result':rows}
    h.executor=FixtureExecutor()
    h.apply('F24',action,'request')
    assert h.state.factors['F24'].calculation_ids
