import copy
import tempfile
import unittest
import json
from types import SimpleNamespace
from pathlib import Path
from runtime_structured_store import StructuredStore, grid, number


class StructuredRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store=StructuredStore(Path(self.temp.name)/'facts.sqlite','model-a')
        self.source={'id':'s','document_id':'d','sheet':'재무','text':'연결 손익 (단위: 백만원)\nA1=항목 | B1=2024 | C1=2025\nA2=매출액 | B2=1,000.25 | C2=0\nA3=영업이익 | B3=(20) | C3=-1'}
        self.aliases={'S1':self.source}
        self.table={'source_id':'S1','title':'손익','title_quote':'연결 손익','basis':'연결','basis_quote':'연결 손익','unit':'백만원','unit_quote':'단위: 백만원',
                    'columns':[{'column':c,'period':p,'period_quote':p,'unit':'','unit_quote':''} for c,p in [('B','2024'),('C','2025')]],
                    'rows':[{'row':r,'metric':m,'unit':'','unit_quote':''} for r,m in [('2','매출액'),('3','영업이익')]],'excluded_cells':['C3']}
        self.store.register(self.aliases)

    def test_sql_uses_exact_original_numbers_and_missing_is_not_zero(self):
        self.assertEqual(self.store.review([self.table],self.aliases)[0]['status'],'accepted')
        facts=self.store.packet(self.aliases)['facts']
        self.assertEqual({r['cell']:r['value'] for r in facts},{'B2':'1000.25','C2':'0','B3':'-20'})
        self.assertEqual(number('-1'),'-1')  # Meaning of sentinel is not a numeric rule.

    def test_reuse_and_changed_source_model_invalidate(self):
        self.store.review([self.table],self.aliases)
        pending,cached=self.store.register(self.aliases)
        self.assertFalse(pending);self.assertIn('S1',cached)
        self.store.review([self.table],self.aliases)
        self.assertEqual(self.store.packet(self.aliases)['fact_count'],3)
        changed={'S1':{**self.source,'text':self.source['text'].replace('1,000.25','1,200')}}
        self.assertEqual(self.store.packet(changed)['fact_count'],0)
        other=StructuredStore(self.store.path,'model-b')
        self.assertEqual(other.packet(self.aliases)['fact_count'],0)

    def test_made_up_unit_rejected_without_poisoning_cache(self):
        table=copy.deepcopy(self.table);table['unit']='억원'
        self.assertEqual(self.store.review([table],self.aliases)[0]['status'],'rejected')
        self.assertEqual(self.store.packet(self.aliases)['fact_count'],0)

    def test_company_and_source_scoped(self):
        self.store.review([self.table],self.aliases)
        other={'S1':{**self.source,'document_id':'another-company'}}
        self.assertEqual(self.store.packet(other)['fact_count'],0)

    def test_no_period_no_invented_fact(self):
        table=copy.deepcopy(self.table)
        for c in table['columns']:c['period']=''
        self.assertEqual(self.store.review([table],self.aliases)[0]['status'],'unresolved')
        self.assertEqual(self.store.packet(self.aliases)['fact_count'],0)

    def test_mixed_unit_is_not_approved_as_a_single_amount_unit(self):
        source={**self.source,'text':self.source['text'].replace('백만원','백만원, %')}
        table=copy.deepcopy(self.table);table.update(unit='백만원, %',unit_quote='단위: 백만원, %')
        aliases={'S1':source};self.store.register(aliases)
        self.assertEqual(self.store.review([table],aliases)[0]['status'],'unresolved')
        self.assertEqual(self.store.packet(aliases)['fact_count'],0)

    def test_normalization_budget_preserves_whole_original_sources(self):
        from runtime_structured_store import budget_request
        body={'sources':[{'id':'S1','text':'immutable original'}],
              'structured_grids':{'S1':{'large':'x'*8000}},'cached_sql_tables':{}}
        request={'messages':[{'role':'user','content':json.dumps(body)}],'max_tokens':1000,
                 'structured_outputs':{'json':{'properties':{'structured_tables':{'items':{'properties':{'source_id':{}}}}}}}}
        result=budget_request(request,lambda m:(len(m[-1]['content']),3000))
        self.assertTrue(result['input_within_budget'])
        self.assertEqual(result['deferred_normalization_sources'],['S1'])
        self.assertEqual(json.loads(request['messages'][-1]['content'])['sources'],body['sources'])
        self.assertEqual(request['structured_outputs']['json']['properties']['structured_tables']['maxItems'],0)

    def test_native_grid_does_not_duplicate_cell_values(self):
        from runtime_structured_store import prompt_grids
        grids,_=self.store.register(self.aliases)
        compact=prompt_grids(grids,self.aliases)
        self.assertNotIn('1000',json.dumps(compact))
        self.assertLess(len(json.dumps(compact)),len(json.dumps(grids)))

    def test_pdf_grid_and_ambiguous_duplicate_and_plain_text(self):
        self.assertEqual(len(grid({'text':'항목 | 2024 | 2025\n매출 | 100 | 200'})),6)
        self.assertEqual(grid({'text':'A1=1\nA1=2'}),[])
        self.assertEqual(grid({'text':'매출 100과 차입금 200을 검토한다.'}),[])

    def test_conflicting_mappings_are_kept_separate(self):
        self.store.review([self.table],self.aliases)
        changed=copy.deepcopy(self.table);changed['basis']='';changed['basis_quote']=''
        self.store.review([changed],self.aliases)
        rows=self.store.packet(self.aliases)['facts']
        self.assertEqual(len(rows),6)
        self.assertEqual({r['basis'] for r in rows},{'연결',''})

    def test_production_preparation_and_review_context_use_sql(self):
        import prepared_context
        import evidence_quality
        calls=[]
        def complete(config,request,*args,**kwargs):
            calls.append(request)
            body=json.loads(request['messages'][-1]['content'])
            self.assertIn('S1',body['structured_grids'])
            packet={'facts':[],'tables':[],'conflicts':[],'search_queries':[], 'source_excerpts':[],
                    'numeric_evidence':[],'calculations':[],'structured_tables':[self.table]}
            return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(packet)}}]}
        root=Path(self.temp.name)
        app=SimpleNamespace(BASE=root,config=lambda:{'model':'model-a'},dump=lambda path,data:path.write_text(json.dumps(data),encoding='utf-8'))
        args=(app,SimpleNamespace(complete=complete),lambda messages:(100,65536),root,'ga',[self.source],[],None,'quality prompt',None,None,[])
        packet=prepared_context.prepare(*args,fixed=True)
        cached=prepared_context.prepare(*args,fixed=True)
        self.assertEqual(len(calls),1)
        self.assertEqual(packet['structured_sql']['fact_count'],3)
        self.assertEqual(cached['structured_sql']['fact_count'],3)
        context=evidence_quality.context(packet)
        self.assertEqual(context['structured_sql']['tables'][0]['rows'][0][-1],'1000.25')
        self.assertIn(self.source['text'].splitlines()[0],prepared_context.source_text(self.source,packet))


if __name__=='__main__':unittest.main()
