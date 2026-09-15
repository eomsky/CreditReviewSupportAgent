import unittest
from frozen_review_reason_bound import bound_schema


class ExplanationBoundTests(unittest.TestCase):
    def test_internal_only_preserves_required_and_body(self):
        original = {'type':'object','required':['reason','text','rows'],'properties':{
            'reason':{'type':'string'},'text':{'type':'string'},
            'rows':{'type':'array','items':{'properties':{'reason':{'type':'string','maxLength':100}}}}}}
        changed = bound_schema(original)
        self.assertEqual(changed['required'],original['required'])
        self.assertEqual(changed['properties']['text'],original['properties']['text'])
        self.assertEqual(changed['properties']['reason']['maxLength'],320)
        self.assertEqual(changed['properties']['rows']['items']['properties']['reason']['maxLength'],100)
        self.assertNotIn('maxLength',original['properties']['reason'])


if __name__ == '__main__': unittest.main()
