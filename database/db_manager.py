# -*- coding: utf-8 -*-
"""
数据库管理器
提供法律数据库的所有CRUD操作和查询功能
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager

class DatabaseManager:
    """法律数据库管理类"""
    
    def __init__(self, db_path: str = "legal_database.db"):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._ensure_database()
    
    def _ensure_database(self):
        """确保数据库和表存在"""
        dirname = os.path.dirname(self.db_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        
        # 如果数据库不存在，创建它
        if not os.path.exists(self.db_path):
            self._create_database()
    
    def _create_database(self):
        """创建数据库和所有表"""
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        
        if os.path.exists(schema_path):
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            with self.get_connection() as conn:
                conn.executescript(schema_sql)
                conn.commit()
        
        print(f"[OK] Database created: {self.db_path}")
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 返回字典形式的结果
        try:
            yield conn
        finally:
            conn.close()
    
    # ==================== 法律相关操作 ====================
    
    def insert_law(self, law_data: Dict) -> int:
        """插入一部法律"""
        now = datetime.now().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO laws (
                    title, short_title, category, issuing_authority, 
                    document_number, publish_date, effective_date, 
                    expiry_date, status, source_url, content,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                law_data.get('title'),
                law_data.get('short_title'),
                law_data.get('category'),
                law_data.get('issuing_authority'),
                law_data.get('document_number'),
                law_data.get('publish_date'),
                law_data.get('effective_date'),
                law_data.get('expiry_date'),
                law_data.get('status', 'active'),
                law_data.get('source_url'),
                law_data.get('content'),
                now,
                now
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_law_by_id(self, law_id: int) -> Optional[Dict]:
        """根据ID获取法律"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM laws WHERE id = ?", (law_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_statistics(self) -> Dict:
        """获取数据库统计信息"""
        with self.get_connection() as conn:
            stats = {}
            try:
                # 总法律数
                cursor = conn.execute("SELECT COUNT(*) as count FROM laws WHERE status = 'active'")
                stats['total_laws'] = cursor.fetchone()['count']
                
                # 按类别统计
                cursor = conn.execute("""
                    SELECT category, COUNT(*) as count 
                    FROM laws 
                    WHERE status = 'active'
                    GROUP BY category
                """)
                stats['by_category'] = {row['category']: row['count'] for row in cursor.fetchall()}
                
                # 总法条数
                cursor = conn.execute("SELECT COUNT(*) as count FROM articles")
                stats['total_articles'] = cursor.fetchone()['count']
                
                # 数据库大小
                if os.path.exists(self.db_path):
                    stats['db_size_mb'] = os.path.getsize(self.db_path) / (1024 * 1024)
                else:
                    stats['db_size_mb'] = 0
            except:
                stats = {'error': 'Table not found'}
            
            return stats
    
    def search_laws_pro(self, query: str, filters: Dict = None, limit: int = 20) -> List[Dict]:
        """
        高级全文检索 (FTS5)
        
        Args:
            query: 搜索关键词
            filters: 过滤条件 {'status': '有效', 'category': '法律'}
            limit: 返回数量
            
        Returns:
            List[Dict]: 包含高亮摘要的法律列表
        """
        if not filters: filters = {}
        
        with self.get_connection() as conn:
            # 构建 FTS 查询语句
            # 使用 snippet(laws_fts, 1, '<b>', '</b>', '...', 64) 获取 full_text 列的高亮
            # 列索引: 0=title, 1=full_text
            
            # 处理 query，避免语法错误
            clean_query = query.replace('"', '""')
            fts_query = f'"{clean_query}"'
            
            sql = """
                SELECT 
                    l.id, l.title, l.publish_date, l.status, l.category,
                    snippet(laws_fts, 1, '【', '】', '...', 64) as snippet,
                    bm.rank
                FROM laws_fts bm 
                JOIN laws l ON l.id = bm.rowid 
                WHERE laws_fts MATCH ?
            """
            params = [fts_query]
            
            # 应用过滤器
            if filters.get('status'):
                sql += " AND l.status = ?"
                params.append(filters['status'])
            if filters.get('category'):
                sql += " AND l.category = ?"
                params.append(filters['category'])
                
            sql += " ORDER BY bm.rank LIMIT ?"
            params.append(limit)
            
            try:
                cursor = conn.execute(sql, params)
                return [dict(row) for row in cursor.fetchall()]
            except sqlite3.OperationalError as e:
                print(f"Search error: {e}")
                return []

    def get_law_structure(self, law_id: int) -> Dict:
        """
        获取法规的层级结构 (TOC)
        
        Returns:
            Dict: {
                'title': '民法典',
                'structure': [
                    {'type': '编', 'title': '第一编 总则', 'children': [...]},
                    ...
                ]
            }
        """
        law = self.get_law_by_id(law_id)
        if not law: return None
        
        content = law.get('content', '') or ''
        structure = []
        current_bian = None
        current_zhang = None
        current_jie = None
        
        import re
        
        # 正则匹配模式
        p_bian = re.compile(r'^\s*(第[一二三四五六七八九十]+编)\s+(.+)$')
        p_zhang = re.compile(r'^\s*(第[一二三四五六七八九十]+章)\s+(.+)$')
        p_jie = re.compile(r'^\s*(第[一二三四五六七八九十]+节)\s+(.+)$')
        p_tiao = re.compile(r'^\s*(第[一二三四五六七八九十百]+条)\s+')
        
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # 匹配 编
            m_bian = p_bian.match(line)
            if m_bian:
                current_bian = {'type': '编', 'name': m_bian.group(1), 'title': m_bian.group(2), 'children': []}
                structure.append(current_bian)
                current_zhang = None # 重置章
                current_jie = None   # 重置节
                continue
                
            # 匹配 章
            m_zhang = p_zhang.match(line)
            if m_zhang:
                current_zhang = {'type': '章', 'name': m_zhang.group(1), 'title': m_zhang.group(2), 'children': []}
                if current_bian:
                    current_bian['children'].append(current_zhang)
                else:
                    structure.append(current_zhang) # 没有编的情况
                current_jie = None # 重置节
                continue
                
            # 匹配 节
            m_jie = p_jie.match(line)
            if m_jie:
                current_jie = {'type': '节', 'name': m_jie.group(1), 'title': m_jie.group(2), 'children': []}
                if current_zhang:
                    current_zhang['children'].append(current_jie)
                elif current_bian: # 特殊情况：有编无章直接节（少见）
                     current_bian['children'].append(current_jie)
                else:
                    structure.append(current_jie)
                continue
                
            # 匹配 条 (只记录条号，不记录内容，保持目录轻量)
            # 如果需要定位，可以记录行号或字符索引
            # 这里简化处理，暂不把“条”放入目录树，因为条目太多
            # 如果用户需要“民法典结构”，通常是指编章节
            
        return {
            'id': law['id'],
            'title': law['title'],
            'toc': structure
        }

# 测试代码
if __name__ == "__main__":
    db = DatabaseManager()
    stats = db.get_statistics()
    print("[STATS] Database stats:")
    print(f"  - Total Laws: {stats.get('total_laws', 0)}")
    print(f"  - Total Articles: {stats.get('total_articles', 0)}")
