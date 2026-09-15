import json,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
import semantic_table_review as semantic

class SemanticTableTest(unittest.TestCase):
 def test_model_is_explicitly_told_whether_layout_is_fixed(self):
  t={'caption':'임의 표','columns':['항목','값'],'rows':[['예',0]]}
  self.assertIs(semantic.input_table(t)['fixed_template'],False)
  self.assertIs(semantic.input_table({**t,'fixed_template':True})['fixed_template'],True)
 def test_explicit_unit_decision_removes_stale_caption_unit(self):
  t={'caption':'기업 기본현황 (단위: 백만원)','columns':['항목','내용'],'rows':[['설립','2001년']]}
  semantic.apply_layout(t,{'caption':t['caption'],'unit_review':{'reason':'설립 정보는 금액 측정값이 아님','unit':''}})
  self.assertEqual(t['caption'],'기업 기본현황');self.assertEqual(t['rows'],[['설립','2001년']])
 def test_fixed_layout_cannot_drop_empty_rows_or_columns(self):
  table={'fixed_template':True,'caption':'고정 표','columns':['항목','2024','2025'],'rows':[['매출',None,100],['이익',None,None]]}
  rules=semantic.schema([table],['S1'])['properties']['T0']['properties']
  self.assertEqual(rules['omit_columns']['maxItems'],0);self.assertEqual(rules['omit_rows']['maxItems'],0)
  semantic.apply_layout(table,{'omit_columns':[1],'omit_rows':[1],'caption':'변경'})
  self.assertEqual(table['columns'],['항목','2024','2025']);self.assertEqual(len(table['rows']),2);self.assertEqual(table['caption'],'고정 표')
 def test_layout_uses_model_decision_and_keeps_real_values(self):
  t={'columns':['기업명','설립월','소재지','지분율','장부가액','사업'],'rows':[['회사',None,'한국',34.3,None,'제조'],['합계',None,None,None,None,None]],'column_widths':[25,12,13,12,15,23]}
  semantic.apply_layout(t,{'omit_columns':[1,4],'omit_rows':[1],'layout_reason':'회사 현황의 확인 불가 열과 합산 의미 없는 행 제외','caption':'종속회사 현황 (단위: %)'})
  self.assertEqual(t['columns'],['기업명','소재지','지분율','사업']);self.assertEqual(t['rows'],[['회사','한국',34.3,'제조']]);self.assertAlmostEqual(sum(t['column_widths']),100)
 def test_stream_cells_ignore_partial_number_and_track_table_row(self):
  text='{"T0":{"columns":["항목","2025"],"rows":{"R2":{"values":{"C0":"기말현금","C1":123'
  cells=semantic.stream_cells(text,['p::table-0'])
  self.assertFalse(any(c['row']==2 and c['column']==1 for c in cells))
  cells=semantic.stream_cells(text+'},"source_ids":[]',['p::table-0'])
  self.assertEqual(cells[-1],{'table_key':'p::table-0','row':2,'column':1,'value':123})
 def test_stream_never_emits_truncated_negative_or_decimal_value(self):
  payload={'T1':{'rows':{'R3':{'values':{'C2':-821459.25,'C3':'문자 "인용"'}}}}}
  text=json.dumps(payload,ensure_ascii=False)
  for end in range(len(text)+1):
   for cell in semantic.stream_cells(text[:end],['first','second']):
    self.assertEqual(cell['table_key'],'second')
    self.assertEqual(cell['value'],-821459.25 if cell['column']==2 else '문자 "인용"')
 def test_reserved_total_position_preserves_model_values_and_sources(self):
  table={'columns':['매출처','금액','비중','매출처','금액','비중'],'rows':[[None]*6 for _ in range(5)]+[['상기 외',None,None,'상기 외',None,None],['합계',None,None,'합계',None,None]]}
  rows={f'R{i}':{'values':{f'C{j}':v for j,v in enumerate(row)},'source_ids':[],'reason':''} for i,row in enumerate(table['rows'])}
  rows['R2']={'values':{f'C{j}':v for j,v in enumerate(['합계',321,100,'합계',654,100])},'source_ids':['S1'],'reason':'원문 합계 확인'}
  semantic.place_reserved_rows(table,{'rows':rows})
  self.assertEqual(rows['R6']['values']['C1'],321);self.assertEqual(rows['R6']['values']['C4'],654)
  self.assertIn('S1',rows['R6']['source_ids']);self.assertTrue(all(v is None for v in rows['R2']['values'].values()))
 def test_reasoned_table_output_preserves_structure_and_links_original(self):
  draft={'tables':[{'fixed_template':True,'caption':'매출처','columns':['전기','당기'],'rows':[[None,None]]}],'paragraphs':[{'id':'p','text':'본문','sources':[]}]}
  memory={'draft':draft,'documents':[],'evidence':[{'id':'original','document_id':'doc','text':'2028년 123; 2029년 456'}]}
  output={'T0':{'columns':['2028년','2029년'],'rows':{'R0':{'values':{'C0':123,'C1':456},'source_ids':['S1'],'reason':'원문 연도 및 값 대응','calculation':''}},'unresolved':[]}}
  llm=SimpleNamespace(complete=lambda *a,**k:{'choices':[{'finish_reason':'stop','message':{'content':json.dumps(output)}}]})
  app=SimpleNamespace(config=lambda:{'model':'test'},dump=lambda *a:None,lock=threading.RLock())
  with tempfile.TemporaryDirectory() as d:result=semantic.review(app,llm,lambda m:(100,32768),Path(d),'test',memory,{'run':{}},None)
  self.assertEqual(result['tables'][0]['columns'],['2028년','2029년'])
  self.assertEqual(result['paragraphs'][0]['sources'][0]['id'],'original')
  self.assertEqual(draft['tables'][0]['rows'],[[None,None]])
 def test_sparse_changes_distinguish_omission_null_and_zero(self):
  draft={'tables':[{'fixed_template':True,'caption':'표','columns':['항목','2024','2025'],'rows':[['수익',9,None],['매출',1,2]]}],'paragraphs':[{'id':'p','text':'본문','sources':[]}]}
  memory={'draft':draft,'documents':[],'evidence':[{'id':'original','document_id':'doc','text':'원문'}]}
  output={'T0':{'columns':['항목','2024','2025'],'rows':{'R0':{'values':{'C1':None,'C2':0},'source_ids':['S1'],'reason':'정정','calculation':''},'R1':{'values':{},'source_ids':['S1'],'reason':'일치','calculation':''}},'unresolved':[]}}
  llm=SimpleNamespace(complete=lambda *a,**k:{'choices':[{'finish_reason':'stop','message':{'content':json.dumps(output)}}]})
  app=SimpleNamespace(config=lambda:{'model':'test'},dump=lambda *a:None,lock=threading.RLock())
  with tempfile.TemporaryDirectory() as d:result=semantic.review(app,llm,lambda m:(100,32768),Path(d),'test',memory,{'run':{}},None)
  self.assertEqual(result['tables'][0]['rows'],[['수익',None,0],['매출',1,2]])
  self.assertEqual(draft['tables'][0]['rows'],[['수익',9,None],['매출',1,2]])
 def test_schema_keeps_each_table_dimensions(self):
  tables=[{'columns':['a','b','c'],'rows':[[None]*3]*4}]
  fields=semantic.schema(tables,['S1'])['properties']['T0']['properties']
  self.assertEqual(len(fields['rows']['properties']),4)
  self.assertEqual(len(fields['rows']['properties']['R0']['properties']['values']['properties']),3)

if __name__=='__main__':unittest.main()
