@echo off
echo ========================================
echo Stopping Cashier System servers...
echo ========================================
echo.

REM Kill processes on ports 3000 and 3001
echo Checking port 3000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do (
    echo   Stopping process on port 3000 (PID: %%a)
    taskkill /F /PID %%a >nul 2>&1
    if errorlevel 1 (
        echo   Failed to stop process %%a
    ) else (
        echo   Process %%a stopped successfully
    )
)

echo Checking port 3001...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3001" ^| findstr "LISTENING"') do (
    echo   Stopping process on port 3001 (PID: %%a)
    taskkill /F /PID %%a >nul 2>&1
    if errorlevel 1 (
        echo   Failed to stop process %%a
    ) else (
        echo   Process %%a stopped successfully
    )
)

REM Wait a bit
timeout /t 1 /nobreak >nul

echo.
echo ========================================
echo Servers stopped!
echo ========================================
echo.
pause

