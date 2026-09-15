import re

def format_caption(caption):
    text=re.sub(r'\s*\(단위\s*:\s*(?:해당 없음|없음|-)\)','',caption)
    if re.search(r'기업 기본|기업개요|기업 개요|사업 및 영업구조',text):
        text=re.sub(r'\s*·\s*(별도|연결)\s*,?\s*',' · ',text)
    else:text=re.sub(r'(별도|연결)(?=\s*[,·]|\s*20)',r'\1재무제표',text)
    text=re.sub(r'(20\d{2})[-./](\d{2})(?!\d)',lambda m:f'{m[1]}년 {int(m[2])}월 기준',text)
    return re.sub(r'기준\s*기준','기준',text)
