import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Test the exact query that should work
c.execute('''
    SELECT d.id, d.name, d.rack_id, r.code 
    FROM devices d 
    LEFT JOIN racks r ON d.rack_id = r.id 
    WHERE d.rack_id = 40
''')
devices = c.fetchall()
print('Devices with rack_id = 40:')
for d in devices:
    print('  ID:', d[0], 'Name:', d[1], 'Rack:', d[3])

# Check rack 40 exists
c.execute('SELECT id, code, row_pos, col_pos FROM racks WHERE id = 40')
rack = c.fetchone()
print('\\nRack 40:', rack)

# Count all devices
c.execute('SELECT COUNT(*) FROM devices WHERE rack_id IS NOT NULL')
print('Total devices with rack:', c.fetchone()[0])

conn.close()
