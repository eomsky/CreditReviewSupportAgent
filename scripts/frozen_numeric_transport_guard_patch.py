"""Do not render model transport references as financial cell values."""
import ast

def patch(source):
    marker="            if t.get('fixed_template') and not customer and isinstance(original[0],str):"
    assert source.count(marker)==1
    source=source.replace(marker,"            for ci,value in enumerate(original):\n                if ci and type(value) in (int,float):cells[f'C{ci}']['type']=['number','null']\n"+marker)
    marker="            if any(isinstance(v,(int,float)) for v in values) and not row['source_ids']:"
    assert source.count(marker)==1
    source=source.replace(marker,"            transport_reference=any(isinstance(v,str) and re.fullmatch(r'S\\d+\\s*[,|:]\\s*L\\d+\\s*[,|:]\\s*N\\d+',v.strip()) for v in values)\n            if transport_reference or (any(isinstance(v,(int,float)) for v in values) and not row['source_ids']):")
    ast.parse(source)
    return source
