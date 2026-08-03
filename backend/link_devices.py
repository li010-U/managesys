import sqlite3
import os
import random

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Get new racks (ID > 20)
c.execute('SELECT id, code FROM racks WHERE id > 20 ORDER BY id')
new_racks = c.fetchall()
print('New racks:', len(new_racks))

# Get devices currently on old racks (ID 1-10)
c.execute('SELECT id FROM devices WHERE rack_id BETWEEN 1 AND 10')
old_devices = [d[0] for d in c.fetchall()]
print('Devices on old racks:', len(old_devices))

# Update devices to use new racks
updated = 0
for device_id in old_devices:
    # Assign to a random new rack
    new_rack = random.choice(new_racks)
    c.execute('UPDATE devices SET rack_id = ? WHERE id = ?', (new_rack[0], device_id))
    updated += 1

conn.commit()
print('Updated devices:', updated)

# Verify
c.execute('SELECT COUNT(*) FROM devices WHERE rack_id > 20')
print('Devices on new racks:', c.fetchone()[0])

conn.close()
print('Done!')
