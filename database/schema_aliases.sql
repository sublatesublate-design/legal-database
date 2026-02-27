-- 法律简称/别名映射表
-- 用于快速解析用户输入的常用法律简称

CREATE TABLE IF NOT EXISTS law_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alias TEXT NOT NULL UNIQUE,           -- 简称/俗称/关键词
    law_id INTEGER NOT NULL,              -- 外键关联laws表
    alias_type TEXT DEFAULT 'common',     -- 类型: common(常用简称)/abbreviation(缩写)/keyword(关键词)
    confidence REAL DEFAULT 1.0,          -- 匹配置信度(0-1)，1.0表示精确匹配
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (law_id) REFERENCES laws(id) ON DELETE CASCADE
);

-- 创建索引以提升查询性能
CREATE INDEX IF NOT EXISTS idx_aliases_text ON law_aliases(alias);
CREATE INDEX IF NOT EXISTS idx_aliases_law_id ON law_aliases(law_id);
CREATE INDEX IF NOT EXISTS idx_aliases_type ON law_aliases(alias_type);

-- 示例数据（可选）
-- INSERT INTO law_aliases (alias, law_id, alias_type, confidence) VALUES 
--     ('建设工程司法解释', 123, 'common', 1.0),
--     ('民间借贷司法解释', 456, 'common', 1.0);
