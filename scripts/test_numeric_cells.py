import copy,json,re,unittest
from pathlib import Path
from frozen_numeric_cells import restore,NUMBER
from frozen_table_integrity import preserve


class NumericCellsTests(unittest.TestCase):
    def test_period_unit_and_negative_are_materialized(self):
        table={'fixed_template':True,'caption':'표 (단위: 백만원)','columns':['항목','2022-12','2023-12'],'rows':[['투자',None,None]]}
        aliases={'s':{'id':'source','document_id':'doc','page':1,'text':'2023년 당기 2022년 전기 (단위: 원)\n투자 (2,500,000) 1,000,000'}}
        ref={'source_id':'s','header_source_id':'s','line':1,'value_index':0,'period':'2023','source_unit':'원'}
        result={'T0':{'columns':table['columns'],'rows':{'R0':{'values':{'C1':None,'C2':ref}}}}}
        audit=restore(result,[table],aliases)
        self.assertEqual(result['T0']['rows']['R0']['values']['C2'],-3)
        self.assertEqual(audit[0]['raw'],'(2,500,000)')
        wrong=copy.deepcopy(ref);wrong['period']='2022'
        result['T0']['rows']['R0']['values']['C2']=wrong
        restore(result,[table],aliases)
        self.assertEqual(result['T0']['rows']['R0']['values']['C2'],-3)
        self.assertTrue(table['numeric_coordinate_repairs'])

    def test_ambiguous_header_period_is_not_repaired(self):
        table={'fixed_template':True,'caption':'표 (단위: 백만원)','columns':['항목','2023'],'rows':[['값',None]]}
        aliases={'s':{'id':'s','document_id':'doc','text':'2025 2024 (단위: 원)\n항목 1 2 3'}}
        ref={'source_id':'s','header_source_id':'s','line':1,'value_index':0,'period':'2023','source_unit':'원'}
        result={'T0':{'columns':table['columns'],'rows':{'R0':{'values':{'C1':ref}}}}}
        with self.assertRaises(ValueError):restore(result,[table],aliases)

    def test_frozen_cashflow_eight_cells_from_original_tokens(self):
        folder=Path('outputs/experiments/20260914/frozen')
        doc=json.loads((folder/'6a24d3f7e100c7c261789fa652398a48a21bc4b77cce7c6a2d0a71a4ed3ac0d1.json').read_text(encoding='utf-8'))
        sources={s['id']:s for s in doc['sources'] if s.get('page') in (12,13)}
        header=next(s for s in sources.values() if s['id'].endswith('p12-r1'))
        expected=[(243067,415848),(-605426,-821459),(397118,699927),(247041,546282)]
        terms=['I. 영업활동으로','II. 투자활동으로','III. 재무활동으로','VII. 기말의']
        table={'fixed_template':True,'caption':'현금흐름표 (단위: 백만원)','columns':['과목','2023','2024','2025'],'rows':[[t,None,None,None] for t in terms]}
        rows={}
        for i,term in enumerate(terms):
            source,line_index,line=next((s,n,l) for s in sources.values() for n,l in enumerate(s['text'].splitlines()) if l.strip().startswith(term))
            self.assertEqual(len(NUMBER.findall(line)),2)
            values={'C1':None}
            for ci,year,index in [(2,'2024',1),(3,'2025',0)]:values[f'C{ci}']={'source_id':source['id'],'header_source_id':header['id'],'line':line_index,'value_index':index,'period':year,'source_unit':'원'}
            rows[f'R{i}']={'values':values}
        result={'T0':{'columns':table['columns'],'rows':rows}}
        restore(result,[table],sources)
        self.assertEqual([(r['values']['C2'],r['values']['C3']) for r in rows.values()],expected)

    def test_authored_source_values_are_not_overwritten(self):
        source={'tables':[{'caption':'원문','columns':['항목','2024'],'rows':[['값',12]],'source_binding':{'method':'exact_source_template'}}]}
        result=copy.deepcopy(source);result['tables'][0]['rows'][0][1]=1200
        preserve(source,result)
        self.assertEqual(result['tables'][0]['rows'],source['tables'][0]['rows'])
        self.assertTrue(result['tables'][0]['source_conflicts'])


if __name__=='__main__':unittest.main()
