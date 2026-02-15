@echo off
echo Stopping any running servers...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *main.py*" >nul 2>&1
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *tablet_server*" >nul 2>&1
timeout /t 2 /nobreak >nul
echo.
echo Starting Cashier System...
echo.
python main_launcher.py
pause

