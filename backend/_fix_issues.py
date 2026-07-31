#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复脚本 - 修复后端数据库和代码问题
运行方式: python _fix_issues.py (在 D:\managesys\backend 目录下)
"""
import os
import sys

def fix_main_py():
    """修复 main.py 中的 Permission 导入"""
    main_path = "app/main.py"
    if not os.path.exists(main_path):
        print(f"[SKIP] {main_path} not found")
        return False
    
    with open(main_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 修复导入语句
    if 'from app.models.role import Role, Permission' in content:
        content = content.replace(
            'from app.models.role import Role, Permission',
            'from app.models import Role, Permission'
        )
        with open(main_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("[OK] Fixed Permission import in main.py")
        return True
    else:
        print("[SKIP] Permission import already fixed or different pattern")
        return False

def fix_database():
    """修复数据库 - 添加缺失的列"""
    import sqlite3
    
    db_path = "data/managesys.db"
    if not os.path.exists(db_path):
        print(f"[SKIP] Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查 data_centers 表结构
    cursor.execute("PRAGMA table_info(data_centers)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"Current data_centers columns: {columns}")
    
    missing_columns = []
    if 'contact_person' not in columns:
        missing_columns.append("ADD COLUMN contact_person VARCHAR(128)")
    if 'contact_phone' not in columns:
        missing_columns.append("ADD COLUMN contact_phone VARCHAR(32)")
    if 'contact_email' not in columns:
        missing_columns.append("ADD COLUMN contact_email VARCHAR(128)")
    
    if missing_columns:
        for col_def in missing_columns:
            try:
                sql = f"ALTER TABLE data_centers {col_def}"
                cursor.execute(sql)
                print(f"[OK] Added column: {col_def}")
            except sqlite3.OperationalError as e:
                print(f"[WARN] Column already exists: {e}")
        conn.commit()
    else:
        print("[SKIP] All columns already exist")
    
    conn.close()
    print("[OK] Database fixes applied")

if __name__ == "__main__":
    print("=" * 50)
    print("Fixing managesys backend issues...")
    print("=" * 50)
    fix_main_py()
    fix_database()
    print("=" * 50)
    print("Done! Please restart the backend server.")
    print("=" * 50)
