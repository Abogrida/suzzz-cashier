@echo off
echo ========================================
echo تثبيت دعم اللغة العربية (اختياري)
echo ========================================
echo.
echo هذا التثبيت اختياري - النظام يعمل بدونها أيضاً
echo.
echo جاري محاولة تثبيت arabic-reshaper و python-bidi...
echo.

pip install arabic-reshaper>=2.1.3 --quiet
if %errorlevel% equ 0 (
    echo ✅ تم تثبيت arabic-reshaper بنجاح
) else (
    echo ⚠️ فشل تثبيت arabic-reshaper (سيتم استخدام النص الأصلي)
)

pip install python-bidi>=0.4.2 --quiet
if %errorlevel% equ 0 (
    echo ✅ تم تثبيت python-bidi بنجاح
) else (
    echo ⚠️ فشل تثبيت python-bidi (سيتم استخدام النص الأصلي)
)

echo.
echo ========================================
echo انتهى التثبيت
echo ========================================
echo.
echo ملاحظة: إذا فشل التثبيت، النظام سيعمل بدون هذه المكتبات
echo         وسيستخدم ترميز Windows-1256 مباشرة
echo.
pause



