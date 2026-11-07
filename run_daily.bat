@echo off
rem 윈도우 작업 스케줄러가 매일 아침 실행하는 파일. 결과 로그는 data\run.log
chcp 65001 > nul
cd /d "%~dp0"
if not exist data mkdir data
set PYTHONIOENCODING=utf-8
echo ===== %date% %time% ===== >> data\run.log
"C:\Users\playdata2\miniconda3\python.exe" run.py >> data\run.log 2>&1
