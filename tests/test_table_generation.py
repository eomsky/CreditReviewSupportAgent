import json

from credit_review.table_generation import apply_table_plan, run_table_generation


def sample_report():
    return {
        'title': '보고서', 'case_id': 'case', 'review_date': '2026-09-09', 'mode': 'LIVE', 'draft': True,
        'sections': [{
            'title': '재무 분석',
            'paragraphs': [
                {'heading': '성장성 분석', 'text': '2024년 매출액은 20,922억원임.'},
                {'heading': '수익성 분석', 'text': '2025년 매출액은 20,772억원임.'},
            ],
            'tables': [],
        }],
    }


def test_grounded_table_is_inserted_after_selected_paragraph(tmp_path):
    report = sample_report()
    class Store:
        path = tmp_path
    class Harness:
        store = Store()
    class Client:
        def generate_report_tables(self, context):
            return json.dumps({'tables': [{
                'section_index': 0,
                'after_paragraph_index': 1,
                'caption': '매출액 추이',
                'columns': ['연도', '매출액'],
                'rows': [
                    {'cells': ['2024년', '20,922억원'],
                     'source_paths': ['/sections/0/paragraphs/0/text']},
                    {'cells': ['2025년', '20,772억원'],
                     'source_paths': ['/sections/0/paragraphs/1/text']},
                ],
            }]}, ensure_ascii=False)
    record = run_table_generation(Harness(), Client(), report)
    revised = apply_table_plan(report, record)
    assert revised['sections'][0]['tables'][0]['after_paragraph_index'] == 1
    assert revised['sections'][0]['tables'][0]['rows'][1] == ['2025년', '20,772억원']


def test_ungrounded_numeric_table_is_not_applied(tmp_path):
    report = sample_report()
    record = {
        'status': 'COMPLETED',
        'input_fingerprint': __import__('credit_review.table_generation', fromlist=['report_fingerprint']).report_fingerprint(report),
        'tables': [{
            'section_index': 0, 'after_paragraph_index': 0, 'caption': '임의 표',
            'columns': ['연도', '금액'],
            'rows': [{'cells': ['2024년', '99,999억원'],
                      'source_paths': ['/sections/0/paragraphs/0/text']}],
        }],
    }
    assert apply_table_plan(report, record) == report
