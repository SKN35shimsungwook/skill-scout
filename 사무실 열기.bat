@echo off
chcp 65001 > nul
rem 더블클릭하면 skill-scout 사무실 화면을 켜고 브라우저를 연다. 이 창을 닫으면 서버도 꺼진다.
cd /d "%~dp0"
title skill-scout 사무실

rem 이미 켜져 있으면 브라우저만 연다
netstat -ano | findstr ":8565" | findstr "LISTENING" > nul
if %errorlevel%==0 (
    echo 사무실이 이미 켜져 있어서 브라우저만 엽니다.
    start "" http://localhost:8565
    timeout /t 2 > nul
    exit /b
)

echo ============================================
echo   skill-scout 사무실을 켜는 중입니다
echo   브라우저: http://localhost:8565
echo   끄려면 이 창을 닫거나 Ctrl+C 를 누르세요
echo ============================================
set PYTHONIOENCODING=utf-8
"C:\Users\playdata2\miniconda3\python.exe" office.py
echo.
echo 사무실 서버가 꺼졌습니다.
pause
