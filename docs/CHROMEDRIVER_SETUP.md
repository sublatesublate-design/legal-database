# ChromeDriver 安装指南

## 问题说明

如果您在运行 `batch_downloader.py` 时遇到以下错误：
```
Could not reach host. Are you offline?
Failed to resolve 'storage.googleapis.com'
```

这是因为 `webdriver-manager` 无法从 Google 服务器下载 ChromeDriver。在中国大陆访问 Google 服务可能会受到限制。

## 解决方案

### 方案1：手动安装 ChromeDriver（推荐）

#### 步骤1：检查 Chrome 浏览器版本

1. 打开 Chrome 浏览器
2. 点击右上角 ⋮ → 帮助 → 关于 Google Chrome
3. 记下版本号，例如：`143.0.7499.192`

#### 步骤2：下载对应版本的 ChromeDriver

**方式A：官方镜像（推荐）**

访问 Chrome for Testing 下载页面：
```
https://googlechromelabs.github.io/chrome-for-testing/
```

**方式B：国内镜像（更快）**

访问淘宝镜像：
```
https://registry.npmmirror.com/binary.html?path=chromedriver/
```

或者使用以下直接下载链接（替换版本号）：
```
https://registry.npmmirror.com/-/binary/chromedriver/143.0.7499.192/chromedriver_win32.zip
```

#### 步骤3：解压并配置

1. 下载 `chromedriver_win32.zip`
2. 解压得到 `chromedriver.exe`
3. 将 `chromedriver.exe` 放到以下任一位置：

**选项A：添加到系统 PATH（推荐）**

1. 将 `chromedriver.exe` 复制到 `C:\Windows\System32\`
2. 或者创建自定义目录，例如 `C:\chromedriver\`，然后添加到 PATH：
   - 右键"此电脑" → 属性 → 高级系统设置
   - 环境变量 → 系统变量 → Path → 新建
   - 添加 `C:\chromedriver\`

**选项B：放在项目目录**

将 `chromedriver.exe` 放在 `legal-database` 项目根目录下。

#### 步骤4：验证安装

打开 PowerShell 或命令提示符，运行：
```powershell
chromedriver --version
```

如果显示版本信息，说明安装成功。

---

### 方案2：配置代理（如果有代理服务器）

如果您有可用的代理服务器，可以配置让 `webdriver-manager` 通过代理下载。

编辑 `batch_downloader.py`，在导入部分添加：

```python
import os

# 配置代理
os.environ['HTTP_PROXY'] = 'http://your-proxy-server:port'
os.environ['HTTPS_PROXY'] = 'http://your-proxy-server:port'
```

---

### 方案3：使用已安装的 Chrome（Edge WebDriver）

如果您使用 Microsoft Edge 浏览器，可以使用 Edge WebDriver 作为替代：

1. 安装 Edge WebDriver：
```powershell
pip install msedge-selenium-tools
```

2. 修改代码使用 Edge（需要单独修改）

---

## 运行测试

安装完成后，运行测试命令：

```powershell
# 测试单个分类（下载1页）
python batch_downloader.py --category 法律 --max-pages 1
```

如果浏览器成功启动并开始下载，说明配置成功！

---

## 常见问题

### Q1: ChromeDriver 版本必须完全匹配吗？

**A**: 主版本号必须匹配（如 143），但小版本号可以有细微差异。建议尽量使用完全匹配的版本。

### Q2: 如何查找旧版本的 ChromeDriver？

**A**: 访问淘宝镜像查看所有可用版本：
```
https://registry.npmmirror.com/binary.html?path=chromedriver/
```

### Q3: 仍然无法工作怎么办？

**A**: 检查以下几点：
1. Chrome 浏览器是否已更新
2. ChromeDriver 版本是否匹配
3. 防火墙是否阻止了 Chrome
4. 尝试以管理员身份运行脚本

---

## 快速链接

- **Chrome 版本查询**: chrome://version/
- **ChromeDriver 官方**: https://chromedriver.chromium.org/
- **Chrome for Testing**: https://googlechromelabs.github.io/chrome-for-testing/
- **淘宝镜像**: https://registry.npmmirror.com/binary.html?path=chromedriver/

---

## 下一步

安装完成后，参考 [README.md](../README.md) 继续使用批量下载工具。
