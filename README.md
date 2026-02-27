# 国家法律法规数据库 - 智能辅助系统

本系统集成了自动化法规下载、结构化存储及 MCP 智能接入功能，旨在为法律专业人士（如律师、法务）提供精准的法律意见书编写辅助。

## 核心功能

1. **自动化下载**: 适配 `flk.npc.gov.cn` 官方库，支持“法律”、“行政法规”、“司法解释”等全分类批量下载。
2. **状态感知**: 支持按“有效”、“已废止”、“尚未生效”等状态过滤法条，确保引用时效性。
3. **本地数据库**: 将数千份 DOCX 文档转化为结构化 SQLite 数据库，支持全文秒级检索。
4. **MCP Server**: 允许 AI 助手（如 Antigravity）直接调用本地库。

## 安装与配置

### 1. 运行下载器

```powershell
python batch_downloader.py --category 法律 --status 有效
```

### 2. 同步数据库

```powershell
python process_downloads.py
```

### 3. 配置 MCP Server

将以下配置添加到您的 MCP 配置文件中。请注意将 `[YOUR_PATH]` 替换为本项目在您本地的实际绝对路径：

```json
{
  "mcpServers": {
    "legal-db": {
      "command": "python",
      "args": ["/[YOUR_PATH]/mcp_server.py"],
      "env": {
        "PYTHONPATH": "/[YOUR_PATH]"
      }
    }
  }
}
```

## MCP 提供工具说明

- `search_laws(query)`: 模糊搜索相关法规标题。
- `get_article(law_title, article_number)`: 获取特定条文原文（如“公司法”、“第二十一条”）。
- `verify_law_citation(law_title, article_number, content)`: 校验引用的法条内容是否与标准原文一致。

## 日常维护与增量更新

为了保证您的法库始终处于最新状态，建议您执行以下简单的维护流程：

### 1. 增量下载 (按需)

当您在新闻中看到有新法律颁布或修订时，运行下载器：

```powershell
# 仅下载最新的、感兴趣的分类
python batch_downloader.py --category 法律 --status 有效 --max-pages 1
```

*提示：程序会自动跳过已存在的文件，只拉取最新的内容。*

### 2. 一键同步与优化

下载新文件后，运行我为您准备的一键更新脚本：

```powershell
python update.py
```

**此脚本会自动执行：**

- **解压与入库**：将 `downloads` 目录下的新 Word 文档同步到数据库。
- **状态同步**：更新已有法规的最新效力状态。
- **搜索优化**：重建全文检索引索，确保搜索速度依然极速。

### 3. 在 Antigravity 中生效

同步完成后，只需在 Antigravity 的 **Manage MCP Servers** 界面点击 **Refresh (刷新)** 按钮即可。

---

## 许可证 (License)

本项目采用 [MIT License](LICENSE) 开源协议。

---

**⚠️ 注意事项：**

- 如果您发现某个法条失效了（例如变为了“已废止”），请重新下载该分类并指定 `--status 已废止`，然后运行 `update.py`，数据库会自动更新对应的状态标记。
