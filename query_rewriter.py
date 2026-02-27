# -*- coding: utf-8 -*-
"""
Query Rewriter - 查询重写/扩展模块 (E2)

功能：
1. 别名扩展: "民法典" -> "民法典 OR 中华人民共和国民法典"
2. 概念同义词扩展: "撤销权" -> "撤销权 OR 债权人撤销权"
3. 错别字/口语修正 (未来可接 LLM)
"""

import sqlite3
import logging
from pathlib import Path
from functools import lru_cache

logger = logging.getLogger(__name__)
DB_PATH = Path(__file__).parent / "legal_database.db"

@lru_cache(maxsize=1024)
def expand_query(query: str) -> str:
    """
    对查询词进行扩展。
    返回扩展后的查询字符串（例如 "A OR B"）。
    """
    if not query:
        return ""
    
    # 1. 基础清理
    query = query.strip()
    expanded_terms = {query}
    
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            
            # 2. 别名扩展 (Law Aliases)
            # 查 alias -> law_id -> title
            # 场景: 用户搜 "民法典", 扩展为 "中华人民共和国民法典"
            cursor.execute("""
                SELECT l.title 
                FROM law_aliases a 
                JOIN laws l ON a.law_id = l.id 
                WHERE a.alias = ? AND l.status = '有效'
            """, (query,))
            rows = cursor.fetchall()
            for r in rows:
                expanded_terms.add(r[0])
            
            # 查 title -> aliases
            # 场景: 用户搜 "中华人民共和国民法典", 扩展为 "民法典"
            cursor.execute("""
                SELECT a.alias 
                FROM laws l 
                JOIN law_aliases a ON l.id = a.law_id 
                WHERE l.title = ?
            """, (query,))
            rows = cursor.fetchall()
            for r in rows:
                expanded_terms.add(r[0])

            # 3. 概念同义词扩展 (Concept Synonyms)
            # 查 term -> canonical_term
            # 场景: "债权人撤销权" -> "撤销权" (标准概念)
            cursor.execute("SELECT canonical_term FROM concept_synonyms WHERE term = ?", (query,))
            row = cursor.fetchone()
            if row:
                expanded_terms.add(row[0])
                # 还可以进一步查标准概念的同义词? 暂时不递归，避免发散
            
            # 查 canonical_term -> terms
            # 场景: "撤销权" -> "债权人撤销权", "合同撤销权"
            cursor.execute("SELECT term FROM concept_synonyms WHERE canonical_term = ?", (query,))
            rows = cursor.fetchall()
            for r in rows:
                expanded_terms.add(r[0])

    except Exception as e:
        logger.error(f"Query expansion failed: {e}")
        return query

    # 4. 构建 OR 查询
    # 如果扩展后有多个词，用 OR 连接
    # 注意: FTS5 的 OR 语法是 "A OR B"
    # 如果原词包含空格 (已经是复合查询)，则不扩展，避免语法错误
    if " " in query:
        return query
        
    unique_terms = sorted(list(expanded_terms), key=len, reverse=True) # 长词在前
    if len(unique_terms) == 1:
        return unique_terms[0]
    
    # 转义双引号
    safe_terms = [f'"{t.replace(chr(34), "")}"' for t in unique_terms]
    return " OR ".join(safe_terms)

if __name__ == "__main__":
    # Test
    print(expand_query("民法典"))
    print(expand_query("撤销权"))
    print(expand_query("合同法")) # 已废止，但如果有别名关联到有效法? 
    # (注意: 别名表中合同法可能没关联到有效法律，或者关联到了民法典? 需检查数据)
