import json,tempfile,threading,types,unittest
from pathlib import Path
from unittest.mock import patch
from frozen_earnings_slots_patch import patch as transform


class EarningsSlotsTests(unittest.TestCase):
    def test_flattening_preserves_roles_indices_and_source_validation(self):
        m=types.ModuleType('slot_candidate')
        exec(transform(Path('outputs/frozen_candidates/C9/code/scripts/prepared_context.py').read_text(encoding='utf-8')),m.__dict__)
        roles=['latest_actual_'+r for r in ['operating_profit','finance_cost','pretax_profit','income_tax','net_profit']]+['other']
        rows={role:[] for role in roles}
        for role,value in [('pretax_profit',30),('income_tax',50),('net_profit',-20)]:
            rows['latest_actual_'+role]=[{'metric':role,'period':'2025','unit':'백만원','basis':'별도','role':role,'value':value,'status':'confirmed','source_ids':['S1'],'quote_span':{'source_id':'S1','start_line':1,'end_line':1}}]
        packet={'facts':[],'tables':[],'numeric_evidence':rows,'calculations':[{'metric':'bridge','operation':'difference','operands':['latest_actual_pretax_profit','latest_actual_income_tax'],'scale':1,'comparison_basis':'same source basis'}],'conflicts':[],'search_queries':[],'source_excerpts':[]}
        def complete(llm,cfg,req,*args,**kw):
            spec=req['structured_outputs']['json']['properties']['numeric_evidence']
            self.assertEqual(spec['required'],roles)
            self.assertEqual(spec['properties']['latest_actual_income_tax']['items']['properties']['role']['enum'],['income_tax'])
            return {'choices':[{'message':{'content':json.dumps(packet)}}]}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def dump(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value),encoding='utf-8')
            app=types.SimpleNamespace(BASE=root,config=lambda:{'model':'test'},dump=dump,lock=threading.RLock())
            with patch.object(m.llm_recovery,'complete',side_effect=complete):
                result=m.prepare(app,None,None,root,'profitability',[{'id':'real-source','document_id':'d','text':'2025 별도 백만원 세전 30 법인세 50 순손실 -20'}],[{'id':'d'}],None,'',None,None,[],fixed=True)
        self.assertEqual([r['role'] for r in result['numeric_evidence']],['pretax_profit','income_tax','net_profit'])
        self.assertTrue(all(r['source_verified'] for r in result['numeric_evidence']))
        self.assertEqual(result['numeric_evidence'][0]['source_ids'],['real-source'])
        self.assertTrue(any(r['result']==-20 for r in result['arithmetic_checks']))


if __name__=='__main__':unittest.main()
