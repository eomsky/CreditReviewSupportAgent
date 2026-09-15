import ast


def semantic(source):
    marker="    draft['semantic_table_review']=audit"
    assert source.count(marker)==1
    source=source.replace(marker,"    from frozen_table_integrity import preserve\n    preserve(memory['draft'],draft)\n"+marker)
    ast.parse(source)
    return source


def refinement(source):
    marker='    report_table_review.apply(result,response,evidence)'
    assert source.count(marker)==1
    source=source.replace(marker,marker+'\n    from frozen_table_integrity import preserve\n    preserve(draft,result)')
    ast.parse(source)
    return source
