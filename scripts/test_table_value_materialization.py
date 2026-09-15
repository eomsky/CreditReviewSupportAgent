import unittest
from decimal import Decimal
from table_value_materialization import parse_amount,materialize_money


class MaterializationTest(unittest.TestCase):
    def cell(self,raw,unit='원'):
        return {'s':{'raw_value':raw,'row_path':['투자CF'],'column_path':['당기'],
                     'units':[{'text':f'(단위 : {unit})'}],'parser_status':'REVIEW_REQUIRED'}}

    def test_negative_and_large_integer_are_exact(self):
        self.assertEqual(parse_amount('(821,458,531,576)'),Decimal('-821458531576'))
        r=materialize_money('s',self.cell('(821,458,531,576)'),'원','백만원')
        self.assertEqual(r['value'],'-821459');self.assertEqual(r['exact_value'],'-821458.531576')
        self.assertTrue(r['semantic_review_required'])

    def test_missing_is_not_zero_and_negative_one_is_not_discarded(self):
        self.assertIsNone(parse_amount('—'));self.assertEqual(parse_amount('0'),Decimal(0))
        self.assertEqual(parse_amount('-1'),Decimal(-1))

    def test_reject_wrong_or_mixed_unit_and_unknown_cell(self):
        for cells,sid,unit in [(self.cell('10'),'s','천원'),(self.cell('10','백만원, %'),'s','백만원'),(self.cell('10'),'other','원')]:
            with self.assertRaises(ValueError):materialize_money(sid,cells,unit,'백만원')

    def test_malformed_grouping_is_not_silently_normalized(self):
        for value in ['1,23','12%','약 100','( -123 )']:
            with self.assertRaises(ValueError):parse_amount(value)


if __name__=='__main__':unittest.main()
