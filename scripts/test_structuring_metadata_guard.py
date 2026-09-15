import copy,json,unittest
from pathlib import Path
from structuring_metadata_guard import apply
ROOT=Path(__file__).resolve().parents[1]/'outputs/step_trials/C20.10s-step2-r1'
class MetadataGuardTest(unittest.TestCase):
    def test_saved_response_cannot_erase_unknown_basis(self):
        result=json.loads((ROOT/'reviewed-artifact.json').read_text());evidence=json.loads((ROOT/'evidence.json').read_text())
        original=copy.deepcopy(result);guarded=apply(result,evidence)
        self.assertEqual(guarded['paragraphs'],original['paragraphs']);self.assertEqual(guarded['tables'],original['tables'])
        self.assertTrue(guarded['refinement']['information_guidance']['needed_contents'])
        self.assertEqual(next(c for c in guarded['refinement']['quality_checks'] if c['category']=='conflicting_basis')['status'],'unresolved')
        self.assertEqual(apply(guarded,evidence),guarded)
        self.assertEqual(result,original)
    def test_no_unknown_used_source_does_not_invent_gap(self):
        result={'paragraphs':[{'sources':[{'id':'S1'}]}],'refinement':{'remaining_gaps':[]}}
        sources=[{'id':'S1','text':json.dumps({'table_id':'T1','basis':'standalone'})},{'id':'S2','text':json.dumps({'table_id':'T2','basis':'unknown'})}]
        self.assertEqual(apply(result,sources),result)
if __name__=='__main__':unittest.main()
