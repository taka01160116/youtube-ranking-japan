@echo off
set TASK_NAME=YouTubeRankingAutoUpdate
set BAT_PATH="C:\Users\PC_User\Desktop\youtube_ranking_mvp\run_update.bat"

schtasks /create ^
 /tn %TASK_NAME% ^
 /tr %BAT_PATH% ^
 /sc daily ^
 /st 09:00 ^
 /f

echo ✅ タスクスケジューラに登録しました！
pause
