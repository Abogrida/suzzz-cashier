@echo off
echo Building Cashier System EXE...
echo.

REM Install PyInstaller if not installed
pip install pyinstaller

REM Create build directory
if not exist "build" mkdir build
if not exist "dist" mkdir dist

REM Build EXE
pyinstaller --noconfirm --windowed --name "cashier" ^
    --add-data "frontend;frontend" ^
    --add-data "backend;backend" ^
    --hidden-import "uvicorn.loops.auto" ^
    --hidden-import "uvicorn.loops.uvloop" ^
    --hidden-import "uvicorn.protocols.http.auto" ^
    --hidden-import "uvicorn.protocols.websockets.auto" ^
    --hidden-import "uvicorn.lifespan.on" ^
    --collect-all "uvicorn" ^
    --collect-all "fastapi" ^
    --onefile ^
    main.py

echo.
echo Build complete! EXE is in the dist folder.
echo.
pause

