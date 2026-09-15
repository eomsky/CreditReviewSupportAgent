"""Recognize accounting parentheses during lexical source support checks."""
import ast

HELPER='''
def lexical_numbers(quote):
    tokens=re.findall(r'\\(\\s*\\d[\\d,]*(?:\\.\\d+)?\\s*\\)|-?\\d[\\d,]*(?:\\.\\d+)?',quote)
    values=[]
    for token in tokens:
        negative=token.startswith('(')
        value=float(token.strip('() ').replace(',',''))
        values.append(-value if negative else value)
    return values

'''


def patch(source):
    old="numbers=[float(x.replace(',','')) for x in re.findall(r'-?\\d[\\d,]*(?:\\.\\d+)?',quote)]"
    assert source.count(old)==1
    source=source.replace('def validate(packet, sources):',HELPER+'def validate(packet, sources):')
    source=source.replace(old,'numbers=lexical_numbers(quote)')
    ast.parse(source)
    return source
