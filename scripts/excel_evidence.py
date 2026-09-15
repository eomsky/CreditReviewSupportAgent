"""Render original workbook regions with Microsoft Excel, never rebuild cells."""
import io
import re
import subprocess
import tempfile
import threading
from pathlib import Path

import pymupdf
from PIL import Image

_lock = threading.Lock()


def render(data, source, suffix):
    # Coordinates originate in the extraction, not in model-generated text.
    if suffix == 'xlsx':
        cells = re.findall(r'(?:^|\n| \| )([A-Z]+)(\d+)=', source['text'])
        def column(label):
            value = 0
            for char in label:
                value = value * 26 + ord(char) - 64
            return value
        coords = [(int(row), column(col)) for col, row in cells]
    else:
        coords = [(int(r), int(c)) for r, c in re.findall(r'(?:^|\n| \| )R(\d+)C(\d+)=', source['text'])]
    if not coords:
        raise ValueError('엑셀 근거의 셀 위치를 찾을 수 없습니다.')
    def letter(n):
        result = ''
        while n:
            n, rem = divmod(n-1, 26)
            result = chr(65+rem)+result
        return result
    region = f'{letter(min(c for r,c in coords))}{min(r for r,c in coords)}:{letter(max(c for r,c in coords))}{max(r for r,c in coords)}'
    with _lock, tempfile.TemporaryDirectory(prefix='credit-excel-') as temp:
        book = Path(temp)/('source.'+suffix)
        pdf = Path(temp)/'region.pdf'
        book.write_bytes(data)
        result = subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
            str(Path(__file__).with_name('render_excel_region.ps1')),
            '-Source',str(book),'-Sheet',source['sheet'],'-Range',region,'-Output',str(pdf)],
            capture_output=True, timeout=90, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode or not pdf.exists():
            raise ValueError('Excel 원문 이미지 생성에 실패했습니다. 원본 파일을 확인해 주세요.')
        pages=[]
        with pymupdf.open(pdf) as document:
            for page in document:
                pix=page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False)
                pages.append(Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGB'))
        canvas=Image.new('RGB',(max(p.width for p in pages),sum(p.height for p in pages)),'white')
        y=0
        for page in pages:
            canvas.paste(page,(0,y));y+=page.height
        buffer=io.BytesIO();canvas.save(buffer,format='PNG')
        return buffer.getvalue()
