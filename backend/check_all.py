import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Check total racks
c.execute('SELECT COUNT(*) FROM racks')
print('Total racks:', c.fetchone()[0])

# Check rack IDs range
c.execute('SELECT MIN(id), MAX(id) FROM racks')
min_max = c.fetchone()
print('Rack ID range:', min_max[0], '-', min_max[1])

# Check devices with rack_id
c.execute('SELECT MIN(rack_id), MAX(rack_id) FROM devices WHERE rack_id IS NOT NULL')
min_max = c.fetchone()
print('Device rack_id range:', min_max[0], '-', min_max[1])

# Get some devices with their rack
c.execute('''
    SELECT d.id, d.name, d.rack_id, r.code 
    FROM devices d 
    LEFT JOIN racks r ON d.rack_id = r.id 
    WHERE d.rack_id IS NOT NULL 
    LIMIT 5
''')
devices = c.fetchall()
print('\\nDevices with rack:')
for d in devices:
    print('  Device:', d[0], d[1], '-> Rack ID:', d[2], d[3])

conn.close()
