import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Check if id is autoincrement
c.execute("SELECT COUNT(*) FROM alerts")
print(f'Current alerts: {c.fetchone()[0]}')

# Try to manually set id
try:
    c.execute('INSERT INTO alerts (id, target_type, target_id, title, level, status, source) VALUES (1, ?, ?, ?, ?, ?, ?)',
        ('device', 'test', 'Test Alert', 'general', 'new', 'monitor'))
    conn.commit()
    print('Manual insert worked')
except Exception as e:
    print(f'Error: {e}')

conn.close()
