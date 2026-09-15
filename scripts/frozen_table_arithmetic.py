"""Same-row arithmetic from intact source-authored tables; no accounting inference."""
from decimal import Decimal
import re


def context(draft):
    records=[]
    for section in draft.get('sections',[draft]):
        for table in section.get('tables',[]):
            if table.get('source_binding',{}).get('method')!='exact_source_template':continue
            periods=[(i,str(c)) for i,c in enumerate(table['columns']) if i and re.search(r'20\d{2}',str(c)) and not re.search(r'추정|전망|예상',str(c))]
            for row in table['rows']:
                for ai,(i,start) in enumerate(periods):
                    for j,end in periods[ai+1:]:
                        if not all(type(row[k]) in (int,float) for k in (i,j)):continue
                        left,right=Decimal(str(row[i])),Decimal(str(row[j]))
                        records.append([row[0],start,end,row[i],row[j],str(right-left)])
            if records:
                # This packet only describes the arithmetic of this exact table.
                yield {'caption':table['caption'],'source_binding':table['source_binding'],'fields':['항목','시작기간','종료기간','시작값','종료값','증감(종료-시작)'],'comparisons':records,'status':'arithmetic_only'}
            records=[]
