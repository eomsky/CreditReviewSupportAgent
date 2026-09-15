import copy,json,unittest
from pathlib import Path
from structuring_context_audit import augment


class ContextAuditTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'outputs/step_trials/C20.10s-step2-r1'
        self.request=json.loads((root/'refinement.request.json').read_text(encoding='utf-8'))
        self.draft=json.loads((root/'draft.json').read_text(encoding='utf-8'))
        self.evidence=json.loads((root/'evidence.json').read_text(encoding='utf-8'))

    def test_unknown_is_not_equal_basis(self):
        original=copy.deepcopy(self.request)
        out=augment(self.request,self.draft,self.evidence)
        schema=out['structured_outputs']['json']
        self.assertEqual(next(iter(schema['properties'])),'paragraph_context_audit')
        focus=json.loads(out['messages'][-1]['content'])['mandatory_context_review']
        self.assertTrue(focus)
        self.assertEqual(set(schema['properties']['paragraph_context_audit']['required']),{x['paragraph_id'] for x in focus})
        self.assertEqual(schema['properties']['quality_checks']['properties']['conflicting_basis']['properties']['status']['enum'],['unresolved'])
        self.assertEqual(self.request,original)

    def test_known_basis_does_not_add_unknown_constraint(self):
        evidence=copy.deepcopy(self.evidence)
        for source in evidence:
            table=json.loads(source['text']);table['basis']='consolidated';source['text']=json.dumps(table)
        self.assertEqual(augment(self.request,self.draft,evidence),self.request)


if __name__=='__main__':unittest.main()
