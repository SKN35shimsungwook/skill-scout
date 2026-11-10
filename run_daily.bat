@echo off
rem 윈도우 작업 스케줄러가 08:00·잠금 해제·로그인 때 실행하는 파일 (하루 한 번만 전송). 결과 로그는 data\run.log
chcp 65001 > nul
cd /d "%~dp0"
if not exist data mkdir data
set PYTHONIOENCODING=utf-8
echo ===== %date% %time% ===== >> data\run.log
"C:\Users\playdata2\miniconda3\python.exe" run.py --scheduled >> data\run.log 2>&1
