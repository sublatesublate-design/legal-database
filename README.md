# 国家法律法规数据库 - 智能辅助系统 (Legal Database Hub)

本项目是一个专门为法律专业人士（律师、法务、法学生）开发的高性能、自动化的国家法律法规本地化与智能问答辅助系统。

系统集成了自动化法规下载、结构化存储、以及专为 AI 助手设计的高性能 MCP (Model Context Protocol) 接口，让您的 AI 能够毫秒级检索和引用最准确、最新的中国法律条文。

---

## 🌟 核心引擎与特色

### 1. 自动化数据获取

- **官方源**：自动从国家法律法规数据库 (`flk.npc.gov.cn`) 等官方渠道批量下载 Word/PDF 格式的法律文件。
- **全状态追踪**：支持按“有效”、“已废止”、“尚未生效”等状态建立索引，避免 AI 引用失效法条。

### 2. 结构化解析入库

- **智能拆条机**：内置状态机驱动的解析算法，自动识别复杂的“编-分编-章-节-条”的层级树，将长文档精准拆分为独立的法律条文。
- **SQLite FTS5 + Trigram 检索引擎**：提供工业级的毫秒级全文检索响应速度，支持同义词扩展与概念搜索。

### 3. AI 友好 (MCP 赋能)

- **开箱即用的 MCP Server**：直接为 Claude (或兼容的大模型) 暴露高速的本地法条检索能力。
- **高性能缓存机制**：内置数据库连接池和多级 LRU 缓存，彻底解决频繁调用带来的性能瓶颈。
- **别名识别系统**：AI 找“民法典”，系统自动路由至“中华人民共和国民法典”全文，极大节省 token 损耗并减少对话轮数。

### 4. 可视化操作台 (GUI)

- 内置 **Streamlit** 开发的 Web 看板，提供“零代码”的一键库查新、一键增量同步、一键全库修复操作。

---

## 🚀 快速上手 (How to Use)

### 第一步：环境准备

本项目依赖 Python 3.9+。请确保您的机器已安装 Python 以及 Git。

```bash
# 1. 克隆项目到本地
git clone https://github.com/sublatesublate-design/legal-database.git
cd legal-database

# 2. 安装全部依赖
pip install -r requirements.txt
```

> **注意 (爬虫依赖)**：系统使用 Selenium 进行自动化下载，首次运行时需要系统内存在 Chrome 浏览器及对应版本的 `chromedriver`。

### 第二步：数据库初始化与同步

您可以通过可视化界面或命令行进行数据的抓取与初始化。

#### 方法 A：使用可视化管理面板 (推荐)

最简单且直观的方式是启动可视化管理面板：

```bash
streamlit run app.py
```

1. 浏览器会自动打开管理界面。
2. 在侧边栏选择您关注的各类法律分类（如“法律”、“行政法规”）。
3. 前往 **"📥 批量同步"** 标签页，依次点击 **"下载新文件"** 和 **"处理与入库"**，系统将会自动化建表并将数据解析为结构化数据。

#### 方法 B：使用命令行自动化脚本

如果您更喜欢命令行（或针对服务器部署）：

```bash
# 1. 下载最新有效的法律文件
python batch_downloader.py --category 法律 --status 有效

# 2. 将 downloaded 的 docx 文档解析压缩至 SQLite 数据库
python process_downloads.py
```

### 第三步：配置 AI 工具 (MCP Setup)

当数据库 `legal_database.db` 生成完毕后，您就可以让 AI 助理接入这个法庭级大脑了。

以目前支持 MCP 协议的工具 (如 **Cursor, Claude Desktop, 或 Antigravity**) 为例。请找到对应的 MCP 配置文件 (比如 `mcp_settings.json` 或 `claude_desktop_config.json`)，将以下 JSON 配置追加进去：

```json
{
  "mcpServers": {
    "legal-db": {
      "command": "python",
      "args": ["/[您的电脑/绝对路径]/legal-database/mcp_server.py"],
      "env": {
        "PYTHONPATH": "/[您的电脑/绝对路径]/legal-database"
      }
    }
  }
}
```

**千万注意**：修改上方的 `/[您的电脑/绝对路径]` 为你 clone 本项目的实际目录路径！！！

配置保存并**重载/重启 AI 助手**后，您就可以直接在聊天框告诉 AI：“帮我查一下劳动法关于竞业限制是怎么规定的？”，AI 会自动调用您的本地极速法网给出标准结论！

---

## 🛠 MCP 接口参考

配置成功后，您的 AI 将会获取以下超能力工具：

1. `search_laws(query, category, status)`: （升级版函数）智能概念检索和全文高亮搜索。
2. `get_article(law_title, article_number)`: 直指痛点，精准拿取比如“公司法第七十一条”的原文。
3. `get_law_structure(law_title)`: 获取诸如《民法典》这样庞大法律的长目录结构树 (TOC)。
4. `check_law_validity(law_title)`: 快速判断一部法律当前到底是“有效”还是“已废止”。
5. `batch_verify_citations(document_text)`: 批量校验您写好的法律意见书中的引用，核对法条是否有错别字或已失效。

---

## 📅 日常维护

法律条款日新月异。当您看到新闻有新规出台时：

1. 启动 `streamlit run app.py` -> 点击 **查新与更新**。
2. 或者在命令行直接运行 `python update.py` 触发一键增量查新、下载和全库目录索引重建。

---

## 📄 许可证 (License)

本项目遵循 [MIT License](LICENSE) 开源协议。

**⚠️ 免责声明**：本项目仅作为技术辅助工具，检索到的法条信息仅供学习和参考。正式的执业法律文书出具请务必依赖政府公开文件的最新源文本。
