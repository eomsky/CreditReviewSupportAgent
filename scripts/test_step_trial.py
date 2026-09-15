import tempfile
import unittest
from pathlib import Path
from step_trial import initialize, trial, judge, save, read


class StepTrialTest(unittest.TestCase):
    def test_past_artifact_never_invokes_transport_or_claims_quality(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save(root/'req.json', {'messages': []})
            save(root/'resp.json', {'existing': 'output'})
            initialize(root/'step', root/'req.json', 60, root/'resp.json')
            result = trial(root/'step', root, lambda _: self.fail('Past step was rerun'))
            self.assertTrue(result['reused'])
            self.assertEqual(read(root/'step/state.json')['quality'], 'unassessed')

    def test_only_reviewed_pass_is_locked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save(root/'req.json', {'messages': []})
            initialize(root/'step', root/'req.json', 60)
            response = {'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]}
            trial(root/'step', root, lambda _: response)
            self.assertEqual(read(root/'step/state.json')['status'], 'awaiting_quality_review')
            with self.assertRaises(ValueError):
                trial(root/'step', root, lambda _: self.fail('Unjudged step rerun'))
            (root/'qa.md').write_text('Test fixture assessment', encoding='utf-8')
            judge(root/'step', True, root/'qa.md')
            self.assertTrue(trial(root/'step', root, lambda _: self.fail('Pass rerun'))['reused'])

    def test_twenty_second_tolerance_requires_quality_and_complete_response(self):
        from unittest.mock import patch
        for elapsed, accepted in [(60, True), (80, True), (80.001, False)]:
            with self.subTest(elapsed=elapsed), tempfile.TemporaryDirectory() as temp:
                root=Path(temp)
                save(root/'req.json', {'messages': []})
                initialize(root/'step', root/'req.json', 60)
                with patch('step_trial.time.monotonic', side_effect=[0, elapsed]):
                    result=trial(root/'step', root, lambda _: {'choices':[{'finish_reason':'stop'}]})
                self.assertEqual(read(root/'step/state.json')['status'], 'awaiting_quality_review')
                (root/'qa.md').write_text('Source assessment fixture', encoding='utf-8')
                if accepted:
                    judge(root/'step', True, root/'qa.md')
                    self.assertEqual(read(root/'step/state.json')['time_status'], 'pass' if elapsed<=60 else 'provisional_pass')
                else:
                    with self.assertRaises(ValueError): judge(root/'step', True, root/'qa.md')

    def test_truncated_response_is_failure_and_can_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save(root/'req.json', {'messages': []})
            initialize(root/'step', root/'req.json', 60)
            truncated = {'choices': [{'finish_reason': 'length'}]}
            self.assertEqual(trial(root/'step', root, lambda _: truncated)['status'], 'fail')
            self.assertEqual(trial(root/'step', root, lambda _: truncated)['status'], 'fail')
            self.assertEqual(len(read(root/'step/state.json')['attempts']), 2)


if __name__ == '__main__': unittest.main()
