@echo off
set TASK_NAME=YouTubeRankingAutoUpdate

schtasks /delete /tn %TASK_NAME% /f

echo ✅ タスク %TASK_NAME% を削除しました！
pause
