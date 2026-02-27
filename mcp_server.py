# -*- coding: utf-8 -*-
"""
增强版MCP服务器 - 带连接池和缓存
极大提升查询速度
"""
from mcp.server.fastmcp import FastMCP
import sqlite3
import re
import os
import sys
import logging
from pathlib import Path
from functools import lru_cache
from contextlib import contextmanager
import threading
import jieba
import jieba.analyse

# 同步预热 jieba 词典，避免首次搜索时 1-2s 的加载延迟
jieba.initialize()
try:
    from query_rewriter import expand_query
except ImportError:
    def expand_query(q): return q

# 配置 logging 到 stderr（MCP 使用 stdout 进行 JSON-RPC 通信，禁止 print）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("legal-db")

# 初始化 FastMCP
mcp = FastMCP("Legal-Database")

try:
    from vector_db import get_vector_index
    # Lazy-init: 首次搜索时才加载模型和向量
    vdb = True  # marker: vector_db is available
except ImportError:
    logger.warning("vector_db or dependencies not found. Semantic search disabled.")
    vdb = None

DB_PATH = Path(__file__).parent / "legal_database.db"

# 向量引擎就绪标志 — 搜索函数会等待此 Event，避免与预加载竞争
_vector_ready = threading.Event()

# Async preload of vector index to avoid cold start latency
if vdb:
    def _preload_vector_index():
        import time
        t0 = time.time()
        try:
            from vector_db import get_vector_index
            idx = get_vector_index(str(DB_PATH))
            # Force load model + matrix
            idx._load()
            logger.info(f"Vector index preloaded in {time.time()-t0:.1f}s. Articles: {len(idx._article_ids)}")
        except Exception as e:
            logger.warning(f"Vector index preload failed after {time.time()-t0:.1f}s: {e}")
        finally:
            _vector_ready.set()  # 无论成败都标记完成，避免搜索永久阻塞
            
    # Daemon thread ensures it doesn't block shutdown
    _preload_thread = threading.Thread(target=_preload_vector_index, daemon=True)
    _preload_thread.start()
else:
    _vector_ready.set()  # 无向量引擎时立即标记就绪

# ========== 连接池实现 ==========
class ConnectionPool:
    """简单的SQLite连接池"""
    def __init__(self, db_path, pool_size=5):
        self.db_path = db_path
        self.pool_size = pool_size
        self.connections = []
        self.lock = threading.Lock()
        
        # 预创建连接
        for _ in range(pool_size):
            try:
                conn = sqlite3.connect(db_path, check_same_thread=False)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA cache_size=-64000")
                conn.execute("PRAGMA temp_store=MEMORY")
                self.connections.append(conn)
            except:
                pass
    
    @contextmanager
    def get_connection(self):
        """获取连接的上下文管理器"""
        with self.lock:
            if self.connections:
                conn = self.connections.pop()
            else:
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                conn.execute("PRAGMA journal_mode=WAL")
        
        try:
            yield conn
        finally:
            with self.lock:
                if len(self.connections) < self.pool_size:
                    self.connections.append(conn)
                else:
                    conn.close()

# 创建全局连接池
_pool = ConnectionPool(DB_PATH, pool_size=5)

def get_db_connection():
    """获取数据库连接"""
    return _pool.get_connection()

# ========== 缓存实现 ==========

@lru_cache(maxsize=1000)
def resolve_law_alias_cached(query: str):
    """解析法律别名(带缓存)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT l.id, l.title, la.confidence
                FROM law_aliases la
                JOIN laws l ON la.law_id = l.id
                WHERE la.alias = ? AND l.status = '有效'
                ORDER BY la.confidence DESC, l.publish_date DESC
                LIMIT 1
            """, (query,))
            result = cursor.fetchone()
            if result: return result
            
            cursor.execute("""
                SELECT l.id, l.title, la.confidence * 0.9 as adjusted_conf
                FROM law_aliases la
                JOIN laws l ON la.law_id = l.id
                WHERE la.alias LIKE ? AND l.status = '有效'
                ORDER BY adjusted_conf DESC, l.publish_date DESC
                LIMIT 1
            """, (f"%{query}%",))
            return cursor.fetchone()
        except Exception as e:
            logger.warning(f"Alias resolution failed for '{query}': {e}")
            return None

@lru_cache(maxsize=500)
def get_law_by_id_cached(law_id: int):
    """根据ID获取法律信息(带缓存)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT title, publish_date, category, status, content
            FROM laws WHERE id = ?
        """, (law_id,))
        return cursor.fetchone()

# ========== 概念检索实现 ==========

@lru_cache(maxsize=500)
def resolve_concept_cached(query: str):
    """
    解析法律概念(带缓存)
    返回: list of (topic, law_title, law_id, article_hints, relevance) 或 空列表
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        results = []

        # 尝试匹配的候选词列表 (优先完整查询, 然后子短语, 最后单个词)
        candidates = [query]
        tokens = query.split()
        if len(tokens) > 1:
            # 添加所有连续子短语 (从长到短)
            for length in range(len(tokens) - 1, 0, -1):
                for start in range(len(tokens) - length + 1):
                    sub = "".join(tokens[start:start + length])
                    if sub != query:
                        candidates.append(sub)
            # 添加单个词
            for t in tokens:
                if t not in candidates:
                    candidates.append(t)

        for candidate in candidates:
            # 1. 直接匹配 law_topics
            try:
                cursor.execute("""
                    SELECT t.topic, l.title, l.id, t.article_hints, t.relevance
                    FROM law_topics t
                    JOIN laws l ON t.law_id = l.id
                    WHERE t.topic = ? AND l.status = '有效'
                    ORDER BY t.relevance DESC
                """, (candidate,))
                results = cursor.fetchall()
                if results:
                    return tuple(results)
            except Exception as e:
                logger.warning(f"Concept search (exact) failed: {e}")

            # 2. 同义词扩展
            try:
                cursor.execute("""
                    SELECT canonical_term FROM concept_synonyms WHERE term = ?
                """, (candidate,))
                synonyms = [r[0] for r in cursor.fetchall()]

                for syn in synonyms:
                    cursor.execute("""
                        SELECT t.topic, l.title, l.id, t.article_hints, t.relevance
                        FROM law_topics t
                        JOIN laws l ON t.law_id = l.id
                        WHERE t.topic = ? AND l.status = '有效'
                        ORDER BY t.relevance DESC
                    """, (syn,))
                    results.extend(cursor.fetchall())

                if results:
                    return tuple(results)
            except Exception as e:
                logger.warning(f"Concept search (synonym) failed: {e}")

        # 3. 模糊匹配 law_topics
        try:
            cursor.execute("""
                SELECT t.topic, l.title, l.id, t.article_hints, t.relevance
                FROM law_topics t
                JOIN laws l ON t.law_id = l.id
                WHERE t.topic LIKE ? AND l.status = '有效'
                ORDER BY t.relevance DESC
                LIMIT 10
            """, (f"%{query}%",))
            results = cursor.fetchall()
            if results:
                return tuple(results)
        except Exception as e:
            logger.warning(f"Concept search (fuzzy) failed: {e}")

        return ()

def _extract_articles_by_hints(content, hints_str):
    """根据 article_hints (如 '第535-537条') 从法律全文中提取对应条文"""
    if not content or not hints_str:
        return ""

    # 解析 hints: "第535-537条", "第538条,第540条", "第535-537条,第538-542条"
    import re as _re
    target_nums = set()
    for part in hints_str.replace("，", ",").split(","):
        part = part.strip().replace("第", "").replace("条", "")
        if "-" in part:
            try:
                start, end = part.split("-")
                for n in range(int(start), int(end) + 1):
                    target_nums.add(n)
            except ValueError:
                pass
        else:
            try:
                target_nums.add(int(part))
            except ValueError:
                pass

    if not target_nums:
        return ""

    # 将数字转为中文条号匹配
    articles_text = []
    # 按"第X条"拆分正文
    splits = _re.split(r'(第[零一二三四五六七八九十百千万]+条)', content)
    for i in range(1, len(splits), 2):
        article_num_str = splits[i]  # "第五百三十五条"
        body = splits[i + 1] if i + 1 < len(splits) else ""
        # 将中文条号转数字 (复用 article_splitter.cn2an_convert)
        try:
            from article_splitter import cn2an_convert
            num = cn2an_convert(article_num_str.replace("第", "").replace("条", ""))
        except Exception:
            num = 0
        if num in target_nums:
            text = (article_num_str + body).strip()
            # 截取合理长度
            if len(text) > 500:
                text = text[:500] + "..."
            articles_text.append(text)

    return "\n\n".join(articles_text)

def _extract_articles_by_keyword(content, keyword, max_articles=8):
    """从法律全文中提取包含关键词的条文

    支持智能匹配: 如果完整关键词无匹配，尝试子串。
    例如 "债权人代位权" → 也匹配包含 "代位权" 的条文。
    """
    if not content or not keyword:
        return ""

    # 构建匹配词列表: 原词 + 可能的核心子词（取后半段2-4字）
    match_terms = [keyword]
    if len(keyword) > 3:
        # 尝试后半段子串 (如 "债权人代位权" → "代位权")
        for sub_len in range(3, len(keyword)):
            sub = keyword[len(keyword) - sub_len:]
            if sub != keyword:
                match_terms.append(sub)

    articles_text = []
    splits = re.split(r'(第[零一二三四五六七八九十百千万]+条)', content)
    for i in range(1, len(splits), 2):
        article_num_str = splits[i]
        body = splits[i + 1] if i + 1 < len(splits) else ""
        if any(term in body for term in match_terms):
            text = (article_num_str + body).strip()
            if len(text) > 400:
                text = text[:400] + "..."
            articles_text.append(text)
            if len(articles_text) >= max_articles:
                break

    return "\n\n".join(articles_text)

def format_concept_results(concept_hits, query, limit=15, inline_articles=True):
    """将概念检索结果格式化为输出字符串，可选内联条文内容"""
    if not concept_hits:
        return None

    # 去重 (同一部法律只显示一次，合并条文)
    seen = {}
    for topic, law_title, law_id, hints, relevance in concept_hits:
        if law_id not in seen:
            seen[law_id] = {
                'title': law_title,
                'topics': [topic],
                'hints': [hints],
                'relevance': relevance
            }
        else:
            if topic not in seen[law_id]['topics']:
                seen[law_id]['topics'].append(topic)
            if hints not in seen[law_id]['hints']:
                seen[law_id]['hints'].append(hints)

    entries = []
    for law_id, info in sorted(seen.items(), key=lambda x: -x[1]['relevance']):
        topics_str = ", ".join(info['topics'][:3])
        hints_str = ", ".join(info['hints'][:3])
        entry = (
            f"📌 {info['title']}\n"
            f"   概念: {topics_str}\n"
            f"   相关条文: {hints_str}"
        )

        # 内联展示条文内容
        if inline_articles:
            law_info = get_law_by_id_cached(law_id)
            if law_info and law_info[4]:
                articles_text = _extract_articles_by_hints(law_info[4], hints_str)
                if articles_text:
                    entry += f"\n\n{articles_text}"

        entries.append(entry)
        if len(entries) >= limit:
            break

    return f"🔍 概念检索 '{query}' 命中 {len(entries)} 部法律:\n\n" + "\n\n".join(entries)

# ========== MCP工具函数 ==========

@mcp.tool()
def search_laws(query: str, category: str = None, status: str = "有效", limit: int = 15):
    """
    智能搜索法律法规 (Pro版)
    返回结果包含高亮摘要，帮助判断相关性。
    支持别名搜索（如"民法典" -> "中华人民共和国民法典"）。
    支持概念搜索（如"债权人撤销权" -> 民法典第538-542条）。
    """
    # 1. 尝试别名匹配 (不再 early return，继续搜索补充相关司法解释等)
    alias_result_text = ""
    alias_match = resolve_law_alias_cached(query)
    if alias_match:
        law_id, title, confidence = alias_match
        law_info = get_law_by_id_cached(law_id)
        if law_info and (not category or law_info[2] == category):
            content_preview = law_info[4][:100].replace('\n', ' ') + "..." if law_info[4] else ""
            alias_result_text = f"📌 精确匹配:\n标题: {law_info[0]}\n日期: {law_info[1]}\n状态: {law_info[3]}\n摘要: {content_preview}"

    # 1.5 概念检索 (law_topics + concept_synonyms)
    concept_hits = resolve_concept_cached(query)
    concept_output = ""
    if concept_hits:
        concept_output = format_concept_results(concept_hits, query, limit) or ""

    # 2. FTS 全文检索 (带摘要) — 即使概念命中也继续搜索，补充相关司法解释等
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 清理查询词
        clean_query = query.replace('"', '""')
        fts_query = f'"{clean_query}"'

        # 尝试精确短语匹配
        sql = """
            SELECT
                l.id, l.title, l.publish_date, l.category, l.status,
                snippet(laws_fts, 1, '<b>', '</b>', '...', 64) as snippet
            FROM laws_fts bm
            JOIN laws l ON l.id = bm.rowid
            WHERE laws_fts MATCH ?
        """
        params = [fts_query]

        if category: sql += " AND l.category = ?"; params.append(category)
        if status: sql += " AND l.status = ?"; params.append(status)

        sql += " ORDER BY bm.rank LIMIT ?"
        params.append(limit)

        try:
            cursor.execute(sql, params)
            results = cursor.fetchall()
        except Exception as e:
            logger.warning(f"FTS Direct search failed: {e}")
            results = []

        # 中文智能分词 (用于后续 AND/OR/LIKE 搜索)
        if " " not in query and any("\u4e00" <= c <= "\u9fff" for c in query):
            tokens = jieba.lcut_for_search(query)
            tokens = [t for t in tokens if len(t) >= 2]  # 过滤单字
            if not tokens:
                tokens = [query]
        else:
            tokens = query.split()

        # 2b. 尝试 AND 匹配 (所有词都包含)
        if not results and len(tokens) > 1:
            fts_query_and = " AND ".join([f'"{t}"' for t in tokens])
            params[0] = fts_query_and
            try:
                cursor.execute(sql, params)
                results = cursor.fetchall()
            except Exception as e:
                logger.warning(f"FTS AND search failed: {e}")

    # 3. 降级模糊搜索 (标题+正文) - 优先于 FTS OR
    # 当 FTS AND 失败时，与其返回 FTS OR 的松散结果，不如尝试 LIKE AND
    fallback_results = []

    def log_debug(msg):
        logger.debug(msg)

    log_debug(f"Search Query: {query}")
    log_debug(f"FTS AND results: {len(results)}")

    if not results:
        log_debug(f"Entering Fallback Loop.")
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # 3a. 构造 AND 查询 (所有词都必须出现)
            sql_title = "SELECT l.id, l.title, l.publish_date, l.category, l.status FROM laws l WHERE 1=1"
            params_title = []
            for term in tokens:
                sql_title += " AND l.title LIKE ?"
                params_title.append(f"%{term}%")

            sql_title += " ORDER BY l.publish_date DESC LIMIT ?"
            params_title.append(limit)

            cursor.execute(sql_title, params_title)
            rows_title = cursor.fetchall()
            log_debug(f"Title match results: {len(rows_title)}")

            # 3b. 如果标题没匹配到，匹配正文
            rows_content = []
            if not rows_title:
                 sql_content = "SELECT l.id, l.title, l.publish_date, l.category, l.status FROM laws l WHERE 1=1"
                 params_content = []
                 for term in tokens:
                     sql_content += " AND l.content LIKE ?"
                     params_content.append(f"%{term}%")

                 # 增加民法典权重
                 sql_content += " ORDER BY CASE WHEN l.title LIKE '%民法典%' THEN 0 ELSE 1 END, l.publish_date DESC LIMIT ?"
                 params_content.append(limit)

                 try:
                    log_debug(f"Executing Content SQL with {len(params_content)} params")
                    cursor.execute(sql_content, params_content)
                    rows_content = cursor.fetchall()
                    log_debug(f"Content match results: {len(rows_content)}")
                 except Exception as e:
                    log_debug(f"Content SQL Error: {e}")

            fallback_results = rows_title + rows_content

    # 4. FTS OR 匹配 (最后兜底)
    if not results and not fallback_results and len(tokens) > 1:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            fts_query_or = " OR ".join([f'"{t}"' for t in tokens])
            sql = "SELECT l.id, l.title, l.publish_date, l.category, l.status, bm.rank FROM laws_fts bm JOIN laws l ON l.id = bm.rowid WHERE laws_fts MATCH ?"
            params = [fts_query_or]
            
            if category: sql += " AND l.category = ?"; params.append(category)
            if status: sql += " AND l.status = ?"; params.append(status)
            
            sql += " ORDER BY bm.rank LIMIT ?"
            params.append(limit)
            try:
                cursor.execute(sql, params)
                results = cursor.fetchall()
            except Exception as e:
                logger.warning(f"FTS OR search failed: {e}")

    # 5. 向量语义检索 (Vector Search) - 补充语义匹配
    # 如果结果仍然很少 (< limit)，或者 FTS 没结果，尝试语义搜索
    input_results_count = len(results) + len(fallback_results)
    vector_results = []
    
    if vdb and (input_results_count < limit or len(query) > 4):
        # 等待预加载完成（最多 25s），避免与预加载线程竞争
        _vector_ready.wait(timeout=15.0)

        search_result_holder = {"hits": []}

        def _run_vector_search():
            try:
                idx = get_vector_index(str(DB_PATH))
                search_result_holder["hits"] = idx.search(query, limit=5)
            except Exception as e:
                logger.error(f"Vector search inner failed: {e}")

        t = threading.Thread(target=_run_vector_search)
        t.start()
        t.join(timeout=10.0)  # 10s timeout for vector search

        if t.is_alive():
            logger.warning(f"Vector search timed out for query: {query}")
        
        vec_hits = search_result_holder["hits"]
        if vec_hits:
                # VectorIndex.search 返回: [{'article_id': int, 'score': float, 'raw_score': float}]
                vec_ids = [h['article_id'] for h in vec_hits]
                placeholders = ",".join(["?" for _ in vec_ids])
                with get_db_connection() as conn:
                    cur = conn.cursor()
                    cur.execute(f"""
                        SELECT la.id, la.law_id, l.title, l.publish_date, l.category, l.status,
                               substr(la.content, 1, 100) as snippet
                        FROM law_articles la
                        JOIN laws l ON la.law_id = l.id
                        WHERE la.id IN ({placeholders})
                    """, vec_ids)
                    rows_map = {r[0]: r[1:] for r in cur.fetchall()}
                
                for hit in vec_hits:
                    aid = hit['article_id']
                    if aid in rows_map:
                        law_id, title, date, cat, status, snippet = rows_map[aid]
                        snippet_clean = snippet.replace('\n', ' ') + "..."
                        vector_results.append((
                            law_id, title, date, cat, status,
                            f"[语义匹配 {hit['score']:.2f}] {snippet_clean}"
                        ))


    # 格式化输出
    final_rows = []

    # 辅助函数: 添加结果并去重
    seen_ids = set()

    def add_rows(rows, source_label=""):
        for r in rows:
            # r 结构可能不同:
            # FTS: (id, title, date, cat, status, snippet) — 6列
            # Fallback: (id, title, date, cat, status) — 5列
            # Vector: (id, title, date, cat, status, snippet) — 6列
            law_id = r[0]
            if law_id in seen_ids: continue
            seen_ids.add(law_id)

            title = r[1]
            status_str = r[4] if len(r) > 4 else "未知"
            snippet = ""

            if len(r) > 5:  # FTS or Vector with snippet
                snippet = r[5]
                if isinstance(snippet, (int, float)): snippet = ""

            entry = f"📄 {title} ({status_str})"
            if snippet and isinstance(snippet, str):
                entry += f"\n   摘要: {snippet}"

            # 当有概念命中时，按需获取 content 并提取相关条文
            if concept_hits:
                law_info = get_law_by_id_cached(law_id)
                if law_info and law_info[4]:
                    matched_articles = _extract_articles_by_keyword(law_info[4], query)
                    if matched_articles:
                        entry += f"\n\n{matched_articles}"

            final_rows.append(entry)

    # 概念命中的 law_id 要排除，避免重复
    if concept_hits:
        for _, _, cid, _, _ in concept_hits:
            seen_ids.add(cid)

    # 别名匹配的 law_id 也要排除，避免重复
    if alias_match:
        seen_ids.add(alias_match[0])

    # 简单合并: fallback -> results -> vector
    add_rows(fallback_results)
    add_rows(results)
    add_rows(vector_results)

    # 组装最终输出: 别名 > 概念 > FTS/LIKE/Vector
    parts = []
    if alias_result_text:
        parts.append(alias_result_text)
    if concept_output:
        parts.append(concept_output)
    if final_rows:
        if parts:
            parts.append("--- 相关法律法规 ---")
        parts.append("\n\n".join(final_rows))

    if parts:
        return "\n\n".join(parts)
    else:
        return "未找到相关法律法规。"

def _get_cross_references(law_id, article_int):
    """查询 article_cross_references 获取关联条文"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT l.title, acr.target_article_int, la.content
                FROM article_cross_references acr
                JOIN laws l ON acr.target_law_id = l.id
                LEFT JOIN law_articles la ON la.law_id = acr.target_law_id AND la.article_number_int = acr.target_article_int
                WHERE acr.source_law_id = ? AND acr.source_article_int = ?
            """, (law_id, article_int))
            rows = cursor.fetchall()
            
            if not rows: return ""
            
            lines = []
            for title, art_int, content in rows:
                if not content: content = ""
                # 截取前100字
                preview = content[:100].replace("\n", " ") + "..." if len(content) > 100 else content.replace("\n", " ")
                lines.append(f"🔗 {title} 第{art_int}条\n   > {preview}")
            return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Cross-reference query failed: {e}")
        return ""

def _get_sibling_articles(law_id, article_int, conn):
    """查询同一 chapter_path 下的相邻条文"""
    try:
        cursor = conn.cursor()
        # 1. 获取当前条文的 chapter_path
        cursor.execute(
            "SELECT chapter_path FROM law_articles WHERE law_id = ? AND article_number_int = ? LIMIT 1",
            (law_id, article_int)
        )
        row = cursor.fetchone()
        if not row or not row[0]:
            return ""
        
        chapter_path = row[0]
        # 2. 查询同 chapter_path 下的所有条文号（排除自身）
        cursor.execute(
            """SELECT article_number_int, article_number_str 
            FROM law_articles 
            WHERE law_id = ? AND chapter_path = ? AND article_number_int != ?
            ORDER BY article_number_int""",
            (law_id, chapter_path, article_int)
        )
        siblings = cursor.fetchall()
        if not siblings:
            return ""
        
        # 3. 格式化为紧凑列表
        # 筛选: 距离当前条文最近的条文
        siblings.sort(key=lambda x: abs(x[0] - article_int))
        nearest = sorted(siblings[:10], key=lambda x: x[0]) # 重新按条号排序
        
        items = [f"第{s[1]}条" for s in nearest]
        return f"同属「{chapter_path}」: {', '.join(items)}"
    except Exception as e:
        logger.warning(f"Sibling article query failed: {e}")
        return ""


def _expand_synonyms(keyword: str, conn) -> list:
    """查询 search_synonyms 表，返回关键词的所有同义词（含自身）。
    
    示例: _expand_synonyms('股权') → ['股权', '出资额', '股份', '持股', '股东权益']
    """
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s2.word FROM search_synonyms s1
            JOIN search_synonyms s2 ON s1.group_id = s2.group_id
            WHERE s1.word = ?
        """, (keyword,))
        results = [r[0] for r in cursor.fetchall()]
        return results if results else [keyword]
    except Exception:
        return [keyword]


def _build_fts_query_with_synonyms(tokens: list, conn) -> str:
    """为每个关键词扩展同义词，构造 FTS5 AND 查询。
    
    示例: tokens=['离婚', '股权'] →
      '"离婚" AND ("股权" OR "出资额" OR "股份" OR "持股" OR "股东权益")'
    """
    parts = []
    for token in tokens:
        synonyms = _expand_synonyms(token, conn)
        if len(synonyms) > 1:
            or_clause = " OR ".join([f'"{s}"' for s in synonyms])
            parts.append(f"({or_clause})")
        else:
            parts.append(f'"{token}"')
    return " AND ".join(parts)


def _parse_article_number_input(article_number: str) -> int:
    """将用户输入的条号解析为整数。支持 '1023', '第1023条', '第一千零二十三条' 等格式。"""
    cleaned = article_number.replace("第", "").replace("条", "").strip()
    # 去除 "之一" 等后缀
    suffix_match = re.match(r'^(.+?)(之[一二三四五六七八九十]+)?$', cleaned)
    if suffix_match:
        cleaned = suffix_match.group(1)

    if cleaned.isdigit():
        return int(cleaned)

    # 中文数字转换
    try:
        from article_splitter import cn2an_convert
        return cn2an_convert(cleaned)
    except Exception:
        return 0


@mcp.tool()
def get_article(law_title: str, article_number: str):
    """获取具体法条内容,并显示法律状态信息。"""
    # 1. 解析条号为整数
    target_int = _parse_article_number_input(article_number)

    # 2. 解析法律名称
    alias_match = resolve_law_alias_cached(law_title)

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 查找 law_id 和基本信息
        if alias_match:
            law_id = alias_match[0]
            cursor.execute("SELECT title, publish_date, status FROM laws WHERE id = ?", (law_id,))
            law_info = cursor.fetchone()
        else:
            # 先精确匹配标题
            cursor.execute(
                "SELECT id, title, publish_date, status FROM laws "
                "WHERE title = ? ORDER BY publish_date DESC LIMIT 1",
                (law_title,)
            )
            row = cursor.fetchone()
            # 再 LIKE 模糊匹配
            if not row:
                cursor.execute(
                    "SELECT id, title, publish_date, status FROM laws "
                    "WHERE title LIKE ? ORDER BY publish_date DESC LIMIT 1",
                    (f"%{law_title}%",)
                )
                row = cursor.fetchone()
            if not row:
                return f"未找到法律: {law_title}"
            law_id = row[0]
            law_info = row[1:]

        if not law_info:
            return f"未找到法律: {law_title}"

        real_title, date, status = law_info
        status_suffix = f"\n\n📋 法律状态: {status}"
        if status == "已废止":
            status_suffix += " ⚠️ 已失效!"
        elif status == "有效":
            status_suffix += " ✅"

        # 3. 精确查询 law_articles (整数匹配)
        if target_int > 0:
            cursor.execute(
                "SELECT content, article_number_str, chapter_path "
                "FROM law_articles WHERE law_id = ? AND article_number_int = ?",
                (law_id, target_int)
            )
            results = cursor.fetchall()
            if results:
                # 可能有多条 (e.g. 第120条 和 第120条之一)
                parts = []
                for content, num_str, path in results:
                    header = f"📌 【{real_title}】 第{num_str}条"
                    if path:
                        header += f"\n📂 Path: {path}"
                    header += f"\n📜 Content:\n{content}"
                    parts.append(header)
                
                base_result = "\n\n".join(parts) + status_suffix
                
                # 同章节关联推荐
                try:
                    siblings = _get_sibling_articles(law_id, target_int, conn)
                    if siblings:
                        base_result += "\n\n📑 " + siblings
                except Exception as e:
                     logger.warning(f"Sibling query error: {e}")

                # 司法解释关联
                cross_refs = _get_cross_references(law_id, target_int)
                if cross_refs:
                    base_result += "\n\n📎 相关司法解释:\n" + cross_refs

                return base_result

        # 4. 降级: 模糊匹配 article_number_str
        cleaned = article_number.replace("第", "").replace("条", "").strip()
        cursor.execute(
            "SELECT content, article_number_str, chapter_path FROM law_articles "
            "WHERE law_id = ? AND article_number_str LIKE ? LIMIT 1",
            (law_id, f"%{cleaned}%")
        )
        res = cursor.fetchone()
        
        if res:
            path_str = f"\n📂 Path: {res[2]}" if res[2] else ""
            base_result = f"📌 【{real_title}】 第{res[1]}条 ({date}){path_str}\n📜 Content:\n{res[0]}" + status_suffix
            
            # 尝试为模糊匹配结果添加关联推荐
            try:
                import article_splitter
                # 尝试从 res[1] (e.g. "五百三十八") 转换回数字
                ref_int = article_splitter.cn2an_convert(res[1])
                
                if ref_int > 0:
                    siblings = _get_sibling_articles(law_id, ref_int, conn)
                    if siblings:
                        base_result += "\n\n📑 " + siblings
                        
                    cross_refs = _get_cross_references(law_id, ref_int)
                    if cross_refs:
                        base_result += "\n\n📎 相关司法解释:\n" + cross_refs
            except Exception as e:
                logger.warning(f"Fallback sibling/cross-ref query error: {e}")

            return base_result

        return f"在《{real_title}》中未找到条文: {article_number}"

@mcp.tool()

def search_article_content(keywords: str, limit: int = 10):
    """直接在法条内容中搜索关键词。支持概念搜索，自动扩展同义词。"""
    
    internal_limit = 50 # Fetch more candidates for RRF merging

    
    # 1. 概念检索 (Concept Search)
    concept_results = []
    try:
        concept_hits = resolve_concept_cached(keywords)
        if concept_hits:
            # concept_hits: list of (topic, law_title, law_id, article_hints, relevance)
            # 需要将其转换为标准的 article rows
            with get_db_connection() as conn:
                c_concept = conn.cursor()
                for topic, law_title, law_id, hints, relevance in concept_hits:
                    # 解析 hints: "538", "538-542", "12,15"
                    # 简单支持单号和范围
                    target_articles = []
                    parts = hints.replace("，", ",").split(",")
                    for p in parts:
                        p = p.strip()
                        if "-" in p:
                            try:
                                start, end = map(int, p.split("-"))
                                target_articles.extend(range(start, end + 1))
                            except:
                                pass
                        else:
                            try:
                                target_articles.append(int(p))
                            except:
                                pass
                    
                    if target_articles:
                         placeholders = ",".join(["?" for _ in target_articles])
                         # 查询 law_articles
                         sql_concept = f"""
                            SELECT la.article_number_str, la.content, la.chapter_path,
                                   l.title, l.publish_date, l.status
                            FROM law_articles la
                            JOIN laws l ON la.law_id = l.id
                            WHERE la.law_id = ? 
                              AND la.article_number_int IN ({placeholders})
                              AND l.status = '有效'
                         """
                         params = [law_id] + target_articles
                         c_concept.execute(sql_concept, params)
                         rows = c_concept.fetchall()
                         concept_results.extend(rows)
            
            logger.info(f"概念检索命中: {len(concept_results)} 条文")
    except Exception as e:
        logger.error(f"概念检索出错: {e}")

    # 2. FTS 全文检索 (Text Search)
    fts_results = []
    
    # E2: Query Expansion
    expanded_keywords = expand_query(keywords)
    if expanded_keywords != keywords:
        logger.info(f"Article Search Expanded: {keywords} -> {expanded_keywords}")
    
    # Strategy A: Direct FTS with Expanded Query (if it contains OR syntax)
    if expanded_keywords != keywords and " OR " in expanded_keywords:
        try:
            with get_db_connection() as conn:
                c = conn.cursor()
                sql_direct = """
                    SELECT la.article_number_str, la.content, la.chapter_path,
                           l.title, l.publish_date, l.status
                    FROM law_articles_fts fts
                    JOIN law_articles la ON fts.rowid = la.id
                    JOIN laws l ON la.law_id = l.id
                    WHERE law_articles_fts MATCH ? 
                      AND l.status = '有效'
                    ORDER BY bm25(law_articles_fts)
                    LIMIT ?
                """
                c.execute(sql_direct, (expanded_keywords, internal_limit))
                fts_results = c.fetchall()
        except Exception as e:
            logger.error(f"Expanded FTS failed: {e}")

    # Strategy B: Original Token-based Logic (Fallback if Strategy A failed or skipped)
    if not fts_results:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 智能分词
            if " " not in keywords and any("\u4e00" <= char <= "\u9fff" for char in keywords):
                tokens = jieba.lcut_for_search(keywords)
            else:
                tokens = keywords.split()

            # SQL 模板
            sql = """
                SELECT la.article_number_str, la.content, la.chapter_path,
                       l.title, l.publish_date, l.status
                FROM law_articles_fts fts
                JOIN law_articles la ON fts.rowid = la.id
                JOIN laws l ON la.law_id = l.id
                WHERE law_articles_fts MATCH ? 
                  AND l.status = '有效'
                ORDER BY bm25(law_articles_fts)
                LIMIT ?
            """

            # 尝试不同宽度的 FTS 查询
            queries = []
            # B1. FTS AND + 同义词 (最严)
            queries.append(_build_fts_query_with_synonyms(tokens, conn))
            
            # B2. FTS AND (无同义词)
            if len(tokens) > 1:
                queries.append(" AND ".join([f'"{t}"' for t in tokens]))
            
            # B3. FTS OR (兜底)
            all_terms = []
            for t in tokens:
                all_terms.extend(_expand_synonyms(t, conn))
            queries.append(" OR ".join([f'"{t}"' for t in all_terms]))

            for q in queries:
                try:
                    cursor.execute(sql, (q, internal_limit))
                    res = cursor.fetchall()
                    if res:
                        fts_results = res
                        break # 只要一种策略有结果就采纳
                except Exception as e:
                    logger.warning(f"FTS Strategy B failed for query '{q}': {e}")
                    continue
                    
            # D. LIKE 兜底 (针对 FTS 短词问题)
            if not fts_results and len(tokens) >= 1:
                like_sql = """
                    SELECT la.article_number_str, la.content, la.chapter_path,
                           l.title, l.publish_date, l.status
                    FROM law_articles la
                    JOIN laws l ON la.law_id = l.id
                    WHERE l.status = '有效'
                """
                like_params = []
                for t in tokens:
                    if len(t) >= 2:  # 忽略单字
                        like_sql += " AND la.content LIKE ?"
                        like_params.append(f"%{t}%")
                if like_params:
                    like_sql += " ORDER BY CASE WHEN l.title LIKE '%民法典%' THEN 0 WHEN l.title LIKE '%刑法%' THEN 1 ELSE 2 END LIMIT ?"
                    like_params.append(internal_limit)
                    try:
                        cursor.execute(like_sql, like_params)
                        fts_results = cursor.fetchall()
                    except Exception as e:
                        logger.warning(f"LIKE fallback search failed: {e}")
                        pass

    # 3. 向量检索 (Vector Search) — 带超时保护
    vec_results = []
    vec_hits = []
    if vdb:
        # 等待预加载完成（最多 25s），避免与预加载线程竞争
        _vector_ready.wait(timeout=15.0)

        vec_hit_holder = {"hits": []}
        def _run_article_vec_search():
            try:
                idx = get_vector_index(str(DB_PATH))
                vec_hit_holder["hits"] = idx.search(keywords, limit=internal_limit)
            except Exception as e:
                logger.error(f"Vector search inner failed: {e}")

        vt = threading.Thread(target=_run_article_vec_search)
        vt.start()
        vt.join(timeout=10.0)  # 10s timeout，预加载完成后实际只需 <1s

        if vt.is_alive():
            logger.warning(f"search_article_content vector search timed out: {keywords}")
        else:
            vec_hits = vec_hit_holder["hits"]

    try:
        if vec_hits:
            vec_ids = [h['article_id'] for h in vec_hits]
            if vec_ids:
                placeholders = ",".join(["?" for _ in vec_ids])
                with get_db_connection() as conn:
                    c2 = conn.cursor()
                    c2.execute(f"""
                        SELECT la.id, la.article_number_str, la.content, la.chapter_path,
                            l.title, l.publish_date, l.status
                        FROM law_articles la
                        JOIN laws l ON la.law_id = l.id
                        WHERE la.id IN ({placeholders})
                        AND l.status = '有效'
                    """, vec_ids)
                    rows_map = {r[0]: r[1:] for r in c2.fetchall()}

                for hit in vec_hits:
                    aid = hit['article_id']
                    if aid in rows_map:
                        row = rows_map[aid]
                        score = hit['score']
                        vec_results.append({
                            'row': row,
                            'score': score
                        })
                
                vec_results = [x['row'] for x in vec_results]

    except Exception as e:
        logger.debug(f"Vector search post-processing failed: {e}")

    # 4. RRF Merge
    if not (concept_results or fts_results or vec_results):
        return f"未找到内容包含'{keywords}'的法条。"

    K = 60
    scores = {} # key -> score
    data_map = {} # key -> row

    def merge_list(lst, weight):
        for rank, row in enumerate(lst):
            # row: (num_str, content, path, title, date, status)
            # Unique Key: Law + ArticleNum (or content hash)
            # content is unique enough usually. Or Title + Num.
            key = f"{row[3]}_{row[0]}" 
            rrf = weight / (K + rank + 1)
            scores[key] = scores.get(key, 0) + rrf
            data_map[key] = row

    merge_list(concept_results, 2.0)  # Concept: Very High Weight
    merge_list(fts_results, 1.0)      # FTS: High Weight
    merge_list(vec_results, 0.8)      # Vector: Medium Weight

    # Sort
    sorted_keys = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    final_rows = [data_map[k] for k in sorted_keys[:limit]]

    # Format Output
    formatted = []
    for num_str, content, path, law_title_r, date, status in final_rows:
        snippet = content[:200].replace("\n", " ")
        if len(content) > 200:
            snippet += "..."
        
        path_str = f"📂 Path: {path}" if path else ""
        header = f"📌 【{law_title_r}】 第{num_str}条 ({date})"
        
        parts = [header]
        if path_str:
            parts.append(path_str)
        parts.append(f"📜 Content: {snippet}")
        formatted.append("\n".join(parts))

    return "\n\n".join(formatted)

@mcp.tool()
def check_law_validity(law_title: str):
    """快速检查法律有效状态。"""
    alias = resolve_law_alias_cached(law_title)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if alias:
            cursor.execute("SELECT title, status, publish_date FROM laws WHERE id = ?", (alias[0],))
        else:
            cursor.execute("SELECT title, status, publish_date FROM laws WHERE title LIKE ? ORDER BY publish_date DESC LIMIT 1", (f"%{law_title}%",))
        row = cursor.fetchone()
    
    if not row: return f"未找到法律: {law_title}"
    title, status, date = row
    report = f"📋 法律状态报告: {title}\n发布日期: {date}\n状态: {status}"
    if status == "已废止":
        report += " ⚠️ 该法律已失效! "
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title, publish_date FROM laws WHERE title LIKE ? AND status = '有效' AND publish_date > ? LIMIT 1", (f"%{title[:5]}%", date))
            alt = cursor.fetchone()
            if alt: report += f"\n💡 建议改用: {alt[0]} ({alt[1]})"
    elif status == "有效": report += " ✅"
    return report

@mcp.tool()
def get_law_structure(law_title: str):
    """
    获取法规的目录结构 (TOC)。
    返回编、章、节层级，方便快速了解法规全貌，按需读取特定章节。
    """
    alias_match = resolve_law_alias_cached(law_title)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if alias_match:
            cursor.execute("SELECT id, title, content FROM laws WHERE id = ?", (alias_match[0],))
        else:
            cursor.execute("SELECT id, title, content FROM laws WHERE title LIKE ? ORDER BY publish_date DESC LIMIT 1", (f"%{law_title}%",))
        
        row = cursor.fetchone()
        if not row: return f"未找到法律: {law_title}"
        
        law_id, title, content = row
        if not content: return f"《{title}》暂无正文内容。"
        
        structure = []
        current_bian = None
        current_zhang = None
        current_jie = None
        
        # 简化的正则 (适应更多格式)
        p_bian = re.compile(r'^\s*(第[一二三四五六七八九十]+编)\s+(.+)$')
        p_zhang = re.compile(r'^\s*(第[一二三四五六七八九十]+章)\s+(.+)$')
        p_jie = re.compile(r'^\s*(第[一二三四五六七八九十]+节)\s+(.+)$')
        
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line: continue
            
            m_bian = p_bian.match(line)
            if m_bian:
                current_bian = {'type': '编', 'name': m_bian.group(1), 'title': m_bian.group(2), 'children': []}
                structure.append(current_bian)
                current_zhang = None
                current_jie = None
                continue
                
            m_zhang = p_zhang.match(line)
            if m_zhang:
                current_zhang = {'type': '章', 'name': m_zhang.group(1), 'title': m_zhang.group(2), 'children': []}
                if current_bian: current_bian['children'].append(current_zhang)
                else: structure.append(current_zhang)
                current_jie = None
                continue
                
            m_jie = p_jie.match(line)
            if m_jie:
                current_jie = {'type': '节', 'name': m_jie.group(1), 'title': m_jie.group(2), 'children': []}
                if current_zhang: current_zhang['children'].append(current_jie)
                elif current_bian: current_bian['children'].append(current_jie)
                else: structure.append(current_jie)
                continue
        
        if not structure:
            return f"《{title}》似乎没有采用标准的【编-章-节】结构，可能是单层级条文。建议直接使用 get_article 获取具体法条，或 search_article_content 搜索内容。"
            
        return structure

_LEGAL_STOPWORDS = {
    "当事人", "合同", "约定", "规定", "条款", "双方", "一方", "甲方", "乙方",
    "应当", "可以", "不得", "应该", "必须", "本合同", "协议", "根据", "依据",
    "进行", "情况", "问题", "事项", "内容", "要求", "条件", "方式", "期限",
    "责任", "权利", "义务", "违反", "承担", "履行", "支付", "相关", "有关",
}

@mcp.tool()
def get_legal_basis(case_description: str, limit: int = 5):
    """
    根据案情描述推荐相关法律依据 (Beta)。
    简单的关键词匹配，用于寻找切入点。
    """
    # 截断过长输入，避免分析耗时过长
    text = case_description[:3000]

    # 1. 使用 jieba 分析关键词 (TF-IDF)
    try:
        import jieba.analyse
        # 提取更多候选关键词，再过滤停用词
        raw_keywords = jieba.analyse.extract_tags(text, topK=12)
        keywords = [k for k in raw_keywords if len(k) > 1 and k not in _LEGAL_STOPWORDS][:8]
    except ImportError:
        # 降级方案：简单的分词
        keywords = re.split(r'[，。；：\s、]', text)
        keywords = [k for k in keywords if len(k) >= 2 and k not in _LEGAL_STOPWORDS]

    if not keywords: return "请提供更详细的案情描述。"

    # 2. 构建查询
    # 使用空格连接（search_laws 内部会用 jieba 分词处理）
    query = " ".join(keywords)

    return search_laws(query, limit=limit)

@mcp.tool()
def batch_verify_citations(document_text: str):
    """批量核验文档中的法条引用(如《民法典》第147条、民法典第147条之一、《公司法》第71条第2款)"""
    # 模式1: 《法律名》第X条 (支持"之一"后缀和"第X款")
    pattern1 = re.compile(r'《([^》]+)》第([一二三四五六七八九十百千万零\d]+)条(?:之[一二三四五六七八九十]+)?')
    # 模式2: 无书名号，如 "民法典第147条" (法律名以法/典/条例/规定/办法结尾)
    pattern2 = re.compile(r'(?<![《])([一-龥]{2,10}(?:法|典|条例|规定|办法))第([一二三四五六七八九十百千万零\d]+)条(?:之[一二三四五六七八九十]+)?')

    matches = pattern1.findall(document_text) + pattern2.findall(document_text)
    if not matches: return "未识别到法条引用。"

    report = f"📋 批量核验报告 (发现 {len(matches)} 处)\n" + "="*40 + "\n"
    seen = set()
    for law, num in matches:
        cite = f"《{law}》第{num}条"
        if cite in seen: continue
        seen.add(cite)
        res = get_article(law, num)
        if "已废止" in res: report += f"❌ {cite}: 已废止! ⚠️\n"
        elif "有效" in res: report += f"✅ {cite}: 有效\n"
        else: report += f"❓ {cite}: 无法验证或未找到\n"
    return report

@mcp.tool()
def clear_caches():
    """清除所有内部 LRU 缓存 (当数据库更新后调用)"""
    try:
        resolve_law_alias_cached.cache_clear()
        get_law_by_id_cached.cache_clear()
        resolve_concept_cached.cache_clear()
        if hasattr(expand_query, "cache_clear"):
            expand_query.cache_clear()
        
        # 重新加载向量索引
        if vdb:
            try:
                from vector_db import get_vector_index
                vec_index = get_vector_index(str(DB_PATH))
                vec_index.reload()
            except Exception as e:
                logger.warning(f"Failed to reload vector index: {e}")
                
        return "✅ 所有缓存已清除，向量索引已标记为重载。"
    except Exception as e:
        return f"❌ 缓存清除失败: {e}"

if __name__ == "__main__":
    mcp.run()
