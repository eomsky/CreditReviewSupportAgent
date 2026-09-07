import json
import os
import re
from pathlib import Path
import httpx
from .models import Action


def structured_content(content):
    if not isinstance(content, str) or not content.strip():
        raise ValueError("LLM returned empty structured content")
    content = content.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", content, re.DOTALL | re.IGNORECASE)
    if fenced:
        content = fenced.group(1).strip()
    if not isinstance(json.loads(content), dict):
        raise ValueError("LLM response must be a JSON object")
    return content


class ColabClient:
    def __init__(self):
        config_path = Path(os.environ.get("CREDIT_WORKSPACE", "workspace")) / "llm_connection.json"
        config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
        self.base_url = os.environ.get("LLM_BASE_URL", config.get("base_url", "")).rstrip("/")
        self.model = os.environ.get("LLM_MODEL", config.get("model", ""))
        self.key = os.environ.get("LLM_API_KEY", config.get("api_key", ""))
        if not self.base_url or not self.model:
            raise ValueError("Set LLM_BASE_URL and LLM_MODEL in the Codespaces environment")

    def check(self):
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        with httpx.Client(timeout=15) as client:
            response = client.get(self.base_url + "/models", headers=headers)
            response.raise_for_status()
            available = {m["id"] for m in response.json().get("data", [])}
            if self.model not in available:
                raise ValueError("Configured model is not served by the LLM endpoint")

    def complete(self, system: str, context: dict) -> str:
        serialized = json.dumps(context, ensure_ascii=False)
        if len(serialized) > int(os.environ.get("LLM_MAX_CONTEXT_CHARS", "120000")):
            raise ValueError("Context exceeds configured budget; narrow evidence before retrying")
        key = self.key
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        with httpx.Client(timeout=180) as client:
            response = client.post(self.base_url + "/chat/completions", headers=headers,
                json={"model": self.model, "temperature": 0.1, "max_tokens": 6000,
                      "response_format": {"type": "json_object"},
                      "messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": serialized}]})
            response.raise_for_status()
            return structured_content(response.json()["choices"][0]["message"]["content"])

    def next_action(self, context: dict) -> str:
        prompt = (Path(__file__).parent / "prompts" / "factor.md").read_text(encoding="utf-8")
        return self.complete(prompt + "\nJSON schema:\n" + json.dumps(Action.model_json_schema(), ensure_ascii=False), context)

    def synthesize(self, context: dict) -> str:
        return self.complete(
            '검증 가능한 심사 분석 초안을 JSON으로 작성한다. 내부 사고 전문은 출력하지 않는다. '
            '각 문단은 text, factor_ids, evidence_ids, calculation_ids를 가진다. '
            '출력 형식: {"title": str, "paragraphs": [...], "limitations": [str]}. '
            '요인 간 상충관계와 상환능력 영향을 종합한다. 미확인 사항은 유지하고 새로운 수치나 사실을 만들지 않는다. '
            '사용자에게는 완결된 심사보고서 문체로 작성한다. 미분석 개수, 요인 ID, 누락 슬롯이나 추가 확인 체크리스트는 본문에 출력하지 않는다. '
            '자료 한계가 판단에 실질적인 영향을 주면 단정하지 말고 해당 판단의 범위와 조건을 자연스러운 분석 문장에 담는다. '
            '종합 판단과 초안은 최종 승인이나 검증 통과를 의미하지 않는다.', context)
