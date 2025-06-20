import sqlite3

conn = sqlite3.connect('requests.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM requests")

for row in cursor.fetchall():
    print(row)

conn.close()