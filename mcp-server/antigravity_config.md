# 如何在 Antigravity 中配置法律数据库 MCP 服务器

## 配置步骤

### 1. 找到 Antigravity 的 MCP 配置文件

Antigravity 的 MCP 服务器配置通常位于：

- Windows: `%APPDATA%\Antigravity\mcp-config.json`
- 或者在 Antigravity 设置中查找 "MCP Servers" 或 "Extensions" 选项

### 2. 添加法律数据库服务器配置

在 MCP 配置文件中添加以下配置：

```json
{
  "mcpServers": {
    "legal-database": {
      "command": "python",
      "args": [
        "C:\\Users\\24812\\Desktop\\legal-database\\mcp-server\\server.py"
      ],
      "env": {}
    }
  }
}
```

**重要**: 请将路径替换为您的实际项目路径。

### 3. 重启 Antigravity

配置添加后，需要重启 Antigravity 使配置生效。

### 4. 验证连接

重启后，您可以测试连接：

**测试命令：**
> "请查询公司法第三条"

如果我能成功返回法条内容，说明 MCP 服务器配置成功！

## 可用功能

配置成功后，我可以：

1. **搜索法律**: "搜索民法典"
2. **获取法律全文**: "获取公司法全文"
3. **查询特定法条**: "查询公司法第三条"
4. **搜索法条内容**: "搜索所有关于股权转让的法条"
5. **获取所有法条**: "列出民法典所有法条"

## 常见问题

### Q: 配置后没有反应？

A:

1. 确认 Python 已安装并在 PATH 中
2. 确认路径正确（使用绝对路径）
3. 检查 Antigravity 日志是否有错误信息
4. 尝试重启 Antigravity

### Q: 提示找不到模块？

A:

1. 确认已安装依赖：`pip install -r requirements.txt`
2. 确认 Python 虚拟环境配置正确

### Q: 数据库为空？

A:
数据库需要先运行爬虫采集数据：

```powershell
cd legal-database
python scripts/run_crawler.py
```

## 手动测试

如果想在配置前测试 MCP 服务器：

```powershell
cd legal-database\mcp-server
python server.py
```

服务器应该启动并等待输入。按 Ctrl+C 退出。
