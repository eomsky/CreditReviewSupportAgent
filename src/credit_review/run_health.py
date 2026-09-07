"""Persist user-visible execution outcomes without exposing tokens or raw payloads."""
import json
from datetime import datetime, timezone
from .store import atomic_json


def service_failure(error):
    value = str(error).lower()
    return any(x in value for x in ("httpstatuserror", "server error", "client error", "connecterror",
        "timeout", "timed out", "connection", "disconnected", "set llm_", "configured model"))


def explain_failure(error):
    value = str(error).lower()
    if "active writer" in value:
        return "이 보고서가 다른 실행에서 작성 중입니다. 진행 중인 실행이 끝난 뒤 이어서 작성할 수 있습니다."
    if "530" in value:
        return "Colab 연결 터널이 응답하지 않습니다(HTTP 530). Colab 서버와 연결 주소를 복구해야 합니다."
    if any(x in value for x in ("401", "403")):
        return "LLM 서버 인증이 거부됐습니다. 현재 서버의 연결 파일을 다시 적용해야 합니다."
    if "timeout" in value or "timed out" in value:
        return "LLM 응답 대기시간을 초과했습니다. 서버 상태를 확인한 뒤 이어서 실행할 수 있습니다."
    if service_failure(error):
        return "LLM 서버 연결이 끊겼거나 설정을 읽지 못했습니다. 연결 복구 후 이어서 실행할 수 있습니다."
    if "context" in value or "token" in value:
        return "분석 자료가 모델의 입력 한도를 초과했습니다. 입력 범위를 줄여 재시도해야 합니다."
    if "json" in value or "validation" in value or "schema" in value or "cites" in value:
        return "모델 응답의 구조 또는 근거 검증을 통과하지 못했습니다. 확인된 결과는 보존했습니다."
    return "현재 단계의 실행에 실패했습니다. 상세 오류는 내부 기록에 저장했고 기존 결과는 보존했습니다."


def checkpoint(h, status, stage, question="", reason=""):
    record = dict(status=status, stage=stage, question=question, reason=reason,
                  updated_at=datetime.now(timezone.utc).isoformat())
    atomic_json(h.store.path / "run_status.json", record)
    return record


def saved_status(h):
    path = h.store.path / "run_status.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def status_message(record):
    text = f"마지막 단계: {record['stage']}"
    if record.get('question'):
        text += f"\n\n검토 질문: {record['question']}"
    if record.get('reason'):
        text += f"\n\n중단 원인: {record['reason']}"
    if record['status'] in ('FAILED', 'PARTIAL'):
        text += "\n\n작성된 본문과 계산 결과는 보존되어 있습니다. 원인 해결 후 ‘보고서 작성 계속’으로 이어갈 수 있습니다."
    return text
