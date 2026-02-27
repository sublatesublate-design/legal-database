# 法律数据库系统 - macOS 部署指南

## 📦 准备工作 (在您的Windows电脑上)

### 1. 打包需要传输的文件

创建一个文件夹,包含以下文件:

```
legal-database/
├── legal_database.db          (55MB数据库文件 - 最重要!)
├── mcp_server.py              (MCP服务器)
├── database/
│   ├── schema.sql
│   └── schema_aliases.sql
├── requirements.txt           (Python依赖)
└── README.md
```

**关键文件**:

- `legal_database.db` - 包含2333部法律的完整数据库
- `mcp_server.py` - MCP服务器代码
- `requirements.txt` - Python依赖列表

### 2. 传输方式

选择以下任一方式传输到MacBook:

**方式1: 云盘** (推荐)

- 压缩整个文件夹为 `legal-database.zip`
- 上传到百度云盘/阿里云盘/OneDrive
- 在MacBook上下载

**方式2: U盘**

- 直接复制文件夹到U盘
- 在MacBook上复制到本地

**方式3: 网络传输**

- 使用AirDrop (如果Windows支持)
- 或者通过局域网共享文件夹

---

## 🍎 macOS 上的安装步骤

### 步骤1: 安装Python

检查Python版本:

```bash
python3 --version
```

如果没有Python 3.8+,从官网安装:

- 访问 <https://www.python.org/downloads/>
- 下载 macOS 安装包
- 或使用Homebrew: `brew install python@3.11`

### 步骤2: 解压并放置文件

```bash
# 假设文件在Downloads文件夹
cd ~/Downloads
unzip legal-database.zip

# 移动到合适的位置
mkdir -p ~/Documents/legal-database
mv legal-database/* ~/Documents/legal-database/
cd ~/Documents/legal-database
```

### 步骤3: 安装Python依赖

```bash
# 创建虚拟环境(推荐)
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install mcp fastmcp sqlite3
# 或者如果有requirements.txt:
pip install -r requirements.txt
```

### 步骤4: 验证数据库

```bash
# 检查数据库文件是否存在
ls -lh legal_database.db

# 测试数据库连接
python3 -c "import sqlite3; conn = sqlite3.connect('legal_database.db'); c = conn.cursor(); c.execute('SELECT COUNT(*) FROM laws'); print(f'法律总数: {c.fetchone()[0]}'); conn.close()"
```

预期输出: `法律总数: 2333`

### 步骤5: 测试MCP服务器

```bash
# 测试服务器启动
python3 mcp_server.py --help
```

### 步骤6: 配置Antigravity (Claude Desktop / Cursor)

macOS的MCP配置文件位置:

**对于Claude Desktop**:

```bash
~/Library/Application Support/Claude/claude_desktop_config.json
```

**对于Cursor/其他IDE**:
查找类似路径或IDE的设置文件。

**配置内容**:

```json
{
  "mcpServers": {
    "legal-db": {
      "command": "python3",
      "args": [
        "/Users/你的用户名/Documents/legal-database/mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "/Users/你的用户名/Documents/legal-database"
      }
    }
  }
}
```

**⚠️ 重要**:

- 将 `/Users/你的用户名` 替换为实际的用户名
- 可以用 `whoami` 命令查看用户名
- 或者用 `pwd` 命令查看当前路径

### 步骤7: 获取绝对路径

在legal-database目录下执行:

```bash
pwd
# 输出类似: /Users/zhangsan/Documents/legal-database
```

用这个路径替换配置文件中的路径。

### 步骤8: 重启Antigravity

1. 完全退出Antigravity/Claude Desktop
2. 重新打开应用
3. MCP服务器会自动启动

### 步骤9: 验证安装

在Antigravity中测试:

```
帮我查询《公司法》第一条的内容
```

预期结果: 应该在1次查询内返回正确的法条内容。

---

## 🔧 常见问题排查

### 问题1: Python命令不存在

**解决**:

```bash
# 尝试使用python3
python3 --version

# 如果还是不行,安装Python
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python@3.11
```

### 问题2: 找不到数据库文件

**检查**:

```bash
# 确认在正确的目录
cd ~/Documents/legal-database
ls -la legal_database.db
```

如果文件不存在,重新从Windows复制。

### 问题3: MCP服务器无法启动

**检查日志**:

```bash
# 手动启动查看错误
python3 mcp_server.py
```

常见错误:

- `ModuleNotFoundError: No module named 'mcp'` → 运行 `pip install mcp fastmcp`
- `No such file or directory: legal_database.db` → 检查路径是否正确

### 问题4: 权限问题

```bash
# 给予执行权限
chmod +x mcp_server.py

# 确保数据库文件可读
chmod 644 legal_database.db
```

### 问题5: Antigravity找不到MCP服务器

**检查**:

1. 配置文件路径是否正确
2. JSON格式是否有效 (可以用在线JSON验证器)
3. 绝对路径是否使用了正确的用户名
4. 是否重启了Antigravity

---

## 📝 快速配置脚本 (macOS)

创建 `setup_macos.sh`:

```bash
#!/bin/bash

echo "🍎 法律数据库 macOS 安装脚本"
echo "======================================"

# 获取当前路径
INSTALL_DIR="$PWD"
echo "安装目录: $INSTALL_DIR"

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装,请先安装Python"
    exit 1
fi

echo "✅ Python版本: $(python3 --version)"

# 安装依赖
echo ""
echo "📦 安装Python依赖..."
python3 -m pip install --upgrade pip
python3 -m pip install mcp fastmcp

# 检查数据库
if [ ! -f "legal_database.db" ]; then
    echo "❌ 数据库文件不存在!"
    exit 1
fi

echo "✅ 数据库大小: $(du -h legal_database.db | cut -f1)"

# 测试数据库
echo ""
echo "🧪 测试数据库..."
python3 -c "import sqlite3; conn = sqlite3.connect('legal_database.db'); c = conn.cursor(); c.execute('SELECT COUNT(*) FROM laws'); print(f'✅ 法律总数: {c.fetchone()[0]}'); conn.close()"

# 生成MCP配置
echo ""
echo "📝 MCP配置信息:"
echo "{"
echo "  \"mcpServers\": {"
echo "    \"legal-db\": {"
echo "      \"command\": \"python3\","
echo "      \"args\": ["
echo "        \"$INSTALL_DIR/mcp_server.py\""
echo "      ],"
echo "      \"env\": {"
echo "        \"PYTHONPATH\": \"$INSTALL_DIR\""
echo "      }"
echo "    }"
echo "  }"
echo "}"

echo ""
echo "======================================"
echo "✅ 安装完成!"
echo "请将上面的配置复制到Antigravity的MCP配置文件中"
echo "macOS配置文件位置: ~/Library/Application Support/Claude/claude_desktop_config.json"
echo "======================================"
```

使用方式:

```bash
cd ~/Documents/legal-database
chmod +x setup_macos.sh
./setup_macos.sh
```

---

## 🎯 完整检查清单

部署前:

- [ ] 从Windows复制所有必要文件
- [ ] legal_database.db 文件大小约55MB
- [ ] mcp_server.py 文件存在

macOS上:

- [ ] Python 3.8+ 已安装
- [ ] 依赖包已安装 (mcp, fastmcp)
- [ ] 数据库测试通过 (显示2333部法律)
- [ ] MCP配置文件已更新
- [ ] 绝对路径正确(没有中文路径)
- [ ] Antigravity已重启
- [ ] 测试查询成功

---

## 💡 专业建议

1. **使用绝对路径**: macOS上务必使用完整的绝对路径,如 `/Users/username/Documents/legal-database/mcp_server.py`

2. **避免中文路径**: 路径中不要包含中文字符,可能导致编码问题

3. **定期备份**: 数据库文件很重要,建议定期备份到云盘

4. **版本同步**: 如果Windows上更新了数据库,记得同步到MacBook

5. **网络位置**: 建议放在本地磁盘,不要放在网络驱动器或iCloud Drive

6. **安全性**: 数据库文件较大,传输时使用加密方式(如压缩加密)

---

## 📞 需要帮助?

如果遇到问题:

1. 查看本文档的"常见问题排查"部分
2. 运行测试脚本检查每个步骤
3. 检查Antigravity的日志输出
