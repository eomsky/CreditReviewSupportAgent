import copy
import unittest
import business_report_test as api
import report_tables as tables


class ReportTableTests(unittest.TestCase):
    def fixture(self, template='earnings'):
        t=next(t for t in tables.CATALOG if t['id']==template)
        item={'template_id':template,'section_title':'수익성','after_paragraph_index':0,'basis':'별도, 2025년','source_ids':['S1'],'row_evidence':['근거 0 10']*len(t.get('rows',[1])),'values':[[None,0,10] for _ in t.get('rows',[])] or [['확인값']*(len(t['columns'])-int(bool(t.get('label_rows'))))]}
        if not t.get('rows'):
            item['values']=[['확인값']*(len(t['columns'])-int(bool(t.get('label_rows')))) for _ in range(t.get('min_rows',2))]
            item['row_evidence']=['근거 0 10']*len(item['values'])
        if t.get('periods'):item['periods']=['2023','2024','2025']
        return {'sections':[{'title':'수익성','paragraphs':[{'heading':'분석','text':'확인된 본문','source_ids':[]}]}],'report_tables':[item]}

    def test_every_layout_validates_and_preserves_sources(self):
        schema=copy.deepcopy(api.app.REPORT)
        schema['properties']['sections']['items']=copy.deepcopy(api.app.SECTION)
        tables.configure(schema,[{'title':'수익성'}],['S1'])
        for t in tables.CATALOG:
            result=self.fixture(t['id'])
            option=next(o for o in schema['properties']['report_tables']['items']['anyOf'] if o['properties']['template_id']['enum']==[t['id']])
            self.assertEqual(set(result['report_tables'][0]),set(option['required']))
            self.assertGreaterEqual(len(result['report_tables'][0]['values']),option['properties']['values']['minItems'])
            self.assertAlmostEqual(sum(t['presentation']['column_widths']),100)
            self.assertTrue(t['content_rules'])
            tables.apply(result,{'S1':{'id':'real-source','text':'근거 0 10'}})
            table=result['sections'][0]['tables'][0]
            self.assertEqual(len(table['columns']),len(table['rows'][0]))
            self.assertEqual(table['source_ids'],['real-source'])
            self.assertEqual(result['sections'][0]['paragraphs'][0]['source_ids'],['S1'])

    def test_row_source_ids_and_fixed_profile_labels(self):
        result=self.fixture('company_profile')
        t=next(t for t in tables.CATALOG if t['id']=='company_profile')
        item=result['report_tables'][0]
        item['row_evidence']=['S1']*len(item['values'])
        tables.apply(result,{'S1':{'id':'actual-document-region','text':'원문 확인값'}})
        table=result['sections'][0]['tables'][0]
        self.assertEqual([row[0] for row in table['rows']],t['label_rows'])
        self.assertEqual(table['row_source_ids'],['actual-document-region']*len(t['label_rows']))
        self.assertEqual(table['source_ids'],['actual-document-region'])

    def test_missing_values_remain_null_and_zero_is_real(self):
        result=self.fixture();tables.apply(result,{'S1':{'id':'real','text':'근거 0 10'}})
        self.assertEqual(result['sections'][0]['tables'][0]['rows'][0][1:],[None,0,10])

    def test_invalid_source_rejected(self):
        with self.assertRaises(ValueError):tables.apply(self.fixture(),{'S2':{'id':'other'}})

    def test_empty_numeric_table_retains_cells_for_review(self):
        result=self.fixture();result['report_tables'][0]['values']=[[None]*3 for _ in result['report_tables'][0]['values']]
        tables.apply(result,{'S1':{'id':'real','text':'근거 0 10'}})
        self.assertTrue(all(value is None for row in result['sections'][0]['tables'][0]['rows'] for value in row[1:]))

    def test_invented_numbers_are_not_rendered(self):
        result=self.fixture()
        result['report_tables'][0]['values']=[[450000,200000,94818] for _ in result['report_tables'][0]['values']]
        tables.apply(result,{'S1':{'id':'real','text':'근거 0 10'}})
        self.assertTrue(all(value is None for row in result['sections'][0]['tables'][0]['rows'] for value in row[1:]))

    def test_invented_excerpt_is_not_evidence(self):
        result=self.fixture();result['report_tables'][0]['row_evidence']=['근거 450000']*3
        tables.apply(result,{'S1':{'id':'real','text':'근거 0 10'}})
        self.assertTrue(all(value is None for row in result['sections'][0]['tables'][0]['rows'] for value in row[1:]))


if __name__=='__main__':unittest.main()
