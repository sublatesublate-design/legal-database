# -*- coding: utf-8 -*-
"""
VectorDB — 法条向量检索引擎 (V2)

使用 sentence-transformers 将法条编码为 768 维向量，
存储在 SQLite 的 article_embeddings 表中。
查询时加载全部向量到内存，用 numpy 矩阵运算实现毫秒级检索。

性能:
- ~30,000 条 × 768 维 × float32 ≈ 90 MB 内存
- 首次加载: ~5s (模型) + ~2s (向量)
- 单次查询: <100ms
"""

import sqlite3
import numpy as np
import logging
import sys
import threading
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ========== Embedding 模型 ==========
_model = None
MODEL_NAME = 'BAAI/bge-base-zh-v1.5'
EMBEDDING_DIM = 768


def get_model():
    """懒加载 embedding 模型 (全局单例)"""
    global _model
    if _model is None:
        import time
        t0 = time.time()
        logger.info(f"Loading embedding model: {MODEL_NAME}...")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
        logger.info(f"Embedding model loaded in {time.time()-t0:.1f}s.")
    return _model


def encode_text(text: str) -> np.ndarray:
    """将文本编码为归一化向量"""
    model = get_model()
    return model.encode(text, normalize_embeddings=True)


def encode_batch(texts: List[str], batch_size: int = 64) -> np.ndarray:
    """批量编码文本"""
    model = get_model()
    return model.encode(texts, normalize_embeddings=True, batch_size=batch_size,
                        show_progress_bar=True)


# ========== 数据库操作 ==========

def create_embeddings_table(conn: sqlite3.Connection):
    """创建 article_embeddings 表 (幂等)"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS article_embeddings (
            article_id INTEGER PRIMARY KEY,
            embedding BLOB NOT NULL,
            FOREIGN KEY(article_id) REFERENCES law_articles(id)
        )
    """)
    conn.commit()


def insert_embeddings(conn: sqlite3.Connection, article_ids: List[int],
                      embeddings: np.ndarray):
    """批量插入 embedding"""
    data = []
    for i, aid in enumerate(article_ids):
        blob = embeddings[i].astype(np.float32).tobytes()
        data.append((aid, blob))

    conn.executemany(
        "INSERT OR REPLACE INTO article_embeddings (article_id, embedding) VALUES (?, ?)",
        data
    )
    conn.commit()


# ========== 内存缓存 (核心性能优化) ==========

class VectorIndex:
    """
    内存向量索引。
    首次调用时从 SQLite 加载全部向量到 numpy 矩阵，
    同时加载元数据 (长度, 法律类型) 用于加权排序。
    """

    def __init__(self, db_path: str = 'legal_database.db'):
        self.db_path = db_path
        self._article_ids: Optional[np.ndarray] = None
        self._matrix: Optional[np.ndarray] = None  # shape: (N, 768)
        self._boost_factors: Optional[np.ndarray] = None # shape: (N,)
        self._loaded = False
        self._lock = threading.Lock()

    def _load(self):
        """从 SQLite 加载向量及元数据"""
        if self._loaded:
            return

        with self._lock:
            if self._loaded:
                return

            import time
            t0 = time.time()
            logger.info("Loading vector index and metadata into memory...")
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            # 联合查询: 向量 + 长度 + 法律标题
            cursor.execute("""
                SELECT ae.article_id, ae.embedding, length(la.content), l.title
                FROM article_embeddings ae
                JOIN law_articles la ON ae.article_id = la.id
                JOIN laws l ON la.law_id = l.id
            """)
            rows = cursor.fetchall()

            if not rows:
                logger.warning("No embeddings found.")
                # init empty
                self._article_ids = np.array([], dtype=np.int64)
                self._matrix = np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
                self._boost_factors = np.ones(0, dtype=np.float32)
                self._loaded = True
                return

            ids = []
            vecs = []
            boosts = []
            
            CORE_LAWS = ["中华人民共和国民法典", "中华人民共和国公司法", "中华人民共和国刑法", "中华人民共和国劳动法", "中华人民共和国劳动合同法"]

            for aid, blob, length, title in rows:
                ids.append(aid)
                # Vector
                vec = np.frombuffer(blob, dtype=np.float32)
                vecs.append(vec)
                
                # Calculate Boost Factor
                factor = 1.0
                
                # 1. Core Law Boost (+15%)
                if any(core in title for core in CORE_LAWS):
                    factor *= 1.15
                    
                # 2. Length Penalty (Short procedural articles)
                # "Effective Date" clauses typically < 50 chars
                if length < 50:
                    factor *= 0.5
                elif length < 20: 
                    factor *= 0.1

                boosts.append(factor)

            self._article_ids = np.array(ids, dtype=np.int64)
            self._matrix = np.vstack(vecs)  # shape: (N, 768)
            self._boost_factors = np.array(boosts, dtype=np.float32)
            self._loaded = True

            logger.info(f"Vector index loaded in {time.time()-t0:.1f}s: {len(ids)} articles, {self._matrix.nbytes/1024/1024:.1f} MB")
            
        finally:
            conn.close()

    def search(self, query_text: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        语义搜索 (带加权)。
        Score = Cosine_Similarity * Boost_Factor
        """
        self._load()

        if len(self._article_ids) == 0:
            return []

        # 编码查询
        query_vec = encode_text(query_text)  # shape: (768,)

        # 1. 计算原始相似度 (Cosine)
        raw_scores = self._matrix @ query_vec  # shape: (N,)

        # 2. 应用加权
        final_scores = raw_scores * self._boost_factors

        # 3. Top-K
        top_indices = np.argsort(final_scores)[::-1][:limit]

        results = []
        for idx in top_indices:
            results.append({
                'article_id': int(self._article_ids[idx]),
                'score': float(final_scores[idx]),
                'raw_score': float(raw_scores[idx]) # Debug info
            })

        return results

    def reload(self):
        """强制重新加载"""
        self._loaded = False
        self._load()



# ========== 全局单例 ==========
_index: Optional[VectorIndex] = None


def get_vector_index(db_path: str = 'legal_database.db') -> VectorIndex:
    """获取全局 VectorIndex 单例"""
    global _index
    if _index is None:
        _index = VectorIndex(db_path)
    return _index


# ========== 测试 ==========
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    idx = VectorIndex()
    results = idx.search("股权转让", limit=5)
    print(f"\n搜索 '股权转让', Top-5:")
    for r in results:
        print(f"  article_id={r['article_id']}, score={r['score']:.4f}")
