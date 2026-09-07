"""Versioned F01-F30 evidence requirements, independent from report layout."""
import json
from pathlib import Path

FACTORS = json.loads(Path(__file__).with_name("factors.json").read_text(encoding="utf-8"))
if set(FACTORS) != {f"F{i:02}" for i in range(1, 31)}:
    raise ValueError("Factor baseline requires F01-F30")
