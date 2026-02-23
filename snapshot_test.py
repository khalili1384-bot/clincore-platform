import pandas as pd
import json
from clincore.mcare_engine.mcare_sqlite_engine_v6_1 import score_case, load_params

db_path = r'src/clincore/mcare_engine/data/synthesis.db'
params = load_params(r'src/clincore/mcare_engine/mcare_config_v6_1.json')

tags = {}

case_df = pd.DataFrame({
    'symptom_id': [13401754, 13401755, 13401756],
    'weight': [1, 1, 1]
})

df = score_case(db_path, case_df, tags, params, 10, 'AUTO', 'chronic')

snapshot = {
    "total_remedies_evaluated": len(df),
    "top10": [
        {
            "remedy": r["remedy"],
            "mcare_score": round(float(r["mcare_score"]), 6),
            "raw_score": round(float(r["raw_score"]), 6),
        }
        for _, r in df.iterrows()
    ],
}

print(json.dumps(snapshot, indent=2))