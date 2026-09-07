"""Build a self-contained, three-cell Colab LLM server notebook. No embedded secrets."""
import json
from pathlib import Path

CHECK = '''# 1. A100 80GB 확인 및 모델 설정
import os, sys, subprocess, shutil, time, json, secrets, re
from pathlib import Path
from urllib.request import Request, urlopen, urlretrieve
from google.colab import userdata

MODEL_ID = "google/gemma-4-26B-A4B-it"
CONTEXT_TOKENS = 49152  # input + output; request budget reserves 6000 output tokens
PORT = 8001
ROOT = Path("/content/credit_llm_server")
ROOT.mkdir(exist_ok=True)
gpu = subprocess.check_output([
    "nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"
], text=True).strip()
name, memory = gpu.splitlines()[0].rsplit(",", 1)
assert "A100" in name and int(memory.strip()) >= 75000, f"A100 80GB 필요. 현재: {gpu}"
os.environ["HF_TOKEN"] = userdata.get("HF_TOKEN")
assert os.environ["HF_TOKEN"], "Colab 보안 비밀에 HF_TOKEN을 등록하세요."
API_KEY = globals().get("API_KEY") or secrets.token_urlsafe(32)
print(f"GPU: {gpu} / 모델: {MODEL_ID}")
'''

INSTALL = '''# 2. 서버 전용 환경 설치 (최초 실행 시 몇 분 소요)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "uv"], check=True)
uv = shutil.which("uv")
env = ROOT / "venv"
if not (env / "bin/vllm").exists():
    subprocess.run([uv, "venv", "--python", sys.executable, "--seed", str(env)], check=True)
    subprocess.run([
        uv, "pip", "install", "--python", str(env / "bin/python"),
        "vllm", "sentencepiece", "protobuf", "ninja", "--pre",
        "--extra-index-url", "https://wheels.vllm.ai/nightly/cu129",
        "--extra-index-url", "https://download.pytorch.org/whl/cu129",
        "--index-strategy", "unsafe-best-match"
    ], check=True)
cloudflared = ROOT / "cloudflared"
if not cloudflared.exists():
    # Official release asset, verified against the GitHub asset digest when supplied.
    import hashlib
    request = Request("https://api.github.com/repos/cloudflare/cloudflared/releases/latest",
                      headers={"Accept": "application/vnd.github+json", "User-Agent": "CreditReviewSupportAgent"})
    release = json.load(urlopen(request))
    asset = next(a for a in release["assets"] if a["name"] == "cloudflared-linux-amd64")
    urlretrieve(asset["browser_download_url"], cloudflared)
    if asset.get("digest", "").startswith("sha256:"):
        assert hashlib.sha256(cloudflared.read_bytes()).hexdigest() == asset["digest"].split(":")[1]
    cloudflared.chmod(0o755)
print("서버 환경 준비 완료")
'''

SERVE = '''# 3. Gemma 4 시작 → 실제 응답 확인 → Codespaces 연결 파일 생성
os.environ["PATH"] = str(env / "bin") + os.pathsep + os.environ["PATH"]
headers = {"Authorization": f"Bearer {API_KEY}"}
def call(path, payload=None, timeout=10):
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(f"http://127.0.0.1:{PORT}{path}", data=data,
                  headers={**headers, "Content-Type": "application/json"})
    return json.load(urlopen(req, timeout=timeout))

if globals().get("server") and server.poll() is None:
    active_model = next(m for m in call("/v1/models")["data"] if m["id"] == MODEL_ID)
    if active_model.get("max_model_len") != CONTEXT_TOKENS:
        print("문맥 한도 변경을 위해 LLM 서버를 재시작합니다.", flush=True)
        server.terminate()
        try:
            server.wait(timeout=30)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=10)
if not globals().get("server") or server.poll() is not None:
    log = (ROOT / "vllm.log").open("w")
    server = subprocess.Popen([
        str(env / "bin/vllm"), "serve", MODEL_ID,
        "--host", "127.0.0.1", "--port", str(PORT), "--api-key", API_KEY,
        "--served-model-name", MODEL_ID, "--dtype", "bfloat16",
        "--gpu-memory-utilization", "0.90", "--max-model-len", str(CONTEXT_TOKENS),
        "--max-num-seqs", "4", "--max-num-batched-tokens", "8192",
        "--enable-prefix-caching", "--limit-mm-per-prompt", '{"image":0,"video":0,"audio":0}'
    ], stdout=log, stderr=subprocess.STDOUT, env=os.environ.copy(), start_new_session=True)
    for attempt in range(180):
        if server.poll() is not None:
            raise RuntimeError((ROOT / "vllm.log").read_text(errors="replace")[-6000:])
        try:
            call("/v1/models")
            break
        except Exception:
            if attempt % 6 == 0:
                print(f"모델 준비 중 · {attempt * 10}초", flush=True)
            time.sleep(10)
    else:
        raise TimeoutError("모델 준비 시간 초과. /content/credit_llm_server/vllm.log 확인")

reply = call("/v1/chat/completions", {"model": MODEL_ID,
    "messages": [{"role": "user", "content": "한국어로 준비 완료라고만 답하세요."}],
    "max_tokens": 128, "temperature": 0,
    "chat_template_kwargs": {"enable_thinking": False}}, timeout=180)
print("실제 모델 응답:", reply["choices"][0]["message"]["content"])
active_model = next(m for m in call("/v1/models")["data"] if m["id"] == MODEL_ID)
actual_context = active_model.get("max_model_len")
assert actual_context == CONTEXT_TOKENS, f"문맥 설정 불일치: requested={CONTEXT_TOKENS}, actual={actual_context}"
print(f"확인된 전체 문맥: {actual_context:,} tokens · 출력 6,000 tokens 별도 확보")

if not globals().get("tunnel") or tunnel.poll() is not None:
    tunnel_log = (ROOT / "tunnel.log").open("w")
    tunnel = subprocess.Popen([str(cloudflared), "tunnel", "--url", f"http://127.0.0.1:{PORT}",
                              "--no-autoupdate"], stdout=tunnel_log, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(60):
        matches = re.findall(r"https://[a-z0-9-]+\\.trycloudflare\\.com", (ROOT / "tunnel.log").read_text())
        if matches:
            SERVER_URL = matches[0]
            break
        if tunnel.poll() is not None:
            raise RuntimeError("연결 터널 실행 실패. tunnel.log 확인")
        time.sleep(2)
    else:
        raise TimeoutError("연결 주소 생성 시간 초과")

connection = {"base_url": SERVER_URL + "/v1", "model": MODEL_ID, "api_key": API_KEY,
              "context_tokens": actual_context}
config_file = ROOT / "llm_connection.json"
config_file.write_text(json.dumps(connection, indent=2))
config_file.chmod(0o600)
print("서버 주소:", connection["base_url"])
print("아래 연결 파일을 Codespaces workspace/llm_connection.json에 저장하세요. 키가 포함되어 있으므로 공유하지 마세요.")
from IPython.display import display, FileLink
display(FileLink(str(config_file)))
print("LLM 서버 실행 중입니다. 이 런타임이 종료되면 Codespaces 연결도 종료됩니다.", flush=True)
while server.poll() is None and tunnel.poll() is None:
    time.sleep(30)
raise RuntimeError("LLM 서버 또는 연결 터널이 종료되었습니다. 세 번째 셀을 다시 실행하세요.")
'''

def build():
    cells = [{"cell_type": "markdown", "metadata": {}, "source": [
        "# CreditReviewSupportAgent · Gemma 4 LLM 서버\n",
        "**A100 80GB · google/gemma-4-26B-A4B-it**\n\n",
        "런타임 → 런타임 유형 변경 → A100 GPU 및 고용량 RAM을 선택한 후 전체 실행하세요. 실제 GPU 메모리도 확인합니다.\n",
        "왼쪽 열쇠(보안 비밀)의 HF_TOKEN에 이 노트북의 접근을 허용해야 합니다.\n\n",
        "Colab은 추론만 수행합니다. 문서 처리·계산·심사보고서는 Codespaces에서 실행합니다.\n",
        "런타임이 종료되면 서버도 종료됩니다. 재시작 시 새 연결 파일을 사용하세요.\n\n",
        "설치 기준: [vLLM Gemma 4 가이드](https://docs.vllm.ai/projects/recipes/en/stable/Google/Gemma4.html)\n"
    ]}]
    for i, code in enumerate([CHECK, INSTALL, SERVE], 1):
        compile(code, f"cell_{i}", "exec")
        cells.append({"cell_type": "code", "metadata": {"id": f"server-{i}"},
                      "execution_count": None, "outputs": [], "source": code.splitlines(keepends=True)})
    nb = {"nbformat": 4, "nbformat_minor": 5, "metadata": {
        "colab": {"name": "CreditReviewSupportAgent_Gemma4_A100_Server.ipynb", "provenance": []},
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "accelerator": "GPU"}, "cells": cells}
    path = Path("notebooks/CreditReviewSupportAgent_Gemma4_A100_Server.ipynb")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(nb, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)

if __name__ == "__main__":
    build()
