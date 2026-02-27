#!/bin/bash

echo "🍎 法律数据库 macOS 安装脚本"
echo "======================================"

# 获取当前路径
INSTALL_DIR="$PWD"
echo "安装目录: $INSTALL_DIR"

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    echo "请运行: brew install python@3.11"
    exit 1
fi

echo "✅ Python版本: $(python3 --version)"

# 安装依赖
echo ""
echo "📦 安装Python依赖..."
python3 -m pip install --upgrade pip --quiet
python3 -m pip install mcp fastmcp --quiet

if [ $? -eq 0 ]; then
    echo "✅ 依赖安装成功"
else
    echo "❌ 依赖安装失败"
    exit 1
fi

# 检查数据库
if [ ! -f "legal_database.db" ]; then
    echo "❌ 数据库文件不存在!"
    echo "请确保 legal_database.db 在当前目录"
    exit 1
fi

echo "✅ 数据库大小: $(du -h legal_database.db | cut -f1)"

# 测试数据库
echo ""
echo "🧪 测试数据库连接..."
DB_TEST=$(python3 -c "import sqlite3; conn = sqlite3.connect('legal_database.db'); c = conn.cursor(); c.execute('SELECT COUNT(*) FROM laws'); count = c.fetchone()[0]; conn.close(); print(count)" 2>&1)

if [ $? -eq 0 ]; then
    echo "✅ 法律总数: $DB_TEST 部"
else
    echo "❌ 数据库测试失败"
    exit 1
fi

# 检查别名表
echo "🧪 测试别名系统..."
ALIAS_TEST=$(python3 -c "import sqlite3; conn = sqlite3.connect('legal_database.db'); c = conn.cursor(); c.execute('SELECT COUNT(*) FROM law_aliases'); count = c.fetchone()[0]; conn.close(); print(count)" 2>&1)

if [ $? -eq 0 ]; then
    echo "✅ 法律别名: $ALIAS_TEST 个"
else
    echo "⚠️  别名表可能不存在"
fi

# 测试MCP服务器文件
if [ ! -f "mcp_server.py" ]; then
    echo "❌ mcp_server.py 文件不存在!"
    exit 1
fi

echo "✅ MCP服务器文件存在"

# 生成MCP配置
echo ""
echo "======================================"
echo "📝 请将以下配置添加到Antigravity:"
echo ""
echo "配置文件位置:"
echo "~/Library/Application Support/Claude/claude_desktop_config.json"
echo ""
echo "配置内容:"
echo "======================================"
cat <<EOF
{
  "mcpServers": {
    "legal-db": {
      "command": "python3",
      "args": [
        "$INSTALL_DIR/mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "$INSTALL_DIR"
      }
    }
  }
}
EOF
echo "======================================"

echo ""
echo "✅ 安装验证完成!"
echo ""
echo "下一步:"
echo "1. 复制上面的配置到 Antigravity MCP 配置文件"
echo "2. 重启 Antigravity"
echo "3. 测试查询: '帮我查询《公司法》第一条'"
echo ""
echo "🎉 祝使用愉快!"
