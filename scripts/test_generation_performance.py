import copy
import unittest
from datetime import datetime
from generation_performance import Observation,baseline


class PerformanceTests(unittest.TestCase):
    def test_phase_times_and_failure_are_separate_from_completion(self):
        start=datetime(2026,1,1).timestamp()
        obs=Observation('run-20260101-000000-abc',start+1)
        self.assertTrue(obs.record['observed_from_start'])
        self.assertFalse(obs.event({'status':'running','phase':'draft','stage':'generation'},start+1))
        obs.event({'status':'running','phase':'refinement','stage':'review'},start+11)
        self.assertTrue(obs.event({'status':'failed','phase':'refinement','stage':'review'},start+16))
        self.assertEqual([s['elapsed_seconds'] for s in obs.record['stages']],[10,5])
        self.assertEqual(obs.record['elapsed_seconds'],16)
        self.assertIsNone(baseline({**obs.record,'conditions':{}},[]))

    def test_compare_same_workload_and_cache_only(self):
        previous={'run_id':'a','started_at':'2026-01-01','status':'completed','observed_from_start':True,
                  'conditions':{'requested_views':['all'],'model':{'model':'m'},'code_hash':'old'},
                  'schedule':['draft','review'],'cache_hits':0,'cache_misses':1,'elapsed_seconds':100}
        current=copy.deepcopy(previous);current.update(run_id='b',elapsed_seconds=80)
        current['conditions']['code_hash']='new'
        self.assertEqual(baseline(current,[previous])['change_percent'],-20)
        for field,value in [('status','cancelled'),('observed_from_start',False),('observation_gap',True),('concurrent_app_run',True),('cache_hits',1),('schedule',['review'])]:
            r=copy.deepcopy(current);r[field]=value
            self.assertIsNone(baseline(r,[previous]),field)

    def test_late_attachment_is_not_a_complete_observation(self):
        start=datetime(2026,1,1).timestamp()
        self.assertFalse(Observation('run-20260101-000000-abc',start+100).record['observed_from_start'])

if __name__=='__main__':unittest.main()
