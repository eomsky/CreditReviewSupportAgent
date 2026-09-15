import ast
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import business_report_test as api
from frozen_exact_template_patch import patch as source_patch
from frozen_budget_search_patch import patch as budget_patch


class ExactTemplateIntegrationTests(unittest.TestCase):
    def test_complete_copies_source_table_without_model_numeric_output(self):
        path=Path(api.__file__)
        tree=ast.parse(budget_patch(source_patch(path.read_text(encoding='utf-8'))))
        function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='complete')
        scope=dict(api.__dict__)
        scope['token_count']=lambda messages:(100,32768)
        exec(compile(ast.Module(body=[function],type_ignores=[]),'<patched-complete>','exec'),scope)
        template=dict(caption='검토표 (단위: 백만원)',columns=['항목','전전기','전기','당기','추정1기'],labels=['매출'],customer=False)
        evidence=[dict(id='original-cell-range',document_id='doc',format='xlsx',sheet='자료',text='A1=검토표 (단위: 백만원)\nA2=항목 | B2=2022-12 | C2=2023-12 | D2=2024-12 | E2=추정1기\nA3=매출 | B3=11 | C3=12 | D3=13 | E3=14')]
        packet=dict(facts=[],tables=[],numeric_evidence=[],source_excerpts=[],search_queries=[])
        captured=[]
        def model(*args,**kwargs):
            request=args[2];captured.append(request)
            response={'title':'시험','paragraphs':[{'text':'주요사항','source_ids':['S1']}],
                      'analysis_paragraphs':[{'text':'상세 분석1','source_ids':['S1']},{'text':'상세 분석2','source_ids':['S1']}]}
            return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(response)}}]}
        with tempfile.TemporaryDirectory() as tmp, patch.object(api.app,'config',return_value={'model':'test'}), patch.dict(api.fixed_review_tables.TEMPLATES,{'financial_accounts':[template]},clear=True), patch.object(api.prepared_context,'prepare',return_value=copy.deepcopy(packet)), patch.object(api.llm_recovery,'complete',side_effect=model):
            result=scope['complete'](Path(tmp),'financial_accounts','본문을 작성한다.',evidence,{},manifest=[])
        self.assertNotIn('fixed_tables',captured[0]['structured_outputs']['json']['properties'])
        self.assertEqual(result['tables'][0]['rows'],[['매출',11,12,13,14]])
        self.assertEqual(result['tables'][0]['columns'][1:4],['2022-12','2023-12','2024-12'])
        self.assertEqual(len(result['paragraphs']),3)
        self.assertEqual(result['paragraphs'][0]['sources'][0]['id'],'original-cell-range')
        self.assertTrue(result['tables'][0]['source_binding']['semantic_review_required'])


if __name__ == '__main__':unittest.main()
