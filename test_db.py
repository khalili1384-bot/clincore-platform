import sqlite3

con = sqlite3.connect(r"src\clincore\mcare_engine\data\synthesis.135.db")
cur = con.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("TABLES:", cur.fetchall())

con.close()
