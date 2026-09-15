import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import prepared_context as p


class PreparationTests(unittest.TestCase):
    def test_planning_templates_preserve_semantics_without_rendering_metadata(self):
        original=[{'columns':['항목','금액'],'rows':['매출'],'content_rules':'동일 기준',
                   'presentation':{'style':'green'},'column_guidance':{'금액':'우측'},'reference':'example'}]
        result=p.planning_templates(original)
        self.assertEqual(result,[{'columns':['항목','금액'],'rows':['매출'],'content_rules':'동일 기준'}])
        self.assertIn('presentation',original[0])
    def test_internal_citation_notes_are_not_business_values(self):
        t={'columns':['기업','내용','비고'],'rows':[['S1','실제 0','S1, S2'],['임의 회사',0,'S2']]}
        p.clean_reference_cells(t,{'S1','S2'})
        self.assertEqual(t['rows'],[['S1','실제 0'],['임의 회사',0]])
        fixed={'fixed_template':True,'columns':['기업','내용','비고'],'rows':[['S1',0,'S2']]}
        p.clean_reference_cells(fixed,{'S1','S2'})
        self.assertEqual(fixed['rows'],[['S1',0,None]])
    def test_followup_assessment_reuses_verified_packet_and_reads_only_new_originals(self):
        previous=copy.deepcopy(self.packet)
        for item in previous['facts']+previous['tables']:item['source_ids']=['original']
        previous['source_excerpts'][0]['source_id']='original'
        def complete(config,request,*args,**kwargs):
            body=json.loads(request['messages'][-1]['content'])
            self.assertEqual([s['id'] for s in body['sources']],['S2'])
            self.assertEqual(body['previous_assessment']['facts'][0]['source_ids'],['S1'])
            self.assertEqual(body['previous_assessment']['tables'][0]['rows'],['기말현금'])
            return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(self.packet)}}]}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);app=SimpleNamespace(BASE=root,config=lambda:{'model':'m'},dump=lambda path,data:path.write_text(json.dumps(data),encoding='utf-8'))
            sources=self.sources+[{'id':'new','document_id':'doc','text':'추가 원문'}]
            result=p.prepare(app,SimpleNamespace(complete=complete),lambda m:(100,32768),root,'cash',sources,[],None,'',None,None,[],previous_packet=previous,fresh_ids={'new'})
            self.assertEqual(result['tables'][0]['source_ids'],['original'])
            self.assertEqual(previous['facts'][0]['source_ids'],['original'])
    def test_report_plan_receives_full_outline_and_does_not_copy_protected_tables(self):
        context={'full_outline':[{'title':'cash'},{'title':'other'}],'already_used_tables':[{'caption':'existing'}]}
        def complete(config,request,*args,**kwargs):
            body=json.loads(request['messages'][-1]['content'])
            self.assertEqual(body['report_context'],context)
            self.assertEqual(body['sections'][0]['description'],'잔액과 흐름 구별')
            self.assertEqual(request['structured_outputs']['json']['properties']['source_excerpts']['maxItems'],0)
            packet=copy.deepcopy(self.packet);packet['source_excerpts']=[]
            return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(packet)}}]}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);app=SimpleNamespace(BASE=root,config=lambda:{'model':'m'},dump=lambda path,data:path.write_text(json.dumps(data),encoding='utf-8'))
            p.prepare(app,SimpleNamespace(complete=complete),lambda m:(100,32768),root,'cash',[{**self.sources[0],'sheet':'임의 양식'}],[],[{'title':'cash','description':'잔액과 흐름 구별'}],'',None,None,[],report_context=context)
    def setUp(self):
        self.sources=[{'id':'original','document_id':'doc','text':'2025년 연결 현금흐름\n재무활동 700\n기말현금 546'}]
        self.packet={'facts':[{'text':'2025년 연결 기준','source_ids':['S1']}], 'conflicts':[],
                     'source_excerpts':[{'source_id':'S1','passages':['2025년 연결 현금흐름','기말현금 546']}],
                     'tables':[{'section':'cash','caption':'현금흐름 · 2025년 연결','columns':['과목','2025년'],
                                'rows':['기말현금'],'source_ids':['S1'],'reason':'확인된 기간을 비교'}]}

    def test_cache_reuse_and_metadata_invalidation(self):
        calls=[]
        def complete(*args,**kwargs):
            calls.append(1)
            return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(self.packet)}}]}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            app=SimpleNamespace(BASE=root,config=lambda:{'model':'m'},dump=lambda path,data:path.write_text(json.dumps(data),encoding='utf-8'))
            args=(app,SimpleNamespace(complete=complete),lambda m:(100,32768),root,'cash',self.sources)
            first=p.prepare(*args,[{'id':'doc','required':True}],None,'prompt',None,None,[])
            second=p.prepare(*args,[{'id':'doc','required':True}],None,'prompt',None,None,[])
            self.assertEqual(first,second);self.assertEqual(len(calls),1)
            p.prepare(*args,[{'id':'doc','required':False}],None,'prompt',None,None,[])
            self.assertEqual(len(calls),2)
            self.assertEqual(first['tables'][0]['source_ids'],['original'])
            self.assertEqual(p.source_text(self.sources[0],first),'2025년 연결 현금흐름\n[…]\n기말현금 546')

    def test_mismatched_extract_uses_original(self):
        packet={'source_excerpts':[{'source_id':'original','passages':['기말현금 999']} ]}
        self.assertEqual(p.source_text(self.sources[0],packet),self.sources[0]['text'])

    def test_multiple_excerpts_of_same_source_are_all_preserved_in_original_order(self):
        packet={'source_excerpts':[{'source_id':'original','passages':['기말현금 546']},{'source_id':'original','passages':['2025년 연결 현금흐름','재무활동 700']}]}
        result=p.source_text(self.sources[0],packet)
        self.assertEqual(result,'2025년 연결 현금흐름\n[…]\n재무활동 700\n[…]\n기말현금 546')

    def test_structured_sheet_keeps_rows_not_selected_by_compression(self):
        source={**self.sources[0],'sheet':'임의 양식'}
        packet={'source_excerpts':[{'source_id':'original','passages':['기말현금 546']}]}
        self.assertEqual(p.source_text(source,packet),source['text'])

    def test_table_coverage_keeps_both_periods_of_pdf_row(self):
        source={**self.sources[0],'table_coverage':True}
        packet={'source_excerpts':[{'source_id':'original','passages':['기말현금 546']}]}
        self.assertEqual(p.source_text(source,packet),source['text'])

    def test_planned_table_anchor_stays_with_selected_topic(self):
        packet={'tables':[{'section':'summary_2','caption':'명단','columns':['명칭','위치'],'rows':['회사'],'reason':'근거'}]}
        result={'paragraphs':[{'topic_index':0,'source_ids':[]},{'topic_index':3,'source_ids':[]},{'topic_index':3,'source_ids':[]}],
                'planned_tables':{'T0':{'rows':{'R0':{'C1':'지역'}},'source_ids':['S1'],'anchor_topic':3,'after_paragraph_index':1}}}
        p.apply(result,packet,{'S1':{'id':'original'}})
        self.assertEqual(result['tables'][0]['after_paragraph_index'],2)
        self.assertEqual(result['paragraphs'][0]['source_ids'],[])
        self.assertEqual(result['paragraphs'][2]['source_ids'],['S1'])

    def test_source_unit_choices_allow_only_relevant_component(self):
        schema=p.obj({'paragraphs':{'type':'array'}})
        p.configure(schema,self.packet)
        p.set_aliases(schema,{'S1':{'text':'(단위: 백만원, %)'}})
        units=schema['properties']['planned_tables']['properties']['T0']['properties']['unit']['enum']
        self.assertIn('백만원',units);self.assertIn('%',units);self.assertIn('',units)
        self.assertNotIn('평가 개요',units)

    def test_spreadsheet_prompt_removes_addresses_without_losing_cells(self):
        source={'sheet':'임의 시트','text':'시트: 임의 시트\nA1=항목 | B1=2024 | C1=2025\nA2=매출 | B2=0 | C2=-12.5'}
        self.assertEqual(p.prompt_source_text(source),'시트: 임의 시트\n항목 | 2024 | 2025\n매출 | 0 | -12.5')
        self.assertIn('C2=-12.5',source['text'])

    def test_natural_language_search_is_split_without_company_specific_rules(self):
        terms=p.search_terms(['회사명 현금흐름표 기말 현금및현금성자산 2025'])
        self.assertIn('기말',terms);self.assertIn('현금및현금성자산',terms);self.assertNotIn('2025',terms)

    def test_planned_layout_preserves_zero_null_and_original_citations(self):
        packet=copy.deepcopy(self.packet)
        packet['tables'][0]['rows']=['실제 0','미확인']
        schema=p.obj({'tables':{'type':'array'},'paragraphs':{'type':'array'}})
        p.configure(schema,packet);p.set_aliases(schema,{'S1':self.sources[0]})
        self.assertNotIn('tables',schema['properties'])
        result={'paragraphs':[{'text':'본문 유지','source_ids':[]}], 'planned_tables':{'T0':{
            'unit':'백만원','rows':{'R0':{'C1_2025년':0},'R1':{'C1_2025년':None}},'source_ids':['S1'],'after_paragraph_index':0}}}
        p.apply(result,packet,{'S1':self.sources[0]})
        self.assertEqual(result['tables'][0]['rows'],[['실제 0',0],['미확인',None]])
        self.assertIn('백만원',result['tables'][0]['caption'])
        self.assertEqual(result['paragraphs'][0]['text'],'본문 유지')
        self.assertEqual(result['paragraphs'][0]['source_ids'],['S1'])


if __name__=='__main__':unittest.main()
