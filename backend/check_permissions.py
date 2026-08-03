import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Check user and roles
print('=== User & Roles ===')
c.execute('''
    SELECT u.username, u.is_super_admin, GROUP_CONCAT(r.name) 
    FROM users u 
    LEFT JOIN user_roles ur ON u.id = ur.user_id 
    LEFT JOIN roles r ON ur.role_id = r.id 
    GROUP BY u.id
''')
for row in c.fetchall():
    print(f'User: {row[0]}, SuperAdmin: {row[1]}, Roles: {row[2]}')

# Check all roles
print('\\n=== All Roles ===')
c.execute('SELECT id, name, code, is_builtin FROM roles')
for row in c.fetchall():
    print(f'Role {row[0]}: {row[1]} ({row[2]}), Built-in: {row[3]}')

# Check permissions
print('\\n=== All Permissions ===')
c.execute('SELECT id, code, name, module FROM permissions ORDER BY module')
for row in c.fetchall():
    print(f'  {row[3]}: {row[2]} ({row[1]})')

# Check super_admin role permissions
print('\\n=== Super Admin Permissions ===')
c.execute('''
    SELECT p.code FROM permissions p
    JOIN role_permissions rp ON p.id = rp.permission_id
    JOIN roles r ON rp.role_id = r.id
    WHERE r.code = 'super_admin'
''')
perms = [row[0] for row in c.fetchall()]
print(f'Super admin has {len(perms)} permissions')
print('Sample:', perms[:10])

# Check for monitor/alert permissions
print('\\n=== Monitor/Alert Permissions ===')
c.execute("SELECT code, name FROM permissions WHERE code LIKE '%monitor%' OR code LIKE '%alert%'")
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]}')

conn.close()
