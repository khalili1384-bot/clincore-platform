import pandas as pd

from src.clincore.mcare_engine.mcare_sqlite_engine_v6_1 import (
    score_case,
    load_params,
)

DB_PATH = "src/clincore/mcare_engine/data/synthesis.135.db"
CONFIG_PATH = "src/clincore/mcare_engine/mcare_config_v6_1.json"

params = load_params(CONFIG_PATH)

case_df = pd.DataFrame([
    {"symptom_id": 13401754, "weight": 1.0},
    {"symptom_id": 13401755, "weight": 1.0},
])

result = score_case(
    db_path=DB_PATH,
    case_df=case_df,
    tags={},
    params=params,
    top_n=10,
    case_type="auto",
    course="chronic",   # فقط یک رشته بده
)

print("\n=== ENGINE OUTPUT ===\n")
print(result)