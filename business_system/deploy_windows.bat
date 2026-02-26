@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: ═══════════════════════════════════════════════════════════════
::  智能营销业务系统 — Windows 一键自动部署脚本
::  目标目录: D:\myprj\marketing-system
::  使用方法: 右键 → 以管理员身份运行
:: ═══════════════════════════════════════════════════════════════

title 智能营销业务系统 - 自动部署

set "TARGET=D:\myprj\marketing-system"
set "REPO=https://github.com/dail7876/cs249r_book.git"
set "BRANCH=claude/automated-business-system-NiRrP"
set "VENV=%TARGET%\venv"
set "PYTHON_MIN=310"

echo.
echo ╔══════════════════════════════════════════════════╗
echo ║       智能营销业务系统  自动部署程序             ║
echo ║       目标目录: D:\myprj\marketing-system        ║
echo ╚══════════════════════════════════════════════════╝
echo.

:: ───────────────────────────────────────────────────────────────
:: 1. 检查管理员权限
:: ───────────────────────────────────────────────────────────────
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [警告] 建议以管理员身份运行以确保权限正常
    echo        正在尝试继续...
    echo.
)

:: ───────────────────────────────────────────────────────────────
:: 2. 检查 Git
:: ───────────────────────────────────────────────────────────────
echo [1/7] 检查 Git...
git --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [错误] 未检测到 Git！请先安装：https://git-scm.com/download/win
    echo        安装后重新运行此脚本。
    pause
    exit /b 1
)
for /f "tokens=3" %%v in ('git --version') do set GIT_VER=%%v
echo       Git 版本: %GIT_VER%  ✓

:: ───────────────────────────────────────────────────────────────
:: 3. 检查 Python
:: ───────────────────────────────────────────────────────────────
echo [2/7] 检查 Python...
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [错误] 未检测到 Python！请先安装 Python 3.10+
    echo        下载地址：https://www.python.org/downloads/
    echo        安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo       Python 版本: %PY_VER%  ✓

:: ───────────────────────────────────────────────────────────────
:: 4. 创建目标目录并克隆代码
:: ───────────────────────────────────────────────────────────────
echo [3/7] 准备目录并下载代码...
if not exist "D:\myprj" (
    mkdir "D:\myprj"
    echo       已创建 D:\myprj
)

if exist "%TARGET%" (
    echo       目录已存在，正在更新代码...
    cd /d "%TARGET%"
    git fetch origin %BRANCH% >nul 2>&1
    git checkout %BRANCH% >nul 2>&1
    git pull origin %BRANCH%
    if %errorLevel% neq 0 (
        echo [警告] 更新失败，尝试重新克隆...
        cd /d "D:\myprj"
        rmdir /s /q "%TARGET%"
        goto :clone
    )
    goto :after_clone
)

:clone
echo       正在从 GitHub 克隆代码（约 10-30 秒）...
cd /d "D:\myprj"
git clone -b %BRANCH% %REPO% marketing-system
if %errorLevel% neq 0 (
    echo [错误] 代码克隆失败！请检查网络连接或仓库权限。
    pause
    exit /b 1
)

:after_clone
echo       代码已就绪  ✓

:: ───────────────────────────────────────────────────────────────
:: 5. 进入项目目录
:: ───────────────────────────────────────────────────────────────
cd /d "%TARGET%\business_system"
echo       工作目录: %CD%

:: ───────────────────────────────────────────────────────────────
:: 6. 创建虚拟环境
:: ───────────────────────────────────────────────────────────────
echo [4/7] 创建 Python 虚拟环境...
if not exist "%VENV%" (
    python -m venv "%VENV%"
    if %errorLevel% neq 0 (
        echo [错误] 虚拟环境创建失败！
        pause
        exit /b 1
    )
    echo       虚拟环境已创建  ✓
) else (
    echo       虚拟环境已存在，跳过  ✓
)

:: 激活虚拟环境
call "%VENV%\Scripts\activate.bat"

:: ───────────────────────────────────────────────────────────────
:: 7. 安装依赖
:: ───────────────────────────────────────────────────────────────
echo [5/7] 安装依赖包（首次安装约需 2-5 分钟）...
pip install --upgrade pip -q
pip install -r requirements.txt ^
    -i https://pypi.tuna.tsinghua.edu.cn/simple ^
    --trusted-host pypi.tuna.tsinghua.edu.cn
if %errorLevel% neq 0 (
    echo [警告] 部分包安装失败，尝试官方源...
    pip install -r requirements.txt
)
echo       依赖安装完成  ✓

:: ───────────────────────────────────────────────────────────────
:: 8. 配置环境变量
:: ───────────────────────────────────────────────────────────────
echo [6/7] 配置系统...
if not exist "%TARGET%\business_system\.env" (
    copy "%TARGET%\business_system\.env.example" "%TARGET%\business_system\.env" >nul
    echo       已生成 .env 配置文件
    echo.
    echo ┌─────────────────────────────────────────────────────┐
    echo │  [可选] 请编辑以下文件填入 AI Key 和消息平台配置：  │
    echo │  %TARGET%\business_system\.env  │
    echo │                                                     │
    echo │  不填写也可运行（使用内置规则引擎）                 │
    echo └─────────────────────────────────────────────────────┘
    echo.
) else (
    echo       .env 配置文件已存在，跳过  ✓
)

:: 创建数据目录
if not exist "%TARGET%\business_system\data\uploads" mkdir "%TARGET%\business_system\data\uploads"
if not exist "%TARGET%\business_system\data\reports" mkdir "%TARGET%\business_system\data\reports"
if not exist "%TARGET%\business_system\data\cache"   mkdir "%TARGET%\business_system\data\cache"
echo       数据目录已就绪  ✓

:: ───────────────────────────────────────────────────────────────
:: 9. 生成启动脚本
:: ───────────────────────────────────────────────────────────────
echo [7/7] 生成快捷启动脚本...

:: 生成启动脚本
(
echo @echo off
echo chcp 65001 ^>nul
echo title 智能营销业务系统
echo cd /d "%TARGET%\business_system"
echo call "%VENV%\Scripts\activate.bat"
echo echo.
echo echo  正在启动 智能营销业务系统...
echo echo  访问地址: http://localhost:8000
echo echo  按 Ctrl+C 停止服务
echo echo.
echo python main.py
echo pause
) > "%TARGET%\启动系统.bat"

:: 生成停止脚本
(
echo @echo off
echo chcp 65001 ^>nul
echo echo 正在停止 智能营销业务系统...
echo taskkill /f /im python.exe /t ^>nul 2^>^&1
echo echo 已停止。
echo pause
) > "%TARGET%\停止系统.bat"

:: 生成配置编辑脚本
(
echo @echo off
echo notepad "%TARGET%\business_system\.env"
) > "%TARGET%\编辑配置.bat"

echo       快捷脚本已生成  ✓

:: ───────────────────────────────────────────────────────────────
:: 10. 创建桌面快捷方式
:: ───────────────────────────────────────────────────────────────
set "DESKTOP=%USERPROFILE%\Desktop"
set "SHORTCUT=%DESKTOP%\营销业务系统.lnk"

powershell -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s = $ws.CreateShortcut('%SHORTCUT%'); ^
   $s.TargetPath = '%TARGET%\启动系统.bat'; ^
   $s.WorkingDirectory = '%TARGET%\business_system'; ^
   $s.IconLocation = 'shell32.dll,167'; ^
   $s.Description = '智能营销业务系统'; ^
   $s.Save()" >nul 2>&1
if exist "%SHORTCUT%" (
    echo       桌面快捷方式已创建  ✓
) else (
    echo       桌面快捷方式创建失败（可手动双击启动脚本）
)

:: ───────────────────────────────────────────────────────────────
:: 完成
:: ───────────────────────────────────────────────────────────────
echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║                    部署完成！                           ║
echo ╠══════════════════════════════════════════════════════════╣
echo ║  安装目录: D:\myprj\marketing-system                   ║
echo ║                                                         ║
echo ║  启动方式（三选一）：                                   ║
echo ║  ① 双击桌面快捷方式 "营销业务系统"                     ║
echo ║  ② 双击 D:\myprj\marketing-system\启动系统.bat         ║
echo ║  ③ 命令行：cd /d %TARGET%\business_system              ║
echo ║            venv\Scripts\activate                        ║
echo ║            python main.py                               ║
echo ║                                                         ║
echo ║  启动后浏览器访问: http://localhost:8000                ║
echo ║                                                         ║
echo ║  其他脚本：                                             ║
echo ║  · 编辑配置.bat  - 修改 AI Key 和消息平台配置          ║
echo ║  · 停止系统.bat  - 停止服务                            ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

set /p START_NOW="是否立即启动系统？(Y/N): "
if /i "%START_NOW%"=="Y" (
    echo 正在启动...
    start "" "%TARGET%\启动系统.bat"
    timeout /t 3 >nul
    start "" "http://localhost:8000"
)

pause
