import copy
import unittest
import evidence_quality as q


class EvidenceQualityTests(unittest.TestCase):
    def packet(self):
        rows=[{'metric':m,'period':'2025','unit':'백만원','basis':'별도','value':v,
               'status':'confirmed','quote':f'{m} {v}','source_ids':['s']}
              for m,v in [('영업이익',240),('금융비용',160)]]
        return {'numeric_evidence':rows,'calculations':[{'metric':'이자보상배율','operation':'ratio','operands':[0,1],'scale':1,'comparison_basis':'동일 기간 별도'}]}

    def test_ratio_is_calculated_without_percentage_guess(self):
        p=self.packet();r=q.validate(p,{'s':{'text':'영업이익 240 금융비용 160'}})
        self.assertEqual(r['arithmetic_checks'][0]['result'],1.5)
        self.assertNotIn('source_verified',p['numeric_evidence'][0])

    def test_only_verifiable_trailing_citation_is_removed(self):
        p=self.packet();p['numeric_evidence'][0]['quote']+='\n(S1)'
        r=q.validate(p,{'s':{'text':'영업이익 240 금융비용 160'}})
        self.assertEqual(r['arithmetic_checks'][0]['result'],1.5)

    def test_merge_keeps_calculation_references_local_to_packet(self):
        p=q.validate(self.packet(),{'s':{'text':'영업이익 240 금융비용 160'}})
        r=q.merge([p,p]);self.assertEqual(r['arithmetic_checks'][1]['operands'],[2,3])
        self.assertEqual(r['quality_version'],q.VERSION)
        self.assertNotIn('quality_version',q.merge([p,{}]))

    def test_conflicting_or_unquoted_values_cannot_be_calculated(self):
        for mutation in ('quote','basis','unit','period','status'):
            p=self.packet();p['numeric_evidence'][0][mutation]='other'
            r=q.validate(p,{'s':{'text':'영업이익 240 금융비용 160'}})
            self.assertIsNone(r['arithmetic_checks'][0]['result'])

    def test_zero_denominator_and_bad_index_are_unresolved(self):
        p=self.packet();p['calculations'][0]['operands']=[0,99]
        self.assertIsNone(q.validate(p,{'s':{'text':'영업이익 240 금융비용 160'}})['arithmetic_checks'][0]['result'])
        p=self.packet();p['numeric_evidence'][1].update(value=0,quote='금융비용 0')
        self.assertIsNone(q.validate(p,{'s':{'text':'영업이익 240 금융비용 0'}})['arithmetic_checks'][0]['result'])

    def test_tax_bridge_and_growth_do_not_share_period_policy(self):
        p=self.packet();p['calculations'][0]['operation']='difference'
        self.assertEqual(q.validate(p,{'s':{'text':'영업이익 240 금융비용 160'}})['arithmetic_checks'][0]['result'],80)
        p['numeric_evidence'][1]['period']='2024';p['calculations'][0]['operation']='growth_percent'
        self.assertEqual(q.validate(p,{'s':{'text':'영업이익 240 금융비용 160'}})['arithmetic_checks'][0]['result'],50)

    def test_relationship_uses_verified_operands(self):
        p=self.packet();p['calculations']=[];p['key_relationships']={'interest_coverage':[0,1]}
        self.assertEqual(q.validate(p,{'s':{'text':'영업이익 240 금융비용 160'}})['arithmetic_checks'][0]['result'],1.5)

    def test_semantic_roles_calculate_coverage_without_model_formula(self):
        p=self.packet();p['calculations']=[]
        p['numeric_evidence'][0]['role']='operating_profit'
        p['numeric_evidence'][1]['role']='finance_cost'
        r=q.validate(p,{'s':{'text':'영업이익 240 금융비용 160'}})
        self.assertEqual(r['arithmetic_checks'][0]['result'],1.5)
        p['numeric_evidence'].append(copy.deepcopy(p['numeric_evidence'][0]))
        self.assertEqual(q.validate(p,{'s':{'text':'영업이익 240 금융비용 160'}})['arithmetic_checks'],[])

    def test_structured_sources_preserve_headers_and_last_row(self):
        import review_refinement as r
        source={'id':'s','document_id':'d','sheet':'arbitrary','text':'A1=기간 | B1=2029\n'+ '\n'.join(f'A{i}=항목{i} | B{i}={i}' for i in range(2,99))}
        text=r.compact_sources([source],{'paragraphs':[]},limit=150)[0]['text']
        self.assertIn('2029',text)
        self.assertIn('항목98 | 98',text)

if __name__=='__main__':unittest.main()
