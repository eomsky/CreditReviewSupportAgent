import contextlib
import io
import json
import resource
import pandas as pd
import numpy as np

resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
with open('/input/input.json') as f:
    inputs = json.load(f)
dfs = {key: pd.DataFrame(value['rows']) for key, value in inputs.items()}
namespace = {'dfs': dfs, 'pd': pd, 'np': np}
with open('/input/analysis.py') as f:
    code = f.read()
# Docker is the isolation boundary. This is NOT a Python eval sandbox.
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(code, 'analysis.py', 'exec'), namespace)
if 'result' not in namespace:
    raise ValueError('Code must assign JSON-serializable result')
print(json.dumps(namespace['result'], ensure_ascii=False, allow_nan=False))
