import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


class TraceLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # "w" bảo đảm trace chỉ là lượt chạy mới nhất, không append.
        self.file = self.path.open("w", encoding="utf-8")

    def emit(
        self,
        case_id: str | None,
        event: str,
        payload: dict[str, Any],
    ) -> None:
        record = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "case_id": case_id,
            "event": event,
            "payload": payload,
        }
        self.file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.file.flush()

    def close(self) -> None:
        self.file.close()


def write_metadata(
    path: str | Path,
    total_cases: int,
    model_name: str,
    parameter_size_b: float,
) -> None:
    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": {
            "name": model_name,
            "parameter_size_b": parameter_size_b,
        },
        "framework": {
            "orchestration": "Python role-based deterministic multi-agent pipeline",
            "data_processing": f"pandas {pd.__version__}",
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "run": {
            "total_cases": total_cases,
            "trace_file": "logging/trace.jsonl",
        },
        "note": (
            "No external LLM is invoked in this version. "
            "Business decisions are deterministic EC_POLICY_V2 rules."
        ),
    }

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )