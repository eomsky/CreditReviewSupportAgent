import tempfile,unittest
from runtime_vector_store import IncrementalIndex


class IncrementalIndexTests(unittest.TestCase):
    def test_document_isolation_incremental_reuse_and_revised_source(self):
        with tempfile.TemporaryDirectory() as path:
            index=IncrementalIndex(path)
            try:
                # Synthetic short documents verify indexing mechanics, not 100 real PDFs.
                docs={f'd{i}':{'sources':[{'id':f'd{i}-s1','text':f'문서 {i}의 영업활동 현금흐름 및 차입금 현황'}]} for i in range(100)}
                index.ensure(docs)
                self.assertEqual(len(index.metrics),100)
                index.ensure(docs)
                self.assertEqual(len(index.metrics),100)
                hits=index.search('현금흐름','d13',4)
                self.assertEqual([key for key,score in hits],['d13-s1'])
                docs['d13']['sources']=[{'id':'d13-s2','text':'수정한 현금흐름과 투자자산'}]
                index.ensure(docs)
                self.assertEqual(len(index.metrics),101)
                self.assertEqual([key for key,score in index.search('현금흐름','d13',4)],['d13-s2'])
                self.assertEqual(index.search('현금흐름','unknown',4),[])
            finally:index.client.close()


if __name__=='__main__':unittest.main()
