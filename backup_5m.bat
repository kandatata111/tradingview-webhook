@echo off
rem ============================================================
rem  5分足 Gmailバックアップ取得スクリプト
rem  Gmailのメールタイトル: "5分毎"
rem  実行間隔: Windowsタスクスケジューラで5分毎に設定すること
rem ============================================================
cd /d %~dp0
call ..\venv\Scripts\activate.bat 2>nul
if errorlevel 1 (
    rem venvが見つからない場合はシステムPythonを使用
    python backup_recovery.py --fetch --tf-filter 5 --subject-filter "5分毎" --non-interactive --after-days 1
) else (
    python backup_recovery.py --fetch --tf-filter 5 --subject-filter "5分毎" --non-interactive --after-days 1
)
