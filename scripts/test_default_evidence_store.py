import unittest
from types import SimpleNamespace
from default_evidence_store import DefaultEvidenceStore


class DefaultEvidenceStoreTests(unittest.TestCase):
    def test_lazy_initialization_reuse_and_argument_preservation(self):
        original = SimpleNamespace(root='documents', get=lambda key: {'id': key})
        initialized, calls = [], []
        def factory(store, path):
            initialized.append((store, path))
            def select(*args, **kwargs):
                calls.append((args, kwargs)); return ['selected']
            return SimpleNamespace(select=select)
        store = DefaultEvidenceStore(original, 'index', factory)
        self.assertEqual(store.get('A'), {'id': 'A'})
        self.assertFalse(initialized)
        for _ in range(2):
            self.assertEqual(store.select(['cash'], [{'id': 'A'}], budget=100, limit=3), ['selected'])
        self.assertEqual(len(initialized), 1)
        self.assertEqual(calls[0], ((['cash'], [{'id': 'A'}]), {'budget': 100, 'limit': 3}))

    def test_initialization_failure_is_not_keyword_fallback(self):
        def factory(*args): raise RuntimeError('Index unavailable')
        store = DefaultEvidenceStore(SimpleNamespace(select=lambda *a: ['wrong fallback']), 'index', factory)
        with self.assertRaisesRegex(RuntimeError, 'Index unavailable'):
            store.select([], [])
        self.assertIsNone(store._retriever)

    def test_close_releases_index(self):
        closed = []
        retriever = SimpleNamespace(select=lambda *a, **k: [], vector=SimpleNamespace(client=SimpleNamespace(close=lambda: closed.append(True))))
        store = DefaultEvidenceStore(SimpleNamespace(), 'index', lambda *a: retriever)
        store.select([], []); store.close(); store.close()
        self.assertEqual(closed, [True])


if __name__ == '__main__': unittest.main()
