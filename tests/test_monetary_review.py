import json

import pytest

from credit_review.monetary_review import apply_monetary_review, run_monetary_review


def sample_report():
    return {
        'title': '보고서', 'case_id': 'case', 'review_date': '2026-09-09', 'mode': 'LIVE', 'draft': True,
        'sections': [{'title': '상환재원', 'paragraphs': [{
            'heading': '차입금',
            'text': '총차입금은 1,958,239,748천원이며 ~~검토중~~임.',
        }], 'tables': []}],
    }


def test_amount_and_cancellation_findings_are_saved_without_changing_report(tmp_path):
    report = sample_report()
    class Store:
        path = tmp_path
    class Harness:
        store = Store()
    class Client:
        def review_monetary_report(self, context):
            return json.dumps({'edits': [
                {'path': '/sections/0/paragraphs/0/text', 'old': '1,958,239,748천원',
                 'new': '19,582억원', 'kind': 'amount', 'occurrence': 1},
                {'path': '/sections/0/paragraphs/0/text', 'old': '~~검토중~~',
                 'new': '검토중', 'kind': 'cancellation', 'occurrence': 1},
            ]}, ensure_ascii=False)
    record = run_monetary_review(Harness(), Client(), report)
    revised = apply_monetary_review(report, record)
    assert revised == report
    assert [item['new'] for item in record['findings']] == ['19,582억원', '검토중']
    assert json.loads((tmp_path/'monetary_review.json').read_text(encoding='utf-8'))['status'] == 'COMPLETED'


@pytest.mark.parametrize('new', ['1,958천원', '1,958.2백만원', '1,958백만원', '19,581억원'])
def test_invalid_output_unit_or_decimal_is_rejected(tmp_path, new):
    report = sample_report()
    class Store:
        path = tmp_path
    class Harness:
        store = Store()
    class Client:
        def review_monetary_report(self, context):
            return json.dumps({'edits': [{
                'path': '/sections/0/paragraphs/0/text', 'old': '1,958,239,748천원',
                'new': new, 'kind': 'amount', 'occurrence': 1,
            }]}, ensure_ascii=False)
    record = run_monetary_review(Harness(), Client(), report)
    assert record['findings'] == []
    assert record['rejected_finding_count'] == 1
    assert (tmp_path/'monetary_review_raw.txt').exists()
