@echo off
cd /d "%~dp0"

echo ===========================
echo Python のフルパス確認中...
echo ===========================

where python
IF ERRORLEVEL 1 (
    echo ❌ Python コマンドが見つかりません！
    echo 環境変数 Path に Python が登録されていない可能性があります。
    goto end
) ELSE (
    echo ✅ Python が見つかりました！
)

echo.
echo ===========================
echo スクリプトを実行します...
echo ===========================
python scheduler\daily_update.py

echo.
echo ===========================
echo 処理が完了しました。
echo ===========================

:end
echo.
echo 続行するには何かキーを押してください...
pause >nul
