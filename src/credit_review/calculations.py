"""Execute LLM-authored Python in a disposable, networkless Docker container."""
import json
import math
import os
import subprocess
import tempfile
from pathlib import Path
import pandas as pd

from .models import Dataset, Calculation
from .store import json_text


def validate_dataset(dataset: Dataset, allowed_sources: set[str]) -> pd.DataFrame:
    if dataset.scope == "UNKNOWN":
        raise ValueError("연결/별도 확인 전 계산 불가")
    if not dataset.entity.strip():
        raise ValueError("Entity required")
    for column in dataset.columns:
        if column.dtype in ("number", "integer") and not column.unit:
            raise ValueError(f"Numeric column requires an explicit unit: {column.name}")
    for row, refs in zip(dataset.rows, dataset.cell_sources):
        for col, value in row.items():
            if value is not None and not set(refs[col]).issubset(allowed_sources):
                raise ValueError(f"Unknown evidence for {col}")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("Nonfinite input")
    df = pd.DataFrame(dataset.rows)
    if df[dataset.period_column].isna().any():
        raise ValueError("Period cannot be missing")
    return df


class DockerExecutor:
    def execute(self, plan: Calculation, datasets: dict[str, dict]) -> dict:
        if set(plan.dataset_ids) != set(datasets):
            raise ValueError("Dataset inputs do not match plan")
        image = os.environ.get("CALC_IMAGE", "credit-review-calculator:0.1")
        with tempfile.TemporaryDirectory(prefix="credit-calc-") as temp:
            root = Path(temp)
            (root / "input.json").write_text(json_text(datasets), encoding="utf-8")
            (root / "analysis.py").write_text(plan.code, encoding="utf-8")
            name = "credit-calc-" + root.name.lower().replace("_", "-")
            cmd = ["docker", "run", "--rm", "--name", name, "--network=none", "--read-only",
                   "--cpus=1", "--memory=512m", "--pids-limit=64", "--cap-drop=ALL",
                   "--security-opt=no-new-privileges", "--user=65534:65534",
                   "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m", "--ulimit", "fsize=1048576:1048576",
                   "-v", f"{root.resolve()}:/input:ro", image]
            root.chmod(0o755)
            for p in root.iterdir():
                p.chmod(0o644)
            with tempfile.TemporaryFile() as output:
                try:
                    completed = subprocess.run(cmd, stdout=output, stderr=subprocess.STDOUT, timeout=40)
                    output.seek(0)
                    raw = output.read(1_000_001)
                    if len(raw) > 1_000_000:
                        raise ValueError("Calculation output limit exceeded")
                    text = raw.decode("utf-8", errors="replace")
                    if completed.returncode:
                        raise RuntimeError(text[-4000:])
                    result = json.loads(text)
                    json.dumps(result, allow_nan=False)
                    return {"status": "EXECUTED", "result": result, "executor": "docker", "image": image,
                            "verification": "execution_only; semantic correctness requires review"}
                except subprocess.TimeoutExpired as error:
                    subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=10)
                    raise RuntimeError("Calculation exceeded 40 seconds") from error
