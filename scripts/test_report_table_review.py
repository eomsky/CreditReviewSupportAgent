import copy,unittest
import report_table_review as tr
class TableReviewTest(unittest.TestCase):
 def test_completed_semantic_review_is_not_repeated_by_legacy_pass(self):
  d=self.draft();reviewed=d['sections'][0]['tables'][0]
  pending=copy.deepcopy(reviewed);reviewed['semantic_review_completed']=True
  d['sections'][0]['tables'].append(pending)
  cells=tr.missing(d)
  self.assertEqual(len(cells),1);self.assertEqual(next(iter(cells.values()))['table'],1)
  self.assertIsNone(reviewed['rows'][0][1])
 def test_summary_cashflow_is_reviewed_and_spaced_original_label_matches(self):
  d={'tables':[{'caption':'현금흐름표 (단위: 백만원)','columns':['과목','2025'],'rows':[['재무활동으로인한현금흐름',None]],'fixed_template':True}],'paragraphs':[]}
  key=next(iter(tr.missing(d)))
  tr.apply(d,{'table_cell_reviews':[{'cell_id':key,'value':700,'source_ids':['s'],'reason':'원문 확인'}]},[{'id':'s','document_id':'d','text':'III. 재무활동으로 인한 현금흐름 700'}])
  self.assertEqual(d['tables'][0]['rows'][0][1],700)
 def test_subsidiary_total_nonapplicable_cells_excluded(self):
  d={'tables':[{'template_id':'summary2_subsidiaries','caption':'종속회사','columns':['기업명','설립월','소재지','지분율','장부가액','사업내용'],'rows':[['회사',None,'한국',100,None,'제조'],['합계',None,None,None,None,None]]}]}
  cells=tr.missing(d);self.assertEqual(len(cells),3)
  self.assertEqual(sum(c['value_type']=='text' for c in cells.values()),1)
 def test_sales_minus_one_is_missing_not_a_real_value(self):
  d={'tables':[{'template_id':'summary2_sales','caption':'매출','columns':['사업부문','구분','2025'],'rows':[['리조트','수출',-1]]}]}
  key=next(iter(tr.missing(d)))
  tr.apply(d,{'table_cell_reviews':[{'cell_id':key,'value':None,'source_ids':[],'reason':'원문에서 수출 구분 미확인'}]},[])
  self.assertIsNone(d['tables'][0]['rows'][0][2])
 def draft(self):return {'sections':[{'title':'수익성','paragraphs':[{'text':'본문','sources':[]}],'tables':[{'caption':'손익 · 별도 (단위: 백만원)','columns':['구분','2023','2024'],'rows':[['매출총이익',None,0]],'after_paragraph_index':0}]}]}
 def test_fill_and_preserve_existing_zero(self):
  d=self.draft();ids=list(tr.missing(d));self.assertEqual(len(ids),1)
  tr.apply(d,{'table_cell_reviews':[{'cell_id':ids[0],'value':56291,'source_ids':['s'],'reason':'원문 값 확인'}]},[{'id':'s','document_id':'d','text':'매출총이익 2023년 56,291'}])
  self.assertEqual(d['sections'][0]['tables'][0]['rows'][0],['매출총이익',56291,0]);self.assertEqual(d['table_review'][0]['status'],'filled')
 def test_unsupported_value_stays_missing(self):
  d=self.draft();key=next(iter(tr.missing(d)))
  tr.apply(d,{'table_cell_reviews':[{'cell_id':key,'value':999,'source_ids':['s'],'reason':'value'}]},[{'id':'s','text':'매출총이익 56,291'}]);self.assertIsNone(d['sections'][0]['tables'][0]['rows'][0][1])
 def test_different_measure_cannot_fill_cell(self):
  d=self.draft();d['sections'][0]['tables'][0]['rows'][0][0]='법인세차감전순이익';key=next(iter(tr.missing(d)))
  tr.apply(d,{'table_cell_reviews':[{'cell_id':key,'value':3781,'source_ids':['s'],'reason':'잘못된 대체'}]},[{'id':'s','text':'당기순이익 3,781'}]);self.assertIsNone(d['sections'][0]['tables'][0]['rows'][0][1])
 def test_original_unit_header_and_rounding(self):
  d=self.draft();key=next(iter(tr.missing(d)))
  ev=[{'id':'row','document_id':'d','page':2,'text':'매출총이익 1,500,001'}, {'id':'header','document_id':'d','page':2,'text':'2023년\n(단위 : 원)'}]
  tr.apply(d,{'table_cell_reviews':[{'cell_id':key,'value':2,'source_ids':['row'],'reason':'백만원 반올림'}]},ev)
  self.assertEqual(d['sections'][0]['tables'][0]['rows'][0][1],2)
  self.assertIn('header',d['table_review'][0]['source_ids'])
 def test_each_missing_cell_must_be_reviewed(self):
  with self.assertRaises(ValueError):tr.apply(self.draft(),{'table_cell_reviews':[]},[])
if __name__=='__main__':unittest.main()
