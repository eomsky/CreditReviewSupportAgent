import unittest
from types import SimpleNamespace
from frozen_page_vector_sources import PageVectorStore, page_bundles


class PageEvidenceTests(unittest.TestCase):
    def test_atomic_page_and_global_rank(self):
        sources = [dict(id=str(i), page=p, text='x'*10,
                        bbox=[0,i,1,i+1]) for i,p in enumerate([1,1,2,2])]
        adapter = object.__new__(PageVectorStore)
        adapter.documents = {'doc': {'sources': sources}}
        adapter.keyword = SimpleNamespace(select=lambda *a, **k: [sources[2], sources[0]])
        adapter.vector = SimpleNamespace(search=lambda *a: [('3', .9), ('1', .8)])
        meta = dict(id='doc', name='test.pdf', priority='매우 중요', required=True)
        hits = adapter.select(['query'], [meta], budget=25, limit=1)
        self.assertEqual([s['id'] for s in hits], ['2','3'])
        self.assertEqual(sum(len(s['text']) for s in hits), 20)

    def test_toc_excluded_and_spreadsheet_sources_not_merged(self):
        rows = [dict(id='toc',page=1,format='pdf',text='.....\n.....\n.....'),
                dict(id='a',page=1,format='xlsx',text='a'),
                dict(id='b',page=1,format='xlsx',text='b')]
        self.assertEqual(set(page_bundles(rows)), {('source','a'),('source','b')})


if __name__ == '__main__': unittest.main()
