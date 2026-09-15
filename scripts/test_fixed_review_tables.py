import unittest
import fixed_review_tables as fixed


class FixedTableTests(unittest.TestCase):
    def test_all_five_views_keep_template_shape_and_only_one_header(self):
        for view,templates in fixed.TEMPLATES.items():
            values={}
            for i,t in enumerate(templates):
                periods=['2024-12','2025-12'] if t['customer'] else ['2023-12','2024-12','2025-12']
                width=len(t['columns'])-(0 if t['customer'] else 1)
                values[f't{i}']={'periods':periods,**{f'r{j}':[None]*width for j in range(len(t['labels']))}}
            result={'fixed_tables':values};fixed.apply(result,view)
            self.assertEqual(len(result['tables']),len(templates))
            for table,t in zip(result['tables'],templates):
                self.assertTrue(table['fixed_template']);self.assertEqual(len(table['rows']),len(t['labels']))
                self.assertEqual(len(table['columns']),len(t['columns']))
                if not t['customer']:self.assertEqual([r[0] for r in table['rows']],t['labels'])
                else:self.assertEqual([table['columns'][1],table['columns'][4]],['2024-12 금액','2025-12 금액'])

    def test_customer_period_schema_and_null_sentinel(self):
        schema={'properties':{},'required':[]};fixed.configure(schema,'customer_concentration')
        self.assertEqual(schema['properties']['fixed_tables']['properties']['t0']['properties']['periods']['maxItems'],2)
        rows={f'r{i}':['null',None,None,'null',None,None] for i in range(7)}
        result={'fixed_tables':{'t0':{'periods':['2028-12','2029-12'],**rows}}};fixed.apply(result,'customer_concentration')
        self.assertIsNone(result['tables'][0]['rows'][0][0])


if __name__=='__main__':unittest.main()
