"""Assemble C9 into a separate preflight tree without importing the app or calling LLM."""
import ast,sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
runner = root / 'scripts/frozen_full_test.py'
source = runner.read_text(encoding='utf-8').split('import live_html_test as app', 1)[0]
candidate=sys.argv[1] if len(sys.argv)>1 else 'C9'
assert candidate in ('C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20')
source = source.replace("ID=sys.argv[1] if len(sys.argv)>1 else 'F3'", f"ID={candidate!r}")
source = source.replace("OUT=ROOT/'outputs/frozen_candidates'/RUNID", f"OUT=ROOT/'outputs/frozen_candidates/{candidate}-assembly-preflight'")
suffix=sys.argv[2] if len(sys.argv)>2 else ''
if suffix:source=source.replace(f'{candidate}-assembly-preflight',f'{candidate}-assembly-preflight-{suffix}')
namespace = {'__file__': str(runner), '__name__': '__main__'}
exec(compile(source, str(runner), 'exec'), namespace)
files = list(namespace['CODE'].rglob('*.py')) + list(namespace['harness'].glob('*.py'))
for path in files:
    ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
print(candidate,'combined assembly and syntax passed:', len(files), 'files; no model calls')
