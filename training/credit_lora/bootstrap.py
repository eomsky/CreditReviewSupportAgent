"""Create a training-only overlay without changing the inference environment."""
import argparse
import json
import subprocess
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--inference-python',default='/content/credit_llm_server/venv/bin/python')
p.add_argument('--environment',default='/content/credit_training/venv')
a=p.parse_args()
root=Path(a.environment)
if not (root/'bin/python').exists():
    subprocess.run([a.inference_python,'-m','venv',str(root)],check=True)
inference_sites=json.loads(subprocess.check_output([a.inference_python,'-c',
    'import site,json; print(json.dumps(site.getsitepackages()))'],text=True))
python=str(root/'bin/python')
site_path=Path(json.loads(subprocess.check_output([python,'-c',
    'import site,json; print(json.dumps(site.getsitepackages()))'],text=True))[0])
(site_path/'inference_dependencies.pth').write_text('\n'.join(inference_sites)+'\n')
subprocess.run([python,'-m','pip','install','peft>=0.19.0','accelerate>=1.10.0',
                'bitsandbytes>=0.49.0'],check=True)
subprocess.run([python,'-c',
    "import torch,transformers,peft,accelerate,bitsandbytes; import importlib.metadata as m; "
    "print({x:m.version(x) for x in ['torch','transformers','peft','accelerate','bitsandbytes']})"],check=True)
