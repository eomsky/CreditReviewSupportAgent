import copy,unittest
from frozen_report_table_reuse import bind,configure,restore,annotate


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.table={'caption':'현황 (단위: 백만원)','columns':['항목','2024','2025'],'rows':[['차입금',10,20],['자본',30,40]],'source_binding':{'method':'exact_source_template','source_id':'s','document_id':'d'}}
        self.prior={'view':{'refinement':{'done':True},'tables':[self.table]}}
        self.plan={'tables':[{'caption':'상환 검토','columns':['구분','2025'],'rows':['자본','차입금'],'source_ids':['s']}]}
        self.evidence=[{'id':'s','document_id':'d'},{'id':'other','document_id':'foreign'}]
    def test_projection_and_no_mutation(self):
        result=bind(self.plan,self.prior,self.evidence)
        self.assertEqual(result['T0']['rows'],[['자본',40],['차입금',20]])
        result['T0']['rows'][0][1]=999
        self.assertEqual(self.table['rows'][1][2],40)
    def test_different_period_or_metric_not_reused(self):
        for field,value in [('columns',['구분','추정1기']),('rows',['총부채'])]:
            plan=copy.deepcopy(self.plan);plan['tables'][0][field]=value
            self.assertEqual(bind(plan,self.prior,self.evidence),{})
    def test_foreign_scope_and_unit_not_reused(self):
        plan=copy.deepcopy(self.plan);plan['tables'][0]['source_ids'].append('other')
        self.assertEqual(bind(plan,self.prior,self.evidence),{})
        plan=copy.deepcopy(self.plan);plan['tables'][0]['caption']='현황 (단위: 원)'
        self.assertEqual(bind(plan,self.prior,self.evidence),{})
    def test_conflicting_source_tables_rejected(self):
        other=copy.deepcopy(self.table);other['rows'][1][2]=999
        self.prior['view']['tables'].append(other)
        self.assertEqual(bind(self.plan,self.prior,self.evidence),{})
    def test_unreviewed_or_no_binding_not_reused(self):
        del self.prior['view']['refinement']
        self.assertEqual(bind(self.plan,self.prior,self.evidence),{})
    def test_actual_table_renderer_receives_original_values_and_source(self):
        import prepared_context
        self.plan['tables'][0].update(section='심사',reason='원문 동일 좌표')
        bindings=bind(self.plan,self.prior,self.evidence)
        schema={'properties':{},'required':[]}
        prepared_context.configure(schema,self.plan)
        configure(schema,bindings)
        self.assertNotIn('rows',schema['properties']['planned_tables']['properties']['T0']['properties'])
        aliases={'S1':self.evidence[0]}
        prepared_context.set_aliases(schema,aliases)
        result={'sections':[{'title':'심사','paragraphs':[{'text':'본문','source_ids':[]}]}],
                'planned_tables':{'T0':{'unit':'원','source_ids':['S1'],'after_paragraph_index':0}}}
        restore(result,bindings,aliases)
        prepared_context.apply(result,self.plan,aliases)
        annotate(result,self.plan,bindings)
        t=result['sections'][0]['tables'][0]
        self.assertEqual(t['rows'],[['자본',40],['차입금',20]])
        self.assertIn('백만원',t['caption'])
        self.assertEqual(t['source_ids'],['s'])
        self.assertEqual(t['source_binding']['projection']['rows'],[1,0])


if __name__=='__main__':unittest.main()
