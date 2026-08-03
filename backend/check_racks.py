import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Get first 10 racks
c.execute('SELECT id, name, code FROM racks ORDER BY id LIMIT 10')
racks = c.fetchall()
print('First 10 racks in DB:')
for r in racks:
    print('  ID:', r[0], 'Name:', r[1], 'Code:', r[2])

# Get devices for rack ID 1
c.execute('SELECT id, name FROM devices WHERE rack_id = 1')
devices = c.fetchall()
print('\\nDevices in rack 1:')
for d in devices:
    print('  ID:', d[0], 'Name:', d[1])

conn.close()
