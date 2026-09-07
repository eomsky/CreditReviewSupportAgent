import json
import os
from pathlib import Path
import httpx
from .models import Action


class ColabClient:
    def __init__(self):
        self.base_url = os.environ.get("LLM_BASE_URL", "").rstrip("/")
        self.model = os.environ.get("LLM_MODEL", "")
        if not self.base_url or not self.model:
            raise ValueError("Set LLM_BASE_URL and LLM_MODEL in the Codespaces environment")

    def complete(self, system: str, context: dict) -> str:
        key = os.environ.get("LLM_API_KEY", "")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        with httpx.Client(timeout=180) as client:
            response = client.post(self.base_url + "/chat/completions", headers=headers,
                json={"model": self.model, "temperature": 0.1, "max_tokens": 6000,
                      "messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": json.dumps(context, ensure_ascii=False)}]})
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    def next_action(self, context: dict) -> str:
        prompt = (Path(__file__).parent / "prompts" / "factor.md").read_text(encoding="utf-8")
        return self.complete(prompt + "\nJSON schema:\n" + json.dumps(Action.model_json_schema(), ensure_ascii=False), context)

    def synthesize(self, context: dict) -> str:
        return self.complete(
            '검증 가능한 심사 분석 초안을 JSON으로 작성한다. 내부 사고 전문은 출력하지 않는다. '
            '각 문단은 text, factor_ids, evidence_ids, calculation_ids를 가진다. '
            '출력 형식: {"title": str, "paragraphs": [...], "limitations": [str]}. '
            '요인 간 상충관계와 상환능력 영향을 종합한다. 미확인 사항은 유지하고 새로운 수치나 사실을 만들지 않는다. '
            '종합 판단과 초안은 최종 승인이나 검증 통과를 의미하지 않는다.', context)
