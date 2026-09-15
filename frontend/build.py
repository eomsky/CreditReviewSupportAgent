"""Build the standalone HTML without changing the supplied visual templates."""
from pathlib import Path
import base64
import re
import json

ROOT = Path(__file__).resolve().parent
outer = (ROOT / 'source/original.html').read_text(encoding='utf-8-sig')
inner = (ROOT / 'source/operating.html').read_text(encoding='utf-8-sig')
# Disable the obsolete workbench API. Only the parent connection owns requests.
inner = inner.replace('if(location.protocol!=="about:" && location.protocol!=="file:") hydrateWorkbench();', '// Requests are owned by the parent bridge.')
inner = inner.replace('</body>', '<script>\n' + (ROOT / 'frame.js').read_text(encoding='utf-8') + '\n</script></body>')
encoded = base64.b64encode(inner.encode()).decode()
outer, count = re.subn(r"atob\('[A-Za-z0-9+/=]+'\)", "atob('" + encoded + "')", outer)
assert count == 1, 'Expected one embedded operating document'
outer = outer.replace('</body>', '<script>\n' + (ROOT / 'stream.js').read_text(encoding='utf-8') + '\n</script></body>')
outer = outer.replace('</body>', '<script>\n' + (ROOT / 'display-text.js').read_text(encoding='utf-8') + '\n</script></body>')
template_data = base64.b64encode((ROOT / 'assets/양식_신용조사서.xlsx').read_bytes()).decode('ascii')
outer = outer.replace('</body>', '<script>window.CreditReviewTemplateData="' + template_data + '";</script></body>')
outer = outer.replace('</body>', '<script>window.CreditReviewWritingRules=' + json.dumps((ROOT.parent / 'prompts/review_writing_rules.txt').read_text(encoding='utf-8')+'\n\n'+(ROOT.parent / 'prompts/review_reasoning_rules.txt').read_text(encoding='utf-8').strip(),ensure_ascii=False).replace('<','\\u003c') + ';\n' + (ROOT / 'bridge.js').read_text(encoding='utf-8') + '\n</script></body>')
outer = outer.replace('</body>', '<script>\n' + (ROOT / 'presentation.js').read_text(encoding='utf-8') + '\n</script></body>')
outer = outer.replace('</body>', '<script>\n' + (ROOT / 'outline.js').read_text(encoding='utf-8') + '\n</script></body>')
outer = outer.replace('</body>', '<script>\n' + (ROOT / 'menu.js').read_text(encoding='utf-8') + '\n</script></body>')
outer = outer.replace('</body>', '<script>\n' + (ROOT / 'chat.js').read_text(encoding='utf-8') + '\n</script></body>')
outer = outer.replace('</body>', '<script>\n' + (ROOT / 'connection.js').read_text(encoding='utf-8') + '\n</script></body>')
outer = outer.replace('UI-TEST v0.1.65', 'UI v0.1.66')
outer = outer.replace('</body>', '<script>\n' + (ROOT / 'home.js').read_text(encoding='utf-8') + '\n</script></body>')
outer = outer.replace('</body>', '<script>\n' + (ROOT / 'upload_hint.js').read_text(encoding='utf-8') + '\n</script></body>')
outer = outer.replace('</body>', '<script>\n' + (ROOT / 'toolbar.js').read_text(encoding='utf-8') + '\n</script></body>')
(ROOT / 'CreditReviewSupportAgent_UI_v0.1.66.html').write_text(outer, encoding='utf-8')
app = outer.replace('</head>', '<style>\n' + (ROOT / 'app.css').read_text(encoding='utf-8') + '\n</style></head>')
app = app.replace('</body>', '<script>\n' + (ROOT / 'app.js').read_text(encoding='utf-8') + '\n</script></body>')
app = app.replace('UI v0.1.66', 'App v0.1.69')
(ROOT / 'CreditReviewSupportAgent_App_v0.1.69.html').write_text(app, encoding='utf-8')
print('Built standalone frontend')
