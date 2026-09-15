import unittest
from frozen_exact_template_source import exact_table, bind_templates, restore_bound, ensure_exact_sources
from types import SimpleNamespace


class ExactSourceTests(unittest.TestCase):
    def setUp(self):
        self.template=dict(caption='검토표 (단위: 백만원)',columns=['항목','전전기','전기','당기','추정1기'],labels=['매출','차입금'],customer=False)
        self.source=dict(id='s',document_id='d',format='xlsx',text='A1=검토표 (단위: 백만원)\nA2=항목 | B2=2022-12 | C2=2023-12 | D2=2024-12 | E2=추정1기\nA3=매출 | B3=11 | C3=12 | D3=13 | E3=14\nA4=차입금 | B4=20 | C4=21 | D4=22 | E4=23')
    def test_keeps_period_value_mapping(self):
        result=exact_table(self.source,self.template)
        self.assertEqual(result['r1'],[20,21,22,23])
        self.assertEqual(result['periods'],['2022-12','2023-12','2024-12'])
        self.assertTrue(result['semantic_review_required'])
    def test_rejects_different_unit_and_incomplete_rows(self):
        for text in [self.source['text'].replace('백만원','원'), self.source['text'].replace(' | E4=23','')]:
            self.assertIsNone(exact_table({**self.source,'text':text},self.template))
    def test_rejects_reordered_period_and_missing_marker(self):
        for text in [self.source['text'].replace('2022-12','2025-12'),self.source['text'].replace('D3=13','D3=-1')]:
            self.assertIsNone(exact_table({**self.source,'text':text},self.template))
    def test_priority_never_resolves_conflicting_values(self):
        a={**self.source,'metadata':{'priority':'high'}}
        b={**self.source,'id':'b','text':self.source['text'].replace('D3=13','D3=99'),'metadata':{'priority':'low'}}
        bound=bind_templates([a,b],[self.template],{'high':2,'low':1})
        self.assertEqual(bound,{})
        b['metadata']['priority']='high'
        self.assertEqual(bind_templates([a,b],[self.template],{'high':2,'low':1}),{})
        bound=bind_templates([a],[self.template],{'high':2,'low':1})
        result={};restore_bound(result,bound)
        self.assertEqual(result['fixed_tables']['t0']['r0'][2],13)
    def test_exact_table_survives_retrieval_miss(self):
        store=SimpleNamespace(get=lambda key:{'format':'xlsx','sources':[self.source]})
        manifest=[{'id':'d','name':'input.xlsx','priority':'high'}]
        rows=ensure_exact_sources(store,[self.template],manifest,[],{'high':2})
        self.assertEqual(len(rows),1)
        self.assertTrue(rows[0]['table_coverage'])
        self.assertEqual(rows[0]['text'],self.source['text'])


if __name__ == '__main__':unittest.main()
