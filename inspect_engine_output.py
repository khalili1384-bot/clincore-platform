import sqlite3
from clincore.pipeline.engine_wrapper import run_engine
from clincore.mcare_engine.mcare_sqlite_engine_v6_1 import score_case, load_params
import pandas as pd

db = r"src\clincore\mcare_engine\data\synthesis.135.db"
cfg = r"src\clincore\mcare_engine\mcare_config_v6_1.json"

# get real symptom_ids
con = sqlite3.connect(db)
cur = con.cursor()
cur.execute("SELECT DISTINCT symptom_id FROM symptom_remedies LIMIT 5")
symptom_ids = [r[0] for r in cur.fetchall()]
con.close()

params = load_params(cfg)
df = pd.DataFrame({"symptom_id": symptom_ids, "weight": [1.0]*len(symptom_ids)})

res = score_case(db, df, {}, params, 5, "auto", "")

print("COLUMNS:", list(res.columns))
print(res.head())
