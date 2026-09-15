import copy
import json
import unittest

from structured_table_probe import cell_frame


def fixture(values):
    h = {'rows':[{'row_id':f'r{i}', 'path':['계정', str(i)],
                  'source_cell_ids':[f'T:R{i}:C0']} for i in range(len(values))],
         'columns':[{'column_id':'c1','path':['당기','2025'],
                     'source_cell_ids':['T:R0:C1']}],
         'cells':[{'row_id':f'r{i}', 'column_id':'c1','value':v,
                   'content_type':'text','unit_refs':['u1'],
                   'source_cell_id':f'T:R{i}:C1'} for i,v in enumerate(values)]}
    table = {'type':'table','physical_table_id':'T','logical_table_id':'L',
             'title':'테스트','units':[{'unit_id':'u1','text':'원'}],
             'notes':[{'text':'전기 재작성'}],'hierarchy':h}
    return {'document':json.dumps({'source':{'pages':[1],'bboxes':[[545.0015804893092]]},'elements':[table]})}


class CellFrameTest(unittest.TestCase):
    def test_no_tables_is_empty_not_fabricated(self):
        self.assertTrue(cell_frame([], 'doc').empty)

    def test_raw_values_and_context_survive(self):
        values=['0','-1','—','','(1,234)','415,848,470,048']
        frame=cell_frame([fixture(values)],'docA')
        self.assertEqual(frame.raw_value.tolist(), values)
        self.assertEqual(frame.iloc[0].column_path,['당기','2025'])
        self.assertEqual(frame.iloc[0].units,[{'unit_id':'u1','text':'원'}])
        self.assertEqual(json.loads(json.dumps(frame.to_dict(orient='records'))),frame.to_dict(orient='records'))

    def test_identity_not_label_deduplication(self):
        a=fixture(['10','10'])
        self.assertEqual(len(cell_frame([a,a],'docA')),2)
        self.assertNotEqual(cell_frame([a],'docA').iloc[0].cell_id,
                            cell_frame([a],'docB').iloc[0].cell_id)

    def test_conflicting_same_cell_is_not_silently_overwritten(self):
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            cell_frame([fixture(['10']),fixture(['11'])],'docA')

    def test_parser_uncertainty_is_preserved(self):
        self.assertEqual(cell_frame([fixture(['10'])],'d').iloc[0].parser_status,'UNKNOWN')
        self.assertEqual(cell_frame([fixture(['10'])],'d',{'T':{'status':'REVIEW_REQUIRED'}}).iloc[0].parser_status,'REVIEW_REQUIRED')


if __name__=='__main__': unittest.main()
