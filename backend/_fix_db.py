import sqlite3
import os

db_path = 'data/managesys.db'
if not os.path.exists(db_path):
    print('[SKIP] Database not found')
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check data_centers table structure
cursor.execute('PRAGMA table_info(data_centers)')
columns = [col[1] for col in cursor.fetchall()]
print('Current columns:', columns)

# Add missing columns
added = []
try:
    if 'contact_person' not in columns:
        cursor.execute('ALTER TABLE data_centers ADD COLUMN contact_person VARCHAR(128)')
        added.append('contact_person')
    if 'contact_phone' not in columns:
        cursor.execute('ALTER TABLE data_centers ADD COLUMN contact_phone VARCHAR(32)')
        added.append('contact_phone')
    if 'contact_email' not in columns:
        cursor.execute('ALTER TABLE data_centers ADD COLUMN contact_email VARCHAR(128)')
        added.append('contact_email')
    
    conn.commit()
    print('Added columns:', added)
except Exception as e:
    print('Error:', e)

conn.close()
print('Database fix done')
