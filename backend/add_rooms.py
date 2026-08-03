import sqlite3
import os
import random

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute('SELECT id, name, code FROM data_centers')
dcs = c.fetchall()
print(f'Data Centers: {len(dcs)}')

c.execute('SELECT id, data_center_id, name, code FROM rooms')
current_rooms = c.fetchall()
print(f'Current rooms: {len(current_rooms)}')

tier_levels = ['Tier I', 'Tier II', 'Tier III', 'Tier IV']
rooms_created = 0

for dc in dcs:
    dc_id, dc_name, dc_code = dc
    existing = [r for r in current_rooms if r[1] == dc_id]
    existing_count = len(existing)
    target = random.randint(3, 5)
    
    for i in range(existing_count, target):
        if '北京' in dc_name:
            prefix = '京'
        elif '上海' in dc_name:
            prefix = '沪'
        elif '深圳' in dc_name:
            prefix = '深'
        else:
            prefix = '主'
        
        room_name = prefix + chr(65+i) + '区'
        parts = dc_code.split('-')
        room_code = 'RM-' + parts[-1] + '-' + str(i+1).zfill(2)
        
        # Check if code exists
        c.execute('SELECT COUNT(*) FROM rooms WHERE code=?', (room_code,))
        if c.fetchone()[0] > 0:
            room_code = room_code + '-' + str(random.randint(1,99))
        
        c.execute('''
            INSERT INTO rooms (data_center_id, name, code, floor, area, load_rating, tier_level, description, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (dc_id, room_name, room_code, str(random.randint(1,6))+'楼', 
              random.randint(200, 600), random.randint(8, 25)*1000,
              random.choice(tier_levels), '高性能计算机房', 'active'))
        rooms_created += 1
        print(f'Created: {room_name} for {dc_name}')

conn.commit()

print(f'\\nTotal rooms created: {rooms_created}')
c.execute('SELECT COUNT(*) FROM rooms')
print(f'Total rooms now: {c.fetchone()[0]}')

print('\\nRooms per DC:')
c.execute('''SELECT dc.name, COUNT(r.id) FROM data_centers dc LEFT JOIN rooms r ON dc.id=r.data_center_id GROUP BY dc.id''')
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]} rooms')

conn.close()
print('\\nDone! Refresh frontend.')
