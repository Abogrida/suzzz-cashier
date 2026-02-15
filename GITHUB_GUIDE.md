# رفع الكود على GitHub يدوياً

حاولت رفع الكود تلقائياً ولكن الـ Git يحتاج إلى إعداد البيانات الشخصية (الاسم والإيميل) أولاً.

يرجى فتح التيرمينال (Terminal) وتشغيل الأوامر التالية بالترتيب:

1.  **تعريف المستخدم (مرة واحدة):**
    ```bash
    git config --global user.email "you@example.com"
    git config --global user.name "Your Name"
    ```
    *(استبدل الإيميل والاسم ببياناتك)*

2.  **حفظ التغييرات:**
    ```bash
    git add .
    git commit -m "Add offline-first sync system"
    ```

3.  **الرفع على الرابط المخصص:**
    ```bash
    git remote remove origin
    git remote add origin https://github.com/Abogrida1/suzz-system.git
    git push -u origin main
    ```

💡 **ملاحظة:** عند الرفع، قد يطلب منك إدخال اسم المستخدم وكلمة المرور (أو Token) الخاص بـ GitHub.
