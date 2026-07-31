import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查表是否存在
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inspection_templates'")
if not cursor.fetchone():
    # 创建巡检模板表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS inspection_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(128) NOT NULL,
        description TEXT,
        device_type_id INTEGER,
        items TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 插入默认模板
    cursor.execute("""INSERT INTO inspection_templates (name, description, items) VALUES (
        '服务器标准巡检', 
        '服务器日常巡检项目',
        '[{"key": "power", "name": "电源状态", "content": "检查电源指示灯是否正常"}, {"key": "network", "name": "网络连接", "content": "检查网口状态灯和网络连通性"}, {"key": "disk", "name": "磁盘状态", "content": "检查硬盘指示灯和RAID状态"}, {"key": "temp", "name": "温度检查", "content": "检查服务器温度是否正常"}, {"key": "console", "name": "控制台", "content": "检查KVM切换器和显示器"}]'
    )""")
    cursor.execute("""INSERT INTO inspection_templates (name, description, items) VALUES (
        '网络设备巡检',
        '交换机、路由器巡检项目',
        '[{"key": "port", "name": "端口状态", "content": "检查所有端口Link灯"}, {"key": "traffic", "name": "流量检查", "content": "检查端口流量是否正常"}, {"key": "power", "name": "电源状态", "content": "检查双电源供电状态"}]'
    )""")
    
    # 创建巡检计划表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS inspection_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(128) NOT NULL,
        description TEXT,
        plan_type VARCHAR(16) DEFAULT 'periodic',
        frequency VARCHAR(16) DEFAULT 'daily',
        weekdays VARCHAR(32),
        day_of_month INTEGER,
        execute_time VARCHAR(8) DEFAULT '09:00',
        facility_id INTEGER,
        template_id INTEGER,
        assignee_id INTEGER,
        status VARCHAR(16) DEFAULT 'active',
        next_execute_date DATE,
        last_execute_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 创建巡检任务表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS inspection_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER NOT NULL,
        plan_name VARCHAR(128) NOT NULL,
        facility_id INTEGER,
        status VARCHAR(16) DEFAULT 'pending',
        priority VARCHAR(16) DEFAULT 'normal',
        assignee_id INTEGER,
        scheduled_date DATE NOT NULL,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        total_items INTEGER DEFAULT 0,
        completed_items INTEGER DEFAULT 0,
        abnormal_items INTEGER DEFAULT 0,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 创建巡检记录表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS inspection_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        device_id INTEGER,
        item_name VARCHAR(128) NOT NULL,
        item_key VARCHAR(64) NOT NULL,
        check_content VARCHAR(512) NOT NULL,
        check_result VARCHAR(32),
        check_value VARCHAR(256),
        check_remark TEXT,
        inspector_id INTEGER NOT NULL,
        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 创建巡检问题表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS inspection_issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        record_id INTEGER,
        device_id INTEGER,
        issue_title VARCHAR(256) NOT NULL,
        issue_description TEXT,
        severity VARCHAR(16) DEFAULT 'normal',
        status VARCHAR(16) DEFAULT 'open',
        reporter_id INTEGER NOT NULL,
        handler_id INTEGER,
        resolve_content TEXT,
        resolve_time TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    print('Inspection tables created successfully')
else:
    print('Inspection tables already exist')

conn.commit()
conn.close()
