import sqlite3
import os
import random

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Get all rooms
c.execute('SELECT id, code FROM rooms')
rooms = c.fetchall()

# Count current racks
c.execute('SELECT COUNT(*) FROM racks')
current_racks = c.fetchone()[0]
print(f'Current racks: {current_racks}')

# Create racks for each room
racks_created = 0
for room_id, room_code in rooms:
    # Count existing racks for this room
    c.execute('SELECT COUNT(*) FROM racks WHERE room_id=?', (room_id,))
    existing = c.fetchone()[0]
    
    # Add 5-15 racks per room
    target = random.randint(5, 15)
    
    for i in range(existing, target):
        rack_name = chr(65 + (i % 26)) + '-' + str((i // 26) + 1).zfill(2)
        rack_code = 'RK-' + room_code + '-' + str(i+1).zfill(2)
        
        # Check if code exists
        c.execute('SELECT COUNT(*) FROM racks WHERE code=?', (rack_code,))
        if c.fetchone()[0] > 0:
            rack_code = rack_code + '-' + str(random.randint(1,9))
        
        c.execute('''
            INSERT INTO racks (room_id, name, code, row_pos, col_pos, total_units, available_units, rated_power, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (room_id, rack_name, rack_code, i//5+1, i%5+1, 42, random.randint(10,30), 
              random.choice([10, 15, 20]), '标准42U机柜'))
        racks_created += 1

conn.commit()

print(f'Racks created: {racks_created}')
c.execute('SELECT COUNT(*) FROM racks')
print(f'Total racks now: {c.fetchone()[0]}')

conn.close()
print('Done!')
