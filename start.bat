@echo off
chcp 65001 >nul
cd /d %~dp0

REM 一键启动：优先使用项目虚拟环境，其次系统 Python
if exist ".venv\Scripts\python.exe" (
    set PY=.venv\Scripts\python.exe
) else (
    set PY=python
)

echo 正在启动霸王茶姬销量分析平台...
%PY% serve.py

pause
