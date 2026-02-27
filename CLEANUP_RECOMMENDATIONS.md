# 文件清理建议

## 📌 核心文件 - 必须保留

### 主程序

- `mcp_server.py` - MCP服务器主程序（最新版）
- `config.py` - 配置文件
- `requirements.txt` - Python依赖
- `legal_database.db` - 数据库文件
- `legal_database.db-shm` / `legal_database.db-wal` - SQLite工作文件

### 数据处理

- `batch_downloader.py` - 批量下载法律文档
- `process_downloads.py` - 处理下载的文档
- `populate_common_aliases.py` - 填充法律别名数据
- `fix_alias_mappings.py` - 修复别名映射

### 文档

- `README.md` - 项目说明
- `DEPLOYMENT_CHECKLIST.md` - 部署检查清单
- `MACOS_DEPLOYMENT.md` - macOS部署文档
- `ALIAS_ACTIVATION.md` - 别名激活说明
- `.gitignore` - Git忽略配置

### 部署相关

- `create_deploy_package.py` - 创建部署包
- `setup_macos.sh` - macOS安装脚本
- `chromedriver.exe` - Chrome驱动（用于爬虫，17MB）

---

## 🗑️ 建议删除 - 临时文件和测试文件

### 调试/分析脚本（刚才创建的）

- `analyze_evolution_potential.py` - 分析法条演变潜力（已取消方案）
- `analyze_db_simple.py` - 简单数据库分析
- `check_abolished_laws.py` - 检查废止法律
- `deep_db_check.py` - 深度数据库检查
- `analyze_database_content.py` - 分析数据库内容

### 测试文件

- `test_alias_system.py` - 测试别名系统
- `test_article_search.py` - 测试法条搜索
- `test_company_law_fix.py` - 测试公司法修复
- `test_correct_search.py` - 测试正确搜索
- `test_daiwei_search.py` - 测试代位搜索
- `test_fts5_improvement.py` - 测试FTS5改进
- `test_improved_search.py` - 测试改进搜索
- `test_query_speed.py` - 测试查询速度
- `test_search_article_content.py` - 测试法条内容搜索
- `test_topic_search.py` - 测试主题搜索

### 调试文件

- `debug_article.py` - 调试法条
- `debug_query.py` - 调试查询
- `debug_query_full.py` - 调试完整查询
- `debug_search.py` - 调试搜索
- `diagnose_company_law.py` - 诊断公司法
- `diagnose_search.py` - 诊断搜索

### 检查工具

- `check_db_tables.py` - 检查数据库表
- `check_fts5.py` - 检查FTS5
- `check_law_validity_tool.py` - 检查法律有效性工具
- `inspect_workspace_db.py` - 检查工作区数据库
- `query_mcp_config.py` - 查询MCP配置
- `find_mcp_deep.py` - 深度查找MCP
- `find_mcp_servers_key.py` - 查找MCP服务器密钥
- `find_old_path.py` - 查找旧路径

### 临时输出文件

- `abolished_laws_report.txt` - 废止法律报告（100KB）
- `database_analysis_result.txt` - 数据库分析结果
- `result_display.txt` - 结果显示
- `article_check.txt` - 法条检查
- `full_results.txt` - 完整结果
- `batch_download.log` - 批量下载日志（114KB）

### 优化相关（可能已合并到主程序）

- `mcp_server_optimized.py` - 优化版MCP服务器（与mcp_server.py重复？）
- `optimize_db.py` - 优化数据库
- `optimize_search_performance.py` - 优化搜索性能
- `apply_optimization.py` - 应用优化
- `analyze_performance.py` - 分析性能

### 其他工具

- `search_article_content_tool.py` - 搜索法条内容工具
- `search_evidence_rules.py` - 搜索证据规则
- `create_topic_mapping.py` - 创建主题映射
- `update.py` - 更新
- `update_checker.py` - 更新检查器
- `download_chromedriver.py` - 下载Chrome驱动
- `app.py` - 应用（Web界面？）

---

## ❓ 需要确认

### 可能有用的

- `app.py` - 如果这是Web界面，可能有用
- `crawler/` 目录 - 如果还需要爬取数据
- `update.py` / `update_checker.py` - 如果有版本更新需求

### 部署包

- `legal-database-deploy/` - 是否是旧的部署版本？

---

## 📊 总结

- **核心文件**: 约15个
- **建议删除**: 约50个文件
- **可节省空间**: 约18MB（主要是chromedriver.exe和日志文件）

执行清理后，项目将更加整洁，只保留必要的核心功能文件。
