import unittest
import summary2_fixed_tables as fixed
import summary2_structure as structure

def placeholder(s):
 if s.get('type')=='object':return {k:placeholder(v) for k,v in s['properties'].items()}
 if s.get('type')=='array':return [placeholder(s['items']) for _ in range(s.get('minItems',0))]
 if s.get('enum'):return s['enum'][0]
 return None if isinstance(s.get('type'),list) else ''
class FixedSummary2Test(unittest.TestCase):
 def test_all_five_tables_always_kept_in_order(self):
  data=placeholder(fixed.schema());result={'topics':{f't{i}':{'paragraphs':[{'heading':'가. 세부항목','text':'본문','source_ids':[]}]} for i in range(7)},'summary2_tables':data}
  structure.flatten(result)
  self.assertEqual([t['template_id'] for t in result['tables']],['summary2_'+t['id'] for t in fixed.TEMPLATES])
  self.assertEqual([t['after_paragraph_index'] for t in result['tables']],[3,3,4,4,4])
  for t in result['tables']:
   self.assertTrue(all(len(row)==len(t['columns']) for row in t['rows']))
   self.assertAlmostEqual(sum(t['column_widths']),100)
  self.assertEqual(result['paragraphs'][1]['topic_title'],'1. 업체개요')
  self.assertEqual(result['paragraphs'][1]['subheading'],'세부항목')
 def test_all_citations_constrained(self):
  s=fixed.schema();fixed.set_aliases(s,['S1','S2'])
  self.assertEqual(s['properties']['products']['properties']['rows']['items']['properties']['source_ids']['items']['enum'],['S1','S2'])
if __name__=='__main__':unittest.main()
