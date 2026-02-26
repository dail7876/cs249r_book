# ═══════════════════════════════════════════════════════════════
#  智能营销业务系统 — Windows PowerShell 一键自动部署脚本
#  目标目录: D:\myprj\marketing-system
#  使用方法: 右键 → 用 PowerShell 运行
#            或管理员 PowerShell 中执行:
#            Set-ExecutionPolicy Bypass -Scope Process -Force
#            .\deploy_windows.ps1
# ═══════════════════════════════════════════════════════════════

$Host.UI.RawUI.WindowTitle = "智能营销业务系统 - 自动部署"
$ErrorActionPreference = "Stop"

# ── 配置 ──────────────────────────────────────────────────────────────────────
$TARGET    = "D:\myprj\marketing-system"
$REPO      = "https://github.com/dail7876/cs249r_book.git"
$BRANCH    = "claude/automated-business-system-NiRrP"
$BIZ_DIR   = "$TARGET\business_system"
$VENV_DIR  = "$TARGET\venv"
$PYPI_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"

function Write-Step([int]$n, [int]$total, [string]$msg) {
    Write-Host ""
    Write-Host "[$n/$total] $msg" -ForegroundColor Cyan
}
function Write-OK([string]$msg)   { Write-Host "      $msg  ✓" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "  [警告] $msg" -ForegroundColor Yellow }
function Write-Fail([string]$msg) {
    Write-Host ""
    Write-Host "  [错误] $msg" -ForegroundColor Red
    Read-Host "按 Enter 退出"
    exit 1
}

# ── 横幅 ──────────────────────────────────────────────────────────────────────
Clear-Host
Write-Host @"
╔══════════════════════════════════════════════════════╗
║       智能营销业务系统  PowerShell 自动部署         ║
║       目标目录: D:\myprj\marketing-system           ║
╚══════════════════════════════════════════════════════╝
"@ -ForegroundColor Blue

# ── Step 1: 检查 Git ──────────────────────────────────────────────────────────
Write-Step 1 7 "检查 Git..."
try {
    $gitVer = git --version 2>&1
    Write-OK "Git: $gitVer"
} catch {
    Write-Fail "未检测到 Git！请安装：https://git-scm.com/download/win"
}

# ── Step 2: 检查 Python ───────────────────────────────────────────────────────
Write-Step 2 7 "检查 Python (需要 3.10+)..."
try {
    $pyVer = python --version 2>&1
    Write-OK "Python: $pyVer"
} catch {
    Write-Fail "未检测到 Python！请安装：https://www.python.org/downloads/ (勾选 Add to PATH)"
}

# ── Step 3: 克隆 / 更新代码 ───────────────────────────────────────────────────
Write-Step 3 7 "下载代码..."
if (-not (Test-Path "D:\myprj")) {
    New-Item -ItemType Directory -Path "D:\myprj" | Out-Null
    Write-OK "已创建 D:\myprj"
}

if (Test-Path $TARGET) {
    Write-Host "      目录已存在，更新代码..." -ForegroundColor Gray
    Set-Location $TARGET
    git fetch origin $BRANCH 2>&1 | Out-Null
    git checkout $BRANCH 2>&1 | Out-Null
    git pull origin $BRANCH
} else {
    Write-Host "      正在从 GitHub 克隆（约 10-30 秒）..." -ForegroundColor Gray
    Set-Location "D:\myprj"
    git clone -b $BRANCH $REPO marketing-system
    if ($LASTEXITCODE -ne 0) { Write-Fail "代码克隆失败！请检查网络连接。" }
}
Write-OK "代码已就绪：$TARGET"

# ── Step 4: 虚拟环境 ──────────────────────────────────────────────────────────
Write-Step 4 7 "创建 Python 虚拟环境..."
if (-not (Test-Path $VENV_DIR)) {
    python -m venv $VENV_DIR
    if ($LASTEXITCODE -ne 0) { Write-Fail "虚拟环境创建失败！" }
    Write-OK "虚拟环境已创建：$VENV_DIR"
} else {
    Write-OK "虚拟环境已存在，跳过"
}

# ── Step 5: 安装依赖 ──────────────────────────────────────────────────────────
Write-Step 5 7 "安装依赖包（首次约需 2-5 分钟）..."
$pip = "$VENV_DIR\Scripts\pip.exe"
& $pip install --upgrade pip -q
Write-Host "      使用清华镜像加速..." -ForegroundColor Gray
& $pip install -r "$BIZ_DIR\requirements.txt" -i $PYPI_MIRROR --trusted-host pypi.tuna.tsinghua.edu.cn
if ($LASTEXITCODE -ne 0) {
    Write-Warn "镜像安装部分失败，尝试官方源..."
    & $pip install -r "$BIZ_DIR\requirements.txt"
}
Write-OK "依赖安装完成"

# ── Step 6: 配置文件 ──────────────────────────────────────────────────────────
Write-Step 6 7 "初始化配置..."
$envFile = "$BIZ_DIR\.env"
if (-not (Test-Path $envFile)) {
    Copy-Item "$BIZ_DIR\.env.example" $envFile
    Write-OK "已生成 .env 配置文件"
    Write-Host @"

  ┌─────────────────────────────────────────────────────────┐
  │  [可选] 如需 AI 对话 / 微信 / 钉钉，请编辑：           │
  │  $envFile
  │                                                         │
  │  不填写也可正常运行（使用内置规则引擎）                 │
  └─────────────────────────────────────────────────────────┘
"@ -ForegroundColor Yellow
} else {
    Write-OK ".env 配置已存在，跳过"
}

# 创建数据目录
@("uploads","reports","cache") | ForEach-Object {
    $dir = "$BIZ_DIR\data\$_"
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
}
Write-OK "数据目录已就绪"

# ── Step 7: 生成脚本 & 快捷方式 ───────────────────────────────────────────────
Write-Step 7 7 "生成快捷启动脚本..."

# 启动脚本
$startScript = @"
@echo off
chcp 65001 >nul
title 智能营销业务系统
cd /d "$BIZ_DIR"
call "$VENV_DIR\Scripts\activate.bat"
echo.
echo  正在启动 智能营销业务系统...
echo  访问地址: http://localhost:8000
echo  按 Ctrl+C 停止服务
echo.
python main.py
pause
"@
$startScript | Set-Content "$TARGET\启动系统.bat" -Encoding UTF8

# 停止脚本
$stopScript = @"
@echo off
chcp 65001 >nul
taskkill /f /im python.exe /t >nul 2>&1
echo 系统已停止。
pause
"@
$stopScript | Set-Content "$TARGET\停止系统.bat" -Encoding UTF8

# 编辑配置脚本
"@echo off`nnotepad `"$envFile`"" | Set-Content "$TARGET\编辑配置.bat" -Encoding UTF8

Write-OK "快捷脚本已生成"

# 桌面快捷方式
try {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $wsh = New-Object -ComObject WScript.Shell
    $shortcut = $wsh.CreateShortcut("$desktop\营销业务系统.lnk")
    $shortcut.TargetPath = "$TARGET\启动系统.bat"
    $shortcut.WorkingDirectory = $BIZ_DIR
    $shortcut.IconLocation = "shell32.dll,167"
    $shortcut.Description = "智能营销业务系统"
    $shortcut.Save()
    Write-OK "桌面快捷方式已创建"
} catch {
    Write-Warn "桌面快捷方式创建失败（可手动运行启动脚本）"
}

# ── 完成 ──────────────────────────────────────────────────────────────────────
Write-Host @"

╔══════════════════════════════════════════════════════════════╗
║                      部署完成！                             ║
╠══════════════════════════════════════════════════════════════╣
║  安装目录: D:\myprj\marketing-system                       ║
║                                                             ║
║  启动方式（三选一）：                                       ║
║  ① 桌面 双击 "营销业务系统" 快捷方式                       ║
║  ② 双击 D:\myprj\marketing-system\启动系统.bat             ║
║  ③ PowerShell:                                             ║
║     cd D:\myprj\marketing-system\business_system           ║
║     ..\venv\Scripts\Activate.ps1                           ║
║     python main.py                                         ║
║                                                             ║
║  浏览器访问: http://localhost:8000                          ║
║  API 文档:   http://localhost:8000/docs                    ║
║                                                             ║
║  其他快捷脚本（在安装目录下）：                             ║
║  · 编辑配置.bat  - 配置 AI Key / 微信 / 钉钉 / 邮件       ║
║  · 停止系统.bat  - 停止运行中的服务                        ║
╚══════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Green

$ans = Read-Host "是否立即启动系统？(Y/N)"
if ($ans -match "^[Yy]") {
    Write-Host "正在启动..." -ForegroundColor Cyan
    Start-Process "$TARGET\启动系统.bat"
    Start-Sleep 4
    Start-Process "http://localhost:8000"
}
