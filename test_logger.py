import pandas as pd
from clincore.mcare_engine.mcare_sqlite_engine_v6_1 import score_case, load_params
from clincore.mcare_engine.case_logger import log_case

db_path = r"src/clincore/mcare_engine/data/synthesis.db"
params = load_params(r"src/clincore/mcare_engine/mcare_config_v6_1.json")

case_df = pd.DataFrame({
    "symptom_id": [13401754, 13401755, 13401756],
    "weight": [1, 1, 1],
})

df = score_case(db_path, case_df, {}, params, 10, "AUTO", "chronic")

case_id = log_case(
    symptom_ids=[13401754, 13401755, 13401756],
    ranking_df=df,
    selected_remedy="caust",
    outcome=None,
    followup_days=None,
    confidence_physician=None,
)

print("Logged case:", case_id)
