# إصلاح خطأ Permission Error عند بناء EXE

## المشكلة
```
PermissionError: [WinError 5] Access is denied: 'C:\\Users\\hacker\\Desktop\\system2\\dist\\دوار_العمده.exe'
```

## الحلول السريعة

### الحل 1: إغلاق التطبيق يدوياً
1. افتح Task Manager (Ctrl + Shift + Esc)
2. ابحث عن `دوار_العمده.exe`
3. اضغط End Task
4. حاول بناء EXE مرة أخرى

### الحل 2: إغلاق File Explorer
1. أغلق أي نافذة File Explorer مفتوحة على مجلد `dist`
2. حاول بناء EXE مرة أخرى

### الحل 3: حذف الملف يدوياً
1. افتح مجلد `dist`
2. احذف ملف `دوار_العمده.exe` يدوياً
3. حاول بناء EXE مرة أخرى

### الحل 4: إعادة تشغيل PowerShell
1. أغلق PowerShell الحالي
2. افتح PowerShell جديد كـ Administrator
3. انتقل إلى مجلد المشروع
4. شغل `python build_exe.py`

### الحل 5: تثبيت psutil (اختياري)
```bash
pip install psutil
```
هذا سيساعد script في إغلاق التطبيق تلقائياً.

## بعد إصلاح المشكلة

1. شغل: `python build_exe.py`
2. انتظر حتى يكتمل البناء
3. الملف سيكون في: `dist/دوار_العمده.exe`

## ملاحظات
- تأكد من إغلاق التطبيق قبل البناء
- تأكد من عدم فتح مجلد `dist` في File Explorer
- بعض برامج Antivirus قد تمنع حذف الملف - أضف استثناء مؤقت














