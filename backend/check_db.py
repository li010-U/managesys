import sqlite3
import os
db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
print('DB path:', db_path)
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('Tables:', [t[0] for t in c.fetchall()])
for t in ['data_centers', 'rooms', 'racks', 'device_types', 'devices']:
    try:
        c.execute(f'SELECT COUNT(*) FROM {t}')
        print(f'{t}: {c.fetchone()[0]}')
    except:
        print(f'{t}: error')
conn.close()
