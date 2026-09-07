from __future__ import annotations

import hashlib
import json
import re
import uuid
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False, default=str)


def identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        raise ValueError("ID must contain only letters, digits, _ or -")
    return value


def atomic_json(path: Path, value: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(uuid.uuid4().hex + ".tmp")
    temp.write_text(json_text(value), encoding="utf-8")
    temp.replace(path)


class Store:
    def __init__(self, root: str | Path, case_id: str, run_id: str):
        self.path = Path(root) / "cases" / identifier(case_id) / "runs" / identifier(run_id)
        self.path.mkdir(parents=True, exist_ok=True)
        self._event_lock = threading.Lock()

    def put(self, stage: str, payload: dict, inputs: list[str] | None = None) -> str:
        aid = identifier(stage) + "_" + uuid.uuid4().hex
        artifact = {"schema_version": "0.1", "id": aid, "stage": stage,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "inputs": inputs or [], "payload": payload}
        artifact["sha256"] = hashlib.sha256(json_text(payload).encode()).hexdigest()
        path = self.path / "artifacts" / f"{aid}.json"
        path.parent.mkdir(exist_ok=True)
        atomic_json(path, artifact)
        return aid

    def get(self, aid: str) -> dict:
        return json.loads((self.path / "artifacts" / f"{identifier(aid)}.json").read_text(encoding="utf-8"))

    def event(self, **value):
        value["time"] = datetime.now(timezone.utc).isoformat()
        with self._event_lock, (self.path / "events.jsonl").open("a", encoding="utf-8") as out:
            out.write(json.dumps(value, ensure_ascii=False, default=str) + "\n")

    def artifacts(self):
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((self.path / "artifacts").glob("*.json"), key=lambda p: p.stat().st_mtime_ns)]
