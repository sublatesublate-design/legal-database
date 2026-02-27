# -*- coding: utf-8 -*-
"""
新增 article_cross_references 表，用于存储法条间的关联（如司法解释）。
"""

import sqlite3
from pathlib import Path

# DB is in the parent directory (project root), not in migrations/
DB_PATH = Path(__file__).parent.parent / "legal_database.db"

def create_cross_ref_table(conn, c):
    print("=== P2: 创建 article_cross_references 表 ===")
    
    # 1. Create table
    c.execute("""
        CREATE TABLE IF NOT EXISTS article_cross_references (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_law_id INTEGER NOT NULL,       -- 源法律ID (如民法典)
            source_article_int INTEGER NOT NULL,  -- 源条号 (如 538)
            target_law_id INTEGER NOT NULL,       -- 目标法律ID (如合同编解释)
            target_article_int INTEGER NOT NULL,  -- 目标条号 (如 44)
            ref_type TEXT DEFAULT 'interpretation', -- 引用类型: interpretation, conflicting, related
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_law_id, source_article_int, target_law_id, target_article_int)
        )
    """)
    
    # 2. Create indices
    c.execute("CREATE INDEX IF NOT EXISTS idx_cross_ref_source ON article_cross_references(source_law_id, source_article_int)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_cross_ref_target ON article_cross_references(target_law_id, target_article_int)")
    
    print("  ✅ 表结构已创建/确认")

def populate_initial_data(conn, c):
    """
    填充初始数据:
    民法典 第538条 -> 合同编通则解释 第44条 (撤销权诉讼标的)
    民法典 第538条 -> 合同编通则解释 第45条 (撤销权诉讼当事人)
    民法典 第539条 -> 合同编通则解释 第44条
    民法典 第539条 -> 合同编通则解释 第45条 
    """
    print("=== P2: 填充初始关联数据 ===")
    
    # Helper to find law ID
    def get_law_id(title_part):
        # 优先全称匹配
        c.execute("SELECT id FROM laws WHERE title = ? AND status='有效' LIMIT 1", (title_part,))
        res = c.fetchone()
        if res: return res[0]
        # 模糊匹配
        c.execute("SELECT id FROM laws WHERE title LIKE ? AND status='有效' ORDER BY (title = ?) DESC LIMIT 1", (f"%{title_part}%", title_part))
        res = c.fetchone()
        return res[0] if res else None

    civ_code_id = get_law_id("中华人民共和国民法典")
    contract_interp_id = get_law_id("最高人民法院关于适用《中华人民共和国民法典》合同编通则若干问题的解释")

    if not civ_code_id or not contract_interp_id:
        print(f"  ⚠️ 未找到相关法律ID (民法典={civ_code_id}, 合同编解释={contract_interp_id})，跳过数据填充")
        return

    # Data: (source_art, target_art)
    relations = [
        (538, 44), (538, 45), (538, 46),
        (539, 44), (539, 45), (539, 46),
        (540, 45), (541, 45)
    ]

    count = 0
    for s_art, t_art in relations:
        try:
            c.execute("""
                INSERT OR IGNORE INTO article_cross_references 
                (source_law_id, source_article_int, target_law_id, target_article_int, ref_type)
                VALUES (?, ?, ?, ?, 'interpretation')
            """, (civ_code_id, s_art, contract_interp_id, t_art))
            if c.rowcount > 0: count += 1
        except Exception as e:
            print(f"  ❌ 插入失败 {s_art}->{t_art}: {e}")

    conn.commit()
    print(f"  ✅ 插入了 {count} 条手动关联数据")

def main():
    print(f"数据库: {DB_PATH}")
    if not DB_PATH.exists():
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        create_cross_ref_table(conn, c)
        populate_initial_data(conn, c)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        conn.rollback()
    finally:
        conn.close()
    
    print("\n🎉 迁移完成！")

if __name__ == "__main__":
    main()
