import unittest
from frozen_budget_search import fit_evidence, removal_order


class BudgetTests(unittest.TestCase):
    def test_matches_linear_boundary_and_protects_required(self):
        rows = [{'id':str(i),'document_id':str(i%3),'metadata':{'required':True},'size':10+i} for i in range(40)]
        protected = {'8','15'}
        order = removal_order(rows, protected)
        calls=[]
        def evaluate(items):
            calls.append(len(items))
            return [], {}, sum(s['size'] for s in items), 450
        result, _ = fit_evidence(rows, protected, evaluate, 50)
        expected=rows
        for n in range(len(order)+1):
            expected=[s for i,s in enumerate(rows) if i not in set(order[:n])]
            if sum(s['size'] for s in expected)+50<=450:break
        self.assertEqual(result,expected)
        self.assertTrue(protected <= {s['id'] for s in result})
        self.assertEqual({s['document_id'] for s in result},{'0','1','2'})
        self.assertLessEqual(len(calls),8)

    def test_over_budget_returns_all_protected_evidence(self):
        rows=[{'id':'a','document_id':'d','size':1000}]
        result,_=fit_evidence(rows,{'a'},lambda s:([],{},1000,100),50)
        self.assertEqual(result,rows)


if __name__ == '__main__': unittest.main()
