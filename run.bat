@echo off
chcp 65001 >nul
REM ============================================================
REM  饼干桌面宠物 · 直接运行（不打包 EXE，需已装 Python+PySide6）
REM ============================================================
cd /d "%~dp0"
python -m pip install -r requirements.txt
python main.py
pause
