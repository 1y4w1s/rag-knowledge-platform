# MCP 连接排障手册

> Windows 环境常见 MCP 连接问题及解决方案。

---

## 1. chrome-mcp（hangwin/mcp-chrome）

### 症状

```
chrome-mcp: Failed to connect to MCP server
chrome-mcp: http 400: {"error":"Invalid MCP request or session."}
chrome-mcp: Screenshot error: Failed to capture tab: image readback failed
```

### 排查步骤

```powershell
# 1. 检查 bridge 是否安装
npm list -g mcp-chrome-bridge

# 2. 检查 Chrome 扩展是否连接
mcp-chrome-bridge doctor
# 期望输出：Connectivity: GET http://127.0.0.1:12306/ping -> 200

# 3. 检查端口
netstat -ano | Select-String "12306"
```

### 修复

**A. bridge 没在运行**
```powershell
# 杀掉旧进程
$proc = Get-NetTCPConnection -LocalPort 12306 -ErrorAction SilentlyContinue
if ($proc) { Stop-Process -Id $proc.OwningProcess -Force }

# 启动 bridge
cmd.exe /c "start /b mcp-chrome-bridge"
# 或：Start-Process -NoNewWindow cmd.exe "/c start /b mcp-chrome-bridge"
```

**B. 扩展未安装**
1. 打开 `https://github.com/hangwin/mcp-chrome/releases` 下载扩展
2. Chrome → `chrome://extensions/` → 开发者模式 → 加载已解压的扩展
3. 点击扩展图标 → **Connect**

**C. 新对话连接不上（session expired）**
```powershell
# 杀掉旧进程 → 重启 bridge → 重新 install MCP
# 然后在新对话中运行：
install_source --apply --kind mcp --name chrome-mcp --replace \
  --source http://127.0.0.1:12306/mcp --transport http
```

### 注意事项

- 截图功能 `chrome_screenshot` 在某些 Chrome 版本中可能 `image readback failed`，这是扩展的已知问题
- 备选方案：使用 `chrome_read_page` 获取 accessibility tree，其中包含所有元素的精确坐标

---

## 2. LM Studio MCP（lmstudio-local）

### 症状

```
MCP server "lmstudio-local" failed to start: hash MCP executable
"...PythonSoftwareFoundation.Python.3.11_...\python.exe":
The file cannot be accessed by the system.
```

### 根因

Windows 11 的 **App Execution Alias (AEA)** 保护机制：
- 从 Microsoft Store 安装的 Python（`python3`、`python.exe`）实际指向
  `C:\Users\<user>\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_...\python.exe`
- 该路径下的可执行文件**受 Windows 保护，无法被其他进程直接启动**
- `where.exe python3` 能找到，但 `Start-Process` 或 `CreateProcess` 对这个路径会失败

### 排查步骤

```powershell
# 1. 检查 Python 安装位置
where.exe python3
(Get-Command python3).Source

# 2. 检查 LM Studio API 是否在运行
curl.exe http://localhost:1234/v1/models

# 3. 检查 Reasonix 缓存
Get-ChildItem "$env:APPDATA\reasonix\repair\config.toml.last-known-good*"
Select-String -Path "$env:APPDATA\reasonix\repair\config.toml.last-known-good" -Pattern "python.exe"
```

### 修复

**方案一：找非 WindowsApps 的 Python 3.11（推荐）**
```powershell
# 查找所有 python.exe
Get-ChildItem "C:\" -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -notmatch "WindowsApps|Windows\\System" } |
  Select-Object FullName
```

常见候选路径：
| 路径 | 说明 |
|------|------|
| `C:\Users\<user>\.agent-reach-venv\Scripts\python.exe` | Agent Reach 自带 |
| `C:\Users\<user>\.lmstudio\extensions\backends\vendor\...\python.exe` | LM Studio 自带 |
| `C:\Users\<user>\miniconda3\python.exe` | Miniconda |
| `C:\Program Files\Python313\python.exe` | 手动安装 |

找到后，在 Reasonix config.toml 中修改命令路径：
```toml
[[plugins]]
name    = "lmstudio-local"
command = "C:\\Users\\<user>\\.agent-reach-venv\\Scripts\\python.exe"
args    = ["-c", "import sys; sys.path.insert(0, 'D:\\\\LMstudio\\\\lmstudio-local-mcp-server'); from lmstudio_local_mcp.server import main; import asyncio; asyncio.run(main())"]
env     = { LMSTUDIO_ENDPOINT = "http://localhost:1234" }
```

**方案二：直接调用 LM Studio HTTP API（不需要 MCP 插件）**

LM Studio 默认在 `http://localhost:1234` 提供 OpenAI 兼容 API，可以绕过 MCP 直接调用：

```python
import httpx

resp = httpx.post("http://localhost:1234/v1/chat/completions", json={
    "model": "zai-org/glm-4.6v-flash",  # 或任何已加载的模型
    "messages": [{"role": "user", "content": "分析这张图片"}],
    "max_tokens": 1000,
})
```

### 注意事项

- `config.toml` 和 `repair/config.toml.last-known-good` **都需要更新**，否则 Reasonix 会从缓存恢复旧路径
- 如果 `last-known-good` 不可写（sandbox 限制），只能在新会话中生效
- `py -3.11` 也会解析回 WindowsApps 路径，不可用

---

## 3. 通用排查清单

| 症状 | 可能原因 | 解决方案 |
|------|---------|---------|
| MCP 连接失败 | bridge/服务未启动 | 检查端口占用，重启服务 |
| 新对话无法连接 | session 过期 | `install_source --replace` 重连 |
| HTTP 400 Invalid request | bridge 会话冲突 | 重启 bridge 进程 |
| 截图失败 `image readback failed` | Chrome 扩展限制 | 改用 `chrome_read_page` |
| 可执行文件无法访问 | WindowsApp AEA 保护 | 改用非 WindowsApps 的 Python |
| 配置修改不生效 | `last-known-good` 缓存 | 同步更新 repair 目录下的缓存文件 |
| API 超时 | 模型未加载 | 先检查 `GET /v1/models` 确认模型在线 |

---

## 4. 快速诊断脚本

```powershell
# one-liner 检查所有 MCP 依赖
Write-Host "=== chrome-mcp ==="
netstat -ano | Select-String "12306"
try { curl.exe -s http://127.0.0.1:12306/ping } catch { Write-Host "chrome-mcp bridge: DOWN" }

Write-Host "`n=== LM Studio ==="
try { curl.exe -s http://localhost:1234/v1/models } catch { Write-Host "LM Studio: DOWN" }

Write-Host "`n=== Python 路径 ==="
where.exe python3
(Get-Command python3).Source
```
