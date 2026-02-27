-- 法律法规数据库 Schema
-- SQLite 数据库结构定义

-- 1. 法律法规主表
CREATE TABLE IF NOT EXISTS laws (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,                    -- 法律名称
    short_title TEXT,                       -- 简称
    category TEXT NOT NULL,                 -- 类别：法律/行政法规/司法解释/部门规章
    issuing_authority TEXT,                 -- 发布机关
    document_number TEXT,                   -- 文号
    publish_date TEXT,                      -- 发布日期 (YYYY-MM-DD)
    effective_date TEXT,                    -- 生效日期
    expiry_date TEXT,                       -- 失效日期（如有）
    status TEXT NOT NULL DEFAULT 'active',  -- 状态：active/repealed/amended
    source_url TEXT,                        -- 原文链接
    content TEXT,                           -- 全文 (Note: was full_text in old schema, but DB uses content)
    created_at TEXT NOT NULL,              -- 入库时间
    updated_at TEXT NOT NULL,              -- 更新时间
    UNIQUE(title, publish_date)            -- 防止重复
);

-- 2. 法条内容表 (Note: Missing in current DB, but keeping definition for reference/future)
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    law_id INTEGER NOT NULL,               -- 外键关联laws表
    chapter TEXT,                          -- 章
    section TEXT,                          -- 节
    article_number TEXT NOT NULL,          -- 条文编号（如"第三条"）
    article_index INTEGER,                 -- 条文序号（数字，便于排序）
    content TEXT NOT NULL,                 -- 条文内容
    FOREIGN KEY (law_id) REFERENCES laws(id) ON DELETE CASCADE
);

-- 3. 修订历史表
CREATE TABLE IF NOT EXISTS revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    law_id INTEGER NOT NULL,               -- 关联的法律
    revision_date TEXT NOT NULL,           -- 修订日期
    revision_type TEXT,                    -- 修订类型：amendment/interpretation
    revision_note TEXT,                    -- 修订说明
    previous_version_id INTEGER,           -- 前一版本ID
    FOREIGN KEY (law_id) REFERENCES laws(id) ON DELETE CASCADE
);

-- 4. 创建索引以提升查询性能
CREATE INDEX IF NOT EXISTS idx_laws_category ON laws(category);
CREATE INDEX IF NOT EXISTS idx_laws_status ON laws(status);
CREATE INDEX IF NOT EXISTS idx_laws_publish_date ON laws(publish_date);
CREATE INDEX IF NOT EXISTS idx_articles_law_id ON articles(law_id);
CREATE INDEX IF NOT EXISTS idx_articles_index ON articles(article_index);
CREATE INDEX IF NOT EXISTS idx_revisions_law_id ON revisions(law_id);

-- 5. 全文搜索虚拟表 (FTS5) - Optimized for Chinese with Trigram
CREATE VIRTUAL TABLE IF NOT EXISTS laws_fts USING fts5(
    title,
    content,
    content='laws',
    content_rowid='id',
    tokenize='trigram'
);

-- FTS5 触发器
CREATE TRIGGER IF NOT EXISTS laws_fts_insert AFTER INSERT ON laws BEGIN
    INSERT INTO laws_fts(rowid, title, content)
    VALUES (new.id, new.title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS laws_fts_update AFTER UPDATE ON laws BEGIN
    UPDATE laws_fts SET title = new.title, content = new.content
    WHERE rowid = new.id;
END;

CREATE TRIGGER IF NOT EXISTS laws_fts_delete AFTER DELETE ON laws BEGIN
    DELETE FROM laws_fts WHERE rowid = old.id;
END;

-- 6. 法条全文搜索表 - (Skipping creation if articles table missing, but definition kept)
-- CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts ...

-- 7. 法律概念同义词表
CREATE TABLE IF NOT EXISTS concept_synonyms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT NOT NULL,                     -- 用户可能搜索的词（如"债权人撤销权"）
    canonical_term TEXT NOT NULL,           -- 标准概念名称（如"撤销权"）
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_concept_synonyms_term ON concept_synonyms(term);

-- 8. 元数据表
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT
);
