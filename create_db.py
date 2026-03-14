import sqlite3

conn = sqlite3.connect("database.db")

conn.execute("""
CREATE TABLE users(
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT,
password TEXT,
fullname TEXT,
email TEXT
)
""")

conn.commit()
conn.close()

print("Database created")