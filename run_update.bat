@echo off
cd /d "%~dp0"
python scheduler\daily_update.py
pause
