# src/clincore/pipeline/engine_wrapper.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

import pandas as pd

from clincore.mcare_engine.mcare_sqlite_engine_v6_1 import load_params, score_case

DB_PATH = Path("src/clincore/mcare_engine/data/synthesis.135.db")
CFG_PATH = Path("src/clincore/mcare_engine/mcare_config_v6_1.json")


@dataclass(frozen=True)
class EngineResultItem:
    remedy_id: str
    score: float


class EngineError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def _build_case_df(symptom_ids: Sequence[int], weights: Sequence[float] | None = None) -> pd.DataFrame:
    if not symptom_ids:
        return pd.DataFrame({"symptom_id": [], "weight": []})

    if weights is None:
        weights = [1.0] * len(symptom_ids)

    if len(weights) != len(symptom_ids):
        raise EngineError("ENGINE_CRASH", "weights length must match symptom_ids length")

    return pd.DataFrame({"symptom_id": list(symptom_ids), "weight": list(weights)})


def run_engine(symptom_ids: Sequence[int], top_n: int = 5) -> List[Dict[str, Any]]:
    try:
        if not DB_PATH.exists():
            raise EngineError("ENGINE_CRASH", f"DB not found: {DB_PATH}")

        if not CFG_PATH.exists():
            raise EngineError("ENGINE_CRASH", f"Config not found: {CFG_PATH}")

        params = load_params(str(CFG_PATH))
        case_df = _build_case_df(symptom_ids)

        result_df = score_case(
            str(DB_PATH),
            case_df,
            {},  # tags
            params,
            int(top_n),
            "auto",
            "",  # course
        )

        if result_df is None or getattr(result_df, "empty", True):
            raise EngineError("EMPTY_RESULT", "Engine returned empty result")

        if "remedy" not in result_df.columns or "mcare_score" not in result_df.columns:
            raise EngineError("ENGINE_CRASH", f"Unexpected engine output columns: {list(result_df.columns)}")

        out = (
            result_df[["remedy", "mcare_score"]]
            .copy()
            .rename(columns={"remedy": "remedy_id", "mcare_score": "score"})
        )

        out["remedy_id"] = out["remedy_id"].astype(str)
        out["score"] = out["score"].astype(float)

        out = out.sort_values(by=["score", "remedy_id"], ascending=[False, True]).head(int(top_n))

        return [{"remedy_id": str(r.remedy_id), "score": float(r.score)} for r in out.itertuples(index=False)]

    except EngineError:
        raise
    except Exception as e:
        raise EngineError("ENGINE_CRASH", str(e)) from e
