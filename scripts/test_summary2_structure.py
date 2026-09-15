import unittest
import summary2_structure as module
from review_refinement import apply_changes


class SummaryStructureTest(unittest.TestCase):
    def fixture(self):
        return {'topics':{f't{i}':{'paragraphs':[{'heading':'검토','text':'원자료 확인 내용','source_ids':['S1']}],'tables':[]} for i in range(7)}}

    def test_all_topics_required_and_aliases_updated(self):
        schema={'properties':{'paragraphs':{}},'required':['paragraphs']}
        module.configure(schema,{'properties':{'source_ids':{'items':{}}}})
        module.set_aliases(schema,['S2'])
        self.assertEqual(len(schema['properties']['topics']['required']),7)
        self.assertNotIn('paragraphs',schema['required'])
        for item in schema['properties']['topics']['properties'].values():
            self.assertEqual(item['properties']['paragraphs']['items']['properties']['source_ids']['items']['enum'],['S2'])

    def test_flatten_keeps_topic_order_and_table_anchor(self):
        result=self.fixture()
        result['topics']['t3']['tables']=[{'columns':['기업','지분'],'rows':[['대상',100]],'after_paragraph_index':0}]
        module.flatten(result)
        self.assertEqual(len(result['paragraphs']),7)
        self.assertEqual(result['tables'][0]['after_paragraph_index'],3)
        self.assertTrue(result['paragraphs'][-1]['heading'].startswith('6. 종합의견'))

    def test_bad_table_width_rejected(self):
        result=self.fixture();result['topics']['t4']['tables']=[{'columns':['매출'],'rows':[[1,2]],'after_paragraph_index':0}]
        with self.assertRaises(ValueError):module.flatten(result)

    def test_refinement_additions_preserve_table_location(self):
        draft={'paragraphs':[{'id':'a','text':'첫 문단','sources':[]},{'id':'b','text':'두번째 문단','sources':[]}],'tables':[{'after_paragraph_index':1}]}
        changes={'revisions':[{'paragraph_id':i,'action':'keep'} for i in ['a','b']],'additions':[{'after_id':'a','text':'보완 내용','source_ids':[]}],'remaining_gaps':[],'information_guidance':{'explanation':'','needed_contents':[]}}
        result=apply_changes(draft,changes,[])
        self.assertEqual(result['tables'][0]['after_paragraph_index'],2)


if __name__=='__main__':unittest.main()
