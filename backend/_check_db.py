import sqlite3
conn = sqlite3.connect('data/managesys.db')
cursor = conn.cursor()

# 列出所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
print("Tables:")
for row in cursor.fetchall():
    print(f"  - {row[0]}")

# 检查 work_order_categories 是否有数据
cursor.execute("SELECT * FROM work_order_categories")
rows = cursor.fetchall()
print(f"\nwork_order_categories: {len(rows)} rows")
for r in rows:
    print(f"  {r}")

# 检查 inspection_templates 是否有数据
cursor.execute("SELECT * FROM inspection_templates")
rows = cursor.fetchall()
print(f"\ninspection_templates: {len(rows)} rows")
for r in rows:
    print(f"  {r}")

conn.close()
