# -*- coding: utf-8 -*-
"""
数据库迁移脚本 003: 创建颗粒化法条表 (V2)

功能：
1. 创建 law_articles 表 (含 article_number_int, article_number_str, chapter_path)
2. 创建 law_articles_fts 全文索引表 (FTS5)
3. 遍历 laws 表，使用 ArticleSplitter 拆分法条并回填
4. 创建触发器保持 FTS 同步
5. 创建索引加速查询

设计：
- 幂等：DROP + CREATE，可反复运行
- 回填所有 status='有效' 的法律
- 错误容忍：单条解析失败不影响整体
"""

import sqlite3
import sys
import time
import logging
from pathlib import Path

# 项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from article_splitter import ArticleSplitter

DB_PATH = project_root / "legal_database.db"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("migration-003")


def run_migration():
    """执行数据库迁移"""
    print("=" * 60)
    print("法律数据库迁移 003: 颗粒化法条系统 (V2)")
    print("=" * 60)

    if not DB_PATH.exists():
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    cursor = conn.cursor()
    splitter = ArticleSplitter()

    try:
        # ========== Step 1: Schema ==========
        print("\n[1/5] 创建 law_articles 表...")

        # 先清理旧表和触发器 (幂等)
        cursor.execute("DROP TRIGGER IF EXISTS law_articles_ai")
        cursor.execute("DROP TRIGGER IF EXISTS law_articles_ad")
        cursor.execute("DROP TRIGGER IF EXISTS law_articles_au")
        cursor.execute("DROP TABLE IF EXISTS law_articles_fts")
        cursor.execute("DROP TABLE IF EXISTS law_articles")

        cursor.execute("""
            CREATE TABLE law_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                law_id INTEGER NOT NULL,
                article_number_int INTEGER,   -- 整数序号: 1023 (排序/过滤)
                article_number_str TEXT,       -- 字符串序号: "120之一" (展示/特殊编号)
                content TEXT,                  -- 完整条文内容
                chapter_path TEXT,             -- 层级路径: "第四编 人格权 / 第四章 肖像权"
                FOREIGN KEY(law_id) REFERENCES laws(id)
            )
        """)
        print("   ✅ law_articles 表已创建")

        # ========== Step 2: FTS5 ==========
        print("\n[2/5] 创建 law_articles_fts 表...")
        cursor.execute("""
            CREATE VIRTUAL TABLE law_articles_fts USING fts5(
                content,
                article_number_str,
                chapter_path,
                tokenize='trigram'
            )
        """)
        print("   ✅ law_articles_fts 表已创建")

        # ========== Step 3: Backfill ==========
        print("\n[3/5] 回填数据 (从 laws 表拆分)...")
        cursor.execute("SELECT id, title, content FROM laws WHERE status = '有效'")
        laws = cursor.fetchall()
        total_laws = len(laws)
        total_articles = 0
        error_count = 0
        t0 = time.time()

        for i, (law_id, law_title, law_content) in enumerate(laws):
            if not law_content:
                continue

            try:
                articles = splitter.split_law(law_content)
                if not articles:
                    continue

                batch = []
                for art in articles:
                    batch.append((
                        law_id,
                        art['article_number_int'],
                        art['article_number_str'],
                        art['content'],
                        art['chapter_path'],
                    ))

                if batch:
                    cursor.executemany(
                        "INSERT INTO law_articles "
                        "(law_id, article_number_int, article_number_str, content, chapter_path) "
                        "VALUES (?, ?, ?, ?, ?)",
                        batch
                    )
                    total_articles += len(batch)

                # 定期提交 + 进度报告
                if (i + 1) % 50 == 0:
                    conn.commit()
                    elapsed = time.time() - t0
                    print(f"   进度: {i+1}/{total_laws} ({total_articles} 条, "
                          f"{elapsed:.1f}s, {error_count} 错误)")

            except Exception as e:
                error_count += 1
                if error_count <= 5:
                    logger.warning(f"处理 [{law_title[:20]}] 出错: {e}")

        conn.commit()
        elapsed = time.time() - t0
        print(f"   ✅ 回填完成: {total_laws} 部法律 → {total_articles} 条 "
              f"({elapsed:.1f}s, {error_count} 错误)")

        # ========== Step 4: Rebuild FTS ==========
        print("\n[4/5] 重建 FTS 索引...")
        cursor.execute("INSERT INTO law_articles_fts(law_articles_fts) VALUES('rebuild')")
        conn.commit()
        print("   ✅ FTS 索引已重建")

        # ========== Step 5: Triggers + Indexes ==========
        print("\n[5/5] 创建触发器和索引...")

        # Insert trigger
        cursor.execute("""
            CREATE TRIGGER law_articles_ai AFTER INSERT ON law_articles BEGIN
                INSERT INTO law_articles_fts(rowid, content, article_number_str, chapter_path)
                VALUES (new.id, new.content, new.article_number_str, new.chapter_path);
            END
        """)

        # Delete trigger
        cursor.execute("""
            CREATE TRIGGER law_articles_ad AFTER DELETE ON law_articles BEGIN
                INSERT INTO law_articles_fts(law_articles_fts, rowid, content, article_number_str, chapter_path)
                VALUES('delete', old.id, old.content, old.article_number_str, old.chapter_path);
            END
        """)

        # Update trigger
        cursor.execute("""
            CREATE TRIGGER law_articles_au AFTER UPDATE ON law_articles BEGIN
                INSERT INTO law_articles_fts(law_articles_fts, rowid, content, article_number_str, chapter_path)
                VALUES('delete', old.id, old.content, old.article_number_str, old.chapter_path);
                INSERT INTO law_articles_fts(rowid, content, article_number_str, chapter_path)
                VALUES (new.id, new.content, new.article_number_str, new.chapter_path);
            END
        """)

        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_la_law_id ON law_articles(law_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_la_number_int ON law_articles(article_number_int)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_la_law_num ON law_articles(law_id, article_number_int)")

        conn.commit()
        print("   ✅ 触发器和索引已创建")

        print(f"\n{'='*60}")
        print(f"✅ 迁移成功！共 {total_articles} 条法条数据。")
        print(f"{'='*60}")
        return True

    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False

    finally:
        conn.close()


def verify_migration():
    """验证迁移结果"""
    print("\n🔍 验证迁移结果...\n")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    all_pass = True

    try:
        # 1. 表结构
        cursor.execute("PRAGMA table_info(law_articles)")
        cols = [r[1] for r in cursor.fetchall()]
        expected = {'id', 'law_id', 'article_number_int', 'article_number_str', 'content', 'chapter_path'}
        if set(cols) == expected:
            print(f"  ✅ 表结构正确: {cols}")
        else:
            print(f"  ❌ 表结构不匹配: 期望 {expected}, 实际 {set(cols)}")
            all_pass = False

        # 2. 总数
        cursor.execute("SELECT count(*) FROM law_articles")
        count = cursor.fetchone()[0]
        print(f"  ✅ 总法条数: {count}")

        # 3. 民法典第1023条 (声音保护)
        cursor.execute("""
            SELECT la.article_number_int, la.article_number_str, substr(la.content, 1, 60)
            FROM law_articles la
            JOIN laws l ON la.law_id = l.id
            WHERE l.title LIKE '%民法典%' AND l.status = '有效'
              AND la.article_number_int = 1023
        """)
        r = cursor.fetchone()
        if r:
            print(f"  ✅ 民法典第1023条: int={r[0]}, str={r[1]}")
            print(f"     内容: {r[2]}...")
        else:
            print("  ❌ 未找到民法典第1023条！")
            all_pass = False

        # 4. FTS 搜索测试
        cursor.execute("""
            SELECT la.article_number_str, substr(la.content, 1, 40)
            FROM law_articles_fts fts
            JOIN law_articles la ON fts.rowid = la.id
            WHERE law_articles_fts MATCH '"声音"'
            LIMIT 3
        """)
        fts_results = cursor.fetchall()
        if fts_results:
            print(f"  ✅ FTS搜索'声音': 找到 {len(fts_results)} 条")
            for r in fts_results:
                print(f"     第{r[0]}条: {r[1]}...")
        else:
            print("  ⚠️ FTS搜索'声音'无结果")

        # 5. chapter_path 检查
        cursor.execute("""
            SELECT la.chapter_path, la.article_number_str
            FROM law_articles la
            JOIN laws l ON la.law_id = l.id
            WHERE l.title LIKE '%民法典%' AND l.status = '有效'
              AND la.chapter_path != '' AND la.chapter_path IS NOT NULL
            LIMIT 3
        """)
        paths = cursor.fetchall()
        if paths:
            print(f"  ✅ chapter_path 示例:")
            for p in paths:
                print(f"     第{p[1]}条 → {p[0]}")
        else:
            print("  ⚠️ 未找到 chapter_path 数据")

    finally:
        conn.close()

    return all_pass


if __name__ == "__main__":
    if run_migration():
        verify_migration()
    else:
        print("\n⚠️ 迁移未成功，请检查错误信息")
