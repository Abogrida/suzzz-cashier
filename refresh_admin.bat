@echo off
echo ===================================
echo   تنظيف Cache وإعادة تشغيل السيرفر
echo ===================================
echo.

echo [1/3] إيقاف السيرفر...
taskkill /F /IM python.exe 2>nul
timeout /t 2 >nul

echo [2/3] تشغيل السيرفر...
start "" python main_launcher.py
timeout /t 5 >nul

echo [3/3] فتح صفحة الإدارة...
echo.
echo ⚠️ مهم: عند فتح الصفحة، اضغط Ctrl+F5 لتحديث الصفحة بدون cache
echo.
start "" http://localhost:3000/admin
echo.
echo ✅ تم! 
echo.
echo إذا لم تظهر أزرار QR:
echo 1. اضغط F12 لفتح Developer Tools
echo 2. اضغط بزر الماوس الأيمن على زر Refresh
echo 3. اختر "Empty Cache and Hard Reload"
echo.
pause
