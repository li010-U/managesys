import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查表是否存在
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='work_order_categories'")
if not cursor.fetchone():
    # 创建工单分类表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS work_order_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(64) NOT NULL UNIQUE,
        code VARCHAR(32) NOT NULL UNIQUE,
        icon VARCHAR(32),
        sort INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 插入默认分类
    cursor.execute("INSERT INTO work_order_categories (name, code, icon, sort) VALUES ('故障报修', 'fault', 'el-icon-warning', 1)")
    cursor.execute("INSERT INTO work_order_categories (name, code, icon, sort) VALUES ('维护保养', 'maintenance', 'el-icon-s-tools', 2)")
    cursor.execute("INSERT INTO work_order_categories (name, code, icon, sort) VALUES ('变更申请', 'change', 'el-icon-edit', 3)")
    cursor.execute("INSERT INTO work_order_categories (name, code, icon, sort) VALUES ('配置调整', 'config', 'el-icon-setting', 4)")
    cursor.execute("INSERT INTO work_order_categories (name, code, icon, sort) VALUES ('其他请求', 'other', 'el-icon-question', 5)")
    
    # 创建工单表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS work_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no VARCHAR(32) NOT NULL UNIQUE,
        title VARCHAR(256) NOT NULL,
        description TEXT,
        category_id INTEGER,
        priority VARCHAR(16) DEFAULT 'normal',
        device_id INTEGER,
        facility_id INTEGER,
        status VARCHAR(16) DEFAULT 'pending',
        creator_id INTEGER NOT NULL,
        assignee_id INTEGER,
        plan_date DATE,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        estimated_hours REAL,
        actual_hours REAL,
        result TEXT,
        satisfaction INTEGER,
        feedback TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 创建工单评论表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS work_order_comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        work_order_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        comment_type VARCHAR(16) DEFAULT 'normal',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 创建工单附件表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS work_order_attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        work_order_id INTEGER NOT NULL,
        file_name VARCHAR(256) NOT NULL,
        file_path VARCHAR(512) NOT NULL,
        file_size INTEGER,
        file_type VARCHAR(64),
        uploader_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    print('WorkOrder tables created successfully')
else:
    print('WorkOrder tables already exist')

conn.commit()
conn.close()
