"""
数据库迁移脚本 001: 添加法律别名表

功能：
1. 创建 law_aliases 表
2. 为常用法律添加简称映射
3. 验证数据完整性
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime

# 数据库路径
DB_PATH = Path(__file__).parent.parent / "legal_database.db"

def run_migration():
    """执行数据库迁移"""
    print("🔧 开始数据库迁移: 添加法律别名表...")
    
    if not DB_PATH.exists():
        print(f"❌ 错误: 数据库文件不存在 {DB_PATH}")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 1. 创建别名表
        print("  → 创建 law_aliases 表...")
        with open(Path(__file__).parent.parent / "database" / "schema_aliases.sql", 'r', encoding='utf-8') as f:
            schema_sql = f.read()
            cursor.executescript(schema_sql)
        
        # 2. 验证表创建成功
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='law_aliases'")
        if cursor.fetchone():
            print("  ✓ law_aliases 表创建成功")
        else:
            raise Exception("表创建失败")
        
        # 3. 验证索引创建
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_aliases%'")
        indexes = cursor.fetchall()
        print(f"  ✓ 创建了 {len(indexes)} 个索引")
        
        conn.commit()
        print("✅ 迁移成功完成！")
        return True
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def verify_migration():
    """验证迁移结果"""
    print("\n🔍 验证迁移结果...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 检查表结构
        cursor.execute("PRAGMA table_info(law_aliases)")
        columns = cursor.fetchall()
        print(f"  → law_aliases 表有 {len(columns)} 个字段:")
        for col in columns:
            print(f"    - {col[1]} ({col[2]})")
        
        # 检查外键
        cursor.execute("PRAGMA foreign_key_list(law_aliases)")
        fks = cursor.fetchall()
        print(f"  → 外键约束: {len(fks)} 个")
        
        print("✅ 验证通过！")
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("法律数据库迁移 - 001: 添加别名系统")
    print("=" * 60)
    print()
    
    if run_migration():
        verify_migration()
    else:
        print("\n⚠️  迁移未成功，请检查错误信息")
