import sqlite3
from clincore.pipeline.engine_wrapper import run_engine

# 1️⃣ get real symptom_ids from DB
con = sqlite3.connect(r"src\clincore\mcare_engine\data\synthesis.135.db")
cur = con.cursor()

cur.execute("SELECT DISTINCT symptom_id FROM symptom_remedies LIMIT 5")
symptom_ids = [r[0] for r in cur.fetchall()]
con.close()

print("SYMPTOM_IDS:", symptom_ids)

# 2️⃣ run engine
result = run_engine(symptom_ids, top_n=5)

print("ENGINE_RESULT:", result)
