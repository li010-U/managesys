import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Get devices with rack_id
c.execute('SELECT id, name, rack_id FROM devices WHERE rack_id IS NOT NULL LIMIT 10')
devices = c.fetchall()
print('Devices with rack_id:')
for d in devices:
    print('  ID:', d[0], 'Name:', d[1], 'rack_id:', d[2])

# Get rack 34 details
c.execute('SELECT id, name, code FROM racks WHERE id = 34')
rack = c.fetchone()
print('\\nRack 34:', rack)

# Count devices by rack_id
c.execute('SELECT rack_id, COUNT(*) FROM devices WHERE rack_id IS NOT NULL GROUP BY rack_id')
by_rack = c.fetchall()
print('\\nDevices by rack_id:')
for r in by_rack[:10]:
    print('  rack_id:', r[0], 'count:', r[1])

conn.close()
