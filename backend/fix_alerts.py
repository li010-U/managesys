import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Check sqlite_sequence
c.execute('SELECT * FROM sqlite_sequence WHERE name="alerts"')
print('Sequence for alerts:', c.fetchone())

# Delete test record
c.execute('DELETE FROM alerts WHERE target_id=?', ('test',))
conn.commit()

# Check current max id
c.execute('SELECT MAX(id) FROM alerts')
print('Max id:', c.fetchone()[0])

conn.close()
