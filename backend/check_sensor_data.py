import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='sensor_data'")
print(c.fetchone()[0])

conn.close()
