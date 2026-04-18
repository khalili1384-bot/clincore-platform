import json
import uuid
import hashlib
from datetime import datetime
from pathlib import Path


LOG_PATH = Path("data/case_logs.jsonl")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def log_case(
    symptom_ids: list[int],
    ranking_df,
    selected_remedy: str,
    outcome: str | None = None,
    followup_days: int | None = None,
    confidence_physician: int | None = None,
    engine_version: str = "v1-deterministic-engine",
    dataset_path: str = "src/clincore/mcare_engine/data/synthesis.db",
):
    case_entry = {
        "case_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "engine_version": engine_version,
        "dataset_hash": _hash_file(dataset_path),
        "symptom_ids": symptom_ids,
        "ranking_snapshot": [
            {
                "remedy": r["remedy"],
                "mcare_score": round(float(r["mcare_score"]), 6),
                "raw_score": round(float(r["raw_score"]), 6),
            }
            for _, r in ranking_df.iterrows()
        ],
        "selected_remedy": selected_remedy,
        "outcome": outcome,
        "followup_days": followup_days,
        "confidence_physician": confidence_physician,
    }

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(case_entry) + "\n")

    return case_entry["case_id"]