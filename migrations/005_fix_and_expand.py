# -*- coding: utf-8 -*-
"""
修复 FTS 触发器 + 清理遗留表 + 扩充别名系统

Phase 1: F1 - 修复触发器（当前触发器引用 3 列但 FTS 只有 1 列）
Phase 3: A1 - 清理遗留 test_fts / test_fts_trigram 表
Phase 2: E1 - 扩充 law_aliases 别名系统
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "legal_database.db"

def fix_triggers(conn, c):
    """修复 FTS 触发器，使其与当前 law_articles_fts 只有 content 列的 schema 一致"""
    print("=== F1: 修复 FTS 触发器 ===")
    
    # 删除旧触发器（引用了不存在的列 article_number_str, chapter_path）
    c.execute("DROP TRIGGER IF EXISTS law_articles_ai")
    c.execute("DROP TRIGGER IF EXISTS law_articles_ad")
    c.execute("DROP TRIGGER IF EXISTS law_articles_au")
    
    # 重建触发器，只同步 content 列
    # 注意：当前 FTS 使用 unicode61 tokenizer（jieba 分词后的内容），
    # 但触发器直接插入原始 content，不经过 jieba 分词。
    # 这是一个已知限制 — 新增的法条不会被 jieba 分词。
    # 后续可考虑统一为 trigram 分词器来避免此问题。
    c.execute("""
        CREATE TRIGGER law_articles_ai AFTER INSERT ON law_articles BEGIN
            INSERT INTO law_articles_fts(rowid, content)
            VALUES (new.id, new.content);
        END
    """)
    c.execute("""
        CREATE TRIGGER law_articles_ad AFTER DELETE ON law_articles BEGIN
            INSERT INTO law_articles_fts(law_articles_fts, rowid, content)
            VALUES('delete', old.id, old.content);
        END
    """)
    c.execute("""
        CREATE TRIGGER law_articles_au AFTER UPDATE ON law_articles BEGIN
            INSERT INTO law_articles_fts(law_articles_fts, rowid, content)
            VALUES('delete', old.id, old.content);
            INSERT INTO law_articles_fts(rowid, content)
            VALUES (new.id, new.content);
        END
    """)
    conn.commit()
    print("  ✅ 触发器已修复（仅同步 content 列）")


def cleanup_test_tables(conn, c):
    """清理遗留的测试 FTS 表"""
    print("\n=== A1: 清理遗留测试表 ===")
    test_tables = [
        "test_fts", "test_fts_config", "test_fts_data", 
        "test_fts_docsize", "test_fts_idx",
        "test_fts_trigram", "test_fts_trigram_config", "test_fts_trigram_data",
        "test_fts_trigram_docsize", "test_fts_trigram_idx"
    ]
    for t in test_tables:
        try:
            c.execute(f"DROP TABLE IF EXISTS [{t}]")
        except Exception as e:
            print(f"  ⚠️ 无法删除 {t}: {e}")
    conn.commit()
    print(f"  ✅ 已清理 {len(test_tables)} 个测试表")


def expand_aliases(conn, c):
    """扩充法律别名系统"""
    print("\n=== E1: 扩充 law_aliases ===")
    
    # 查询所有有效法律
    c.execute("SELECT id, title FROM laws WHERE status = '有效'")
    laws = c.fetchall()
    
    new_aliases = []

    for law_id, title in laws:
        # 1. 去掉 "中华人民共和国" 前缀
        PREFIX = "中华人民共和国"
        if title.startswith(PREFIX):
            short = title[len(PREFIX):]
            new_aliases.append((short, law_id, "short_name", 0.95))
        
        # 2. 常见简称规则
        ABBREV_MAP = {
            "民法典": ["民法典"],
            "刑法": ["刑法"],
            "公司法": ["公司法"],
            "劳动法": ["劳动法"],
            "劳动合同法": ["劳动合同法", "劳合法"],
            "民事诉讼法": ["民事诉讼法", "民诉法"],
            "刑事诉讼法": ["刑事诉讼法", "刑诉法"],
            "行政诉讼法": ["行政诉讼法", "行诉法"],
            "行政处罚法": ["行政处罚法"],
            "行政许可法": ["行政许可法"],
            "行政强制法": ["行政强制法"],
            "行政复议法": ["行政复议法"],
            "治安管理处罚法": ["治安管理处罚法", "治安处罚法"],
            "个人所得税法": ["个人所得税法", "个税法"],
            "企业所得税法": ["企业所得税法", "企税法"],
            "增值税法": ["增值税法"],
            "消费者权益保护法": ["消费者权益保护法", "消保法", "消费者保护法"],
            "反不正当竞争法": ["反不正当竞争法", "反不正当竞争"],
            "反垄断法": ["反垄断法"],
            "合伙企业法": ["合伙企业法"],
            "个人独资企业法": ["个人独资企业法"],
            "证券法": ["证券法"],
            "保险法": ["保险法"],
            "银行业监督管理法": ["银行业监管法"],
            "商业银行法": ["商业银行法"],
            "票据法": ["票据法"],
            "担保法": ["担保法"],  # 已废止但用户会搜
            "合同法": ["合同法"],  # 已并入民法典
            "物权法": ["物权法"],  # 已并入民法典
            "婚姻法": ["婚姻法"],  # 已并入民法典
            "继承法": ["继承法"],  # 已并入民法典
            "侵权责任法": ["侵权责任法"],  # 已并入民法典
            "著作权法": ["著作权法"],
            "专利法": ["专利法"],
            "商标法": ["商标法"],
            "环境保护法": ["环境保护法", "环保法"],
            "土地管理法": ["土地管理法"],
            "城乡规划法": ["城乡规划法"],
            "建筑法": ["建筑法"],
            "道路交通安全法": ["道路交通安全法", "交通安全法", "道交法"],
            "食品安全法": ["食品安全法"],
            "药品管理法": ["药品管理法"],
            "安全生产法": ["安全生产法"],
            "网络安全法": ["网络安全法"],
            "数据安全法": ["数据安全法"],
            "个人信息保护法": ["个人信息保护法", "个保法"],
            "电子商务法": ["电子商务法", "电商法"],
            "招标投标法": ["招标投标法", "招投标法"],
            "政府采购法": ["政府采购法"],
            "仲裁法": ["仲裁法"],
            "人民调解法": ["人民调解法"],
            "国家赔偿法": ["国家赔偿法"],
            "监察法": ["监察法"],
            "法官法": ["法官法"],
            "检察官法": ["检察官法"],
            "律师法": ["律师法"],
            "公证法": ["公证法"],
            "传染病防治法": ["传染病防治法"],
            "民族区域自治法": ["民族区域自治法"],
            "选举法": ["选举法"],
            "突发事件应对法": ["突发事件应对法"],
            "未成年人保护法": ["未成年人保护法", "未保法"],
            "妇女权益保障法": ["妇女权益保障法"],
            "老年人权益保障法": ["老年人权益保障法"],
            "残疾人保障法": ["残疾人保障法"],
            "慈善法": ["慈善法"],
            "社会保险法": ["社会保险法", "社保法"],
            "工会法": ["工会法"],
        }
        
        for key, aliases in ABBREV_MAP.items():
            if key in title:
                for alias in aliases:
                    if alias != title:  # 不重复完整标题
                        new_aliases.append((alias, law_id, "abbreviation", 0.9))

    # 去重并插入
    existing = set()
    c.execute("SELECT alias, law_id FROM law_aliases")
    for alias, lid in c.fetchall():
        existing.add((alias, lid))
    
    inserted = 0
    for alias, law_id, alias_type, confidence in new_aliases:
        if (alias, law_id) not in existing:
            try:
                c.execute("""
                    INSERT INTO law_aliases (alias, law_id, alias_type, confidence)
                    VALUES (?, ?, ?, ?)
                """, (alias, law_id, alias_type, confidence))
                existing.add((alias, law_id))
                inserted += 1
            except sqlite3.IntegrityError:
                pass

    conn.commit()
    
    c.execute("SELECT COUNT(*) FROM law_aliases")
    total = c.fetchone()[0]
    print(f"  ✅ 新增 {inserted} 条别名，总计 {total} 条")


def main():
    print(f"数据库: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        fix_triggers(conn, c)
        cleanup_test_tables(conn, c)
        expand_aliases(conn, c)
        
        # VACUUM 压缩
        print("\n=== 压缩数据库 ===")
        print("  ⏳ 执行 VACUUM（可能需要 30-60 秒）...")
        conn.execute("VACUUM")
        print("  ✅ VACUUM 完成")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        conn.rollback()
    finally:
        conn.close()
    
    print("\n🎉 全部修复完成！")


if __name__ == "__main__":
    main()
