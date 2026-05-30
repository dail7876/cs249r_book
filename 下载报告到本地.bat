@echo off
chcp 65001 >nul
title 下载锚杆台车误差分析报告

:: ═══════════════════════════════════════════════════════════════
::  将"锚杆台车误差与臂架关系可视化报告"下载到指定目录
::  目标: D:\工作文件\赛搏\2026工作\产品开发\实现\台车标定\测试试验
:: ═══════════════════════════════════════════════════════════════

set "TARGET=D:\工作文件\赛搏\2026工作\产品开发\实现\台车标定\测试试验"
set "REPO_RAW=https://raw.githubusercontent.com/dail7876/cs249r_book/claude/automated-business-system-NiRrP/anchor_error_analysis.html"
set "OUTFILE=%TARGET%\锚杆台车误差分析报告.html"

echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║   锚杆台车误差分析报告 — 下载到本地                 ║
echo ╚══════════════════════════════════════════════════════╝
echo.
echo 目标目录: %TARGET%
echo.

:: 1. 创建目录（含所有上级目录）
if not exist "%TARGET%" (
    echo [1/2] 目录不存在，正在创建...
    mkdir "%TARGET%" 2>nul
    if not exist "%TARGET%" (
        echo [错误] 目录创建失败！请检查 D 盘是否存在、是否有写入权限。
        pause
        exit /b 1
    )
    echo       目录已创建  ✓
) else (
    echo [1/2] 目标目录已存在  ✓
)

:: 2. 下载报告文件
echo [2/2] 正在下载报告文件...
curl -L -o "%OUTFILE%" "%REPO_RAW%"
if %errorLevel% neq 0 (
    echo.
    echo [警告] curl 下载失败，尝试 PowerShell 下载...
    powershell -Command "Invoke-WebRequest -Uri '%REPO_RAW%' -OutFile '%OUTFILE%'"
)

if exist "%OUTFILE%" (
    echo       下载完成  ✓
    echo.
    echo ╔══════════════════════════════════════════════════════╗
    echo ║                  完成！                             ║
    echo ╠══════════════════════════════════════════════════════╣
    echo ║  报告已保存至:                                       ║
    echo ║  %OUTFILE%
    echo ╚══════════════════════════════════════════════════════╝
    echo.
    set /p OPEN="是否立即打开报告？(Y/N): "
    if /i "%OPEN%"=="Y" start "" "%OUTFILE%"
) else (
    echo [错误] 下载失败！请检查网络或仓库访问权限。
)

pause
