"""Recheck populated, unbound numeric tables without treating them as empty output."""
import ast


def patch(source):
    marker='def terms(draft):'
    helper='''def verification_targets(draft):
    targets=missing(draft)
    for si,section in enumerate(sections(draft)):
        for ti,table in enumerate(section.get('tables',[])):
            if table.get('source_binding') or table.get('materialized_cells') or table.get('semantic_review_completed'):
                continue
            financial=table.get('template_id')=='summary2_financials' or bool(re.search(r'재무|손익|현금흐름',table.get('caption','')))
            if not financial:continue
            for ri,row in enumerate(table.get('rows',[])):
                for column,value in enumerate(row[1:],1):
                    if isinstance(value,(int,float)) and not isinstance(value,bool):
                        heading=str(table['columns'][column])
                        period=re.search(r'20\\d{2}',heading)
                        label=str(row[0]) if period else heading
                        period=period[0] if period else next((str(x) for x in row if re.search(r'20\\d{2}',str(x))),'')
                        targets[f'T{si}_{ti}_{ri}_{column}']={'label':label,'period':period}
    return targets


'''
    assert source.count(marker)==1
    source=source.replace(marker,helper+marker)
    source=source.replace("for c in missing(draft).values():", "for c in verification_targets(draft).values():")
    source=source.replace("labels=list(dict.fromkeys(c['label'] for c in missing(draft).values()))", "labels=list(dict.fromkeys(c['label'] for c in verification_targets(draft).values()))")
    marker="        # Search each missing measure independently; common years must not crowd it out."
    source=source.replace(marker,"        if any(term in label for term in ('매출','영업이익','순이익','금융비용')):aliases+=['손익계산서']\n"+marker)
    ast.parse(source)
    return source


def business(source):
    old="if report_table_review.missing(memory['draft']) or customer_table:"
    assert source.count(old)==1
    source=source.replace(old,"if report_table_review.verification_targets(memory['draft']) or customer_table:")
    ast.parse(source)
    return source
