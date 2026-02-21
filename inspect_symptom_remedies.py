import sqlite3

con = sqlite3.connect(r"src\clincore\mcare_engine\data\synthesis.135.db")
cur = con.cursor()

cur.execute("PRAGMA table_info(symptom_remedies)")
print("COLUMNS:", cur.fetchall())

con.close()
