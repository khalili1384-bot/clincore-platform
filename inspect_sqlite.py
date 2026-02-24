import sqlite3

DB_PATH = "src/clincore/mcare_engine/data/synthesis.135.db"

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

print("=== TABLES ===")
for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table';"):
    print(row[0])

print("\n=== COLUMNS IN syntree ===")
for row in cur.execute("PRAGMA table_info(syntree);"):
    print(row)

print("\n=== FIRST 5 ROWS FROM syntree ===")
for row in cur.execute("SELECT * FROM syntree LIMIT 5;"):
    print(row)

con.close()