# 法律数据库系统部署清单

## 📦 需要传输的文件

### 必需文件 (必须复制)

- [ ] `legal_database.db` (55MB) - 数据库文件
- [ ] `mcp_server.py` - MCP服务器
- [ ] `setup_macos.sh` - macOS安装脚本

### 可选文件 (建议复制)

- [ ] `README.md` - 说明文档
- [ ] `MACOS_DEPLOYMENT.md` - macOS部署指南
- [ ] `database/schema.sql` - 数据库结构
- [ ] `database/schema_aliases.sql` - 别名表结构

### 维护工具 (可选)

- [ ] `populate_common_aliases.py` - 别名填充工具
- [ ] `fix_alias_mappings.py` - 别名修复工具
- [ ] `test_alias_system.py` - 测试脚本

---

## 📝 部署步骤

### Windows端 (准备)

1. [ ] 创建文件夹 `legal-database-deploy`
2. [ ] 复制上述必需文件到文件夹
3. [ ] 压缩为 `legal-database-deploy.zip`
4. [ ] 传输到MacBook (云盘/U盘/网络)

### macOS端 (安装)

1. [ ] 解压文件到 `~/Documents/legal-database`
2. [ ] 打开终端,进入该目录
3. [ ] 运行 `chmod +x setup_macos.sh`
4. [ ] 运行 `./setup_macos.sh`
5. [ ] 复制输出的配置到Antigravity
6. [ ] 重启Antigravity
7. [ ] 测试查询功能

---

## ✅ 验证清单

### 安装验证

- [ ] Python版本 3.8+
- [ ] 数据库显示 2333 部法律
- [ ] 别名表包含 70+ 别名
- [ ] MCP配置文件已更新
- [ ] Antigravity已重启

### 功能验证

- [ ] 查询"公司法"第一条 - 成功
- [ ] 查询"建设工程司法解释"第二十一条 - 成功
- [ ] 查询"民法典"第一条 - 成功
- [ ] 搜索响应时间快速 (1次查询)

---

## 📞 联系方式

如有问题,请联系部署人员或查看部署文档。
