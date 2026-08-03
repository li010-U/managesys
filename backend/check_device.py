import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("PRAGMA table_info(devices)")
print('Devices columns:')
for col in c.fetchall():
    print(f'  {col[1]} ({col[2]})')

conn.close()
