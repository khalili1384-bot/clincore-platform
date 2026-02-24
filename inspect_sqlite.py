import os, sqlite3
from pathlib import Path

def main():
    db_path = os.getenv("REPERTORY_DB_PATH", "src/clincore/mcare_engine/data/synthesis.db")
    p = Path(db_path)
    print("DB:", p.resolve())
    if not p.exists():
        raise SystemExit(f"DB file not found: {p}")

    con = sqlite3.connect(str(p))
    cur = con.cursor()

    print("=== TABLES ===")
    for (name,) in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"):
        print(name)

    print("\n=== COLUMNS IN symptom_remedies ===")
    try:
        for row in cur.execute("PRAGMA table_info(symptom_remedies);"):
            print(row)
    except Exception as e:
        print("ERROR:", e)

    print("\n=== COLUMNS IN syntree ===")
    try:
        for row in cur.execute("PRAGMA table_info(syntree);"):
            print(row)
    except Exception as e:
        print("ERROR:", e)

    print("\n=== FIRST 5 ROWS FROM syntree ===")
    try:
        for row in cur.execute("SELECT id, id_father, item, level, path FROM syntree LIMIT 5;"):
            print(row)
    except Exception as e:
        print("ERROR:", e)

    con.close()

if __name__ == "__main__":
    main()
