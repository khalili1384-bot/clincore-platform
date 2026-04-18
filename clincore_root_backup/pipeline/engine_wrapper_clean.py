# src/clincore/pipeline/engine_wrapper_clean.py

from pathlib import Path
import pandas as pd
import sqlite3

from clincore.mcare_engine.mcare_sqlite_engine_v6_1 import (
    score_case,
    load_params,
)

BASE_DIR = Path(__file__).resolve().parents[1]
ENGINE_DIR = BASE_DIR / "mcare_engine"
DB_PATH = ENGINE_DIR / "data" / "synthesis.135.db"
CONFIG_PATH = ENGINE_DIR / "mcare_config_v6_1.json"


class EngineError(Exception):
    pass


def run_engine(symptom_ids):
    """
    Phase 3 Engine Wrapper
    Ù…Ø·Ø§Ø¨Ù‚ Freeze v3
    """

    if not symptom_ids:
        raise EngineError("EMPTY_RESULT")

    try:
        # âœ… Ø³Ø§Ø®Øª DataFrame ØµØ­ÛŒØ­ Ø¨Ø§ weight
        case_df = pd.DataFrame({
            "symptom_id": symptom_ids,
            "weight": [1.0] * len(symptom_ids)
        })

        # Load params
        params = load_params(str(CONFIG_PATH))

        # Open sqlite connection
        con = sqlite3.connect(str(DB_PATH))

        result_df = score_case(
            str(DB_PATH),
            case_df,
            tags={},            # Ø·Ø¨Ù‚ engine interface
            params=params,
            top_n=5,
            case_type="auto",   # Ø¨Ø§ÛŒØ¯ lowercase Ø¨Ø§Ø´Ø¯
            course="acute"
        )

        con.close()

        if result_df.empty:
            raise EngineError("EMPTY_RESULT")

        # Sort deterministic
        result_df = result_df.sort_values(
            by=["score", "remedy_id"],
            ascending=[False, True]
        )

        top5 = result_df.head(5).to_dict(orient="records")

        return top5

    except EngineError:
        raise
    except Exception as e:
        raise EngineError(str(e))
