"""Read document text without executing embedded scripts or external links."""
import io
import re
import zipfile
import xml.etree.ElementTree as ET
import tempfile
import subprocess
import sys
from pathlib import Path


def extract(data, suffix):
    if suffix == '.hwp':
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'input.hwp'
            path.write_bytes(data)
            result = subprocess.run([sys.executable, '-X', 'utf8', '-c', 'from hwp5.hwp5txt import main; main()', str(path)], capture_output=True, timeout=60)
            if result.returncode:
                raise ValueError('암호 또는 배포용 보호를 해제한 HWP 5 문서를 사용해 주세요.')
            text = result.stdout.decode('utf-8').strip()
            if not text:
                raise ValueError('추출 가능한 HWP 본문이 없습니다.')
            return [('본문', text)]
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(i.file_size for i in archive.infolist()) > 100*1024*1024:
            raise ValueError('문서 압축 해제 크기는 100MB 이하여야 합니다.')
        patterns = {'.docx': r'word/(document|header\d+|footer\d+|footnotes|endnotes)\.xml',
                    '.pptx': r'ppt/(slides/slide\d+|notesSlides/notesSlide\d+)\.xml',
                    '.hwpx': r'Contents/section\d+\.xml'}
        names = sorted((n for n in archive.namelist() if re.fullmatch(patterns[suffix], n)),
                       key=lambda n: re.sub(r'\d+', lambda m:m[0].zfill(8),n))
        rows = []
        for name in names:
            root = ET.fromstring(archive.read(name))
            paragraphs = []
            for paragraph in root.iter():
                if paragraph.tag.rsplit('}',1)[-1] != 'p':
                    continue
                text = ''.join((e.text or '') for e in paragraph.iter() if e.tag.rsplit('}',1)[-1] == 't')
                if text.strip():
                    paragraphs.append(text)
            if paragraphs:
                rows.append((name, '\n'.join(paragraphs)))
        if not rows:
            raise ValueError('추출 가능한 본문이 없습니다. 이미지로만 된 문서는 텍스트가 포함된 문서로 저장해 주세요.')
        return rows
