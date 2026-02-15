"""
سكريبت بناء EXE مع reset لقاعدة البيانات
"""
import os
import sys
import shutil
import subprocess
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def init_menu_on_first_run():
    """إضافة القائمة تلقائياً عند أول تشغيل"""
    print("[INFO] Setting up menu...")
    try:
        # Import and run menu initialization
        sys.path.insert(0, "backend")
        from db import init_db
        
        # Initialize database
        init_db()
        
        # Initialize menu
        # init_menu_data() # Disabled per user request for empty menu
        
        print("[SUCCESS] Menu added successfully!")
    except Exception as e:
        print(f"[WARNING] Error adding menu: {e}")
        import traceback
        traceback.print_exc()

def reset_database():
    """حذف قاعدة البيانات الحالية لإعادة إنشائها فارغة"""
    print("[INFO] Resetting database...")
    
    # حذف قاعدة البيانات الحالية
    db_paths = [
        "cashier.db",
        "restaurant.db",
        "backend/cashier.db",
        "backend/restaurant.db"
    ]
    
    for db_path in db_paths:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
                print(f"[SUCCESS] Deleted: {db_path}")
            except Exception as e:
                print(f"[WARNING] Error deleting {db_path}: {e}")
    
    # حذف قاعدة البيانات من AppData أيضاً
    appdata_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'DawarElOmda')
    appdata_db = os.path.join(appdata_dir, "cashier.db")
    if os.path.exists(appdata_db):
        try:
            os.remove(appdata_db)
            print(f"[SUCCESS] Deleted: {appdata_db}")
        except Exception as e:
            print(f"[WARNING] Error deleting {appdata_db}: {e}")
    
    print("[SUCCESS] Database reset successfully")
    
    # إضافة القائمة بعد reset
    init_menu_on_first_run()

def cleanup_build():
    """تنظيف ملفات البناء القديمة"""
    print("[INFO] Cleaning build files...")
    
    # Force kill potential running instances
    try:
        subprocess.run("taskkill /F /IM DawarElOmda.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run("taskkill /F /IM main_launcher.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import time
        time.sleep(1) # Wait for release
    except:
        pass

    # حذف build و dist
    for dir_name in ["build", "dist"]:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name)
                print(f"[SUCCESS] Deleted: {dir_name}")
            except Exception as e:
                print(f"[WARNING] Error deleting {dir_name}: {e}")
    
    # حذف مجلد التطبيق القديم
    exe_dir = os.path.join("dist", "DawarElOmda")
    if os.path.exists(exe_dir):
        try:
            shutil.rmtree(exe_dir)
            print(f"[SUCCESS] Deleted old folder: {exe_dir}")
        except Exception as e:
            print(f"[WARNING] Error deleting {exe_dir}: {e}")

def build_exe():
    """بناء EXE"""
    print("[INFO] Building EXE (Folder Mode)...")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            ["python", "-m", "PyInstaller", "--noconfirm", "--clean", "main_launcher.spec"],
            check=True,
            text=True
        )
        print("=" * 60)
        print("[SUCCESS] Build successful!")
        print(f"[INFO] Output folder: {os.path.abspath('dist')}")
        return True
    except subprocess.CalledProcessError as e:
        print("=" * 60)
        print(f"[ERROR] Build failed: {e}")
        return False
    except Exception as e:
        print("=" * 60)
        print(f"[ERROR] Unexpected error: {e}")
        return False

def main():
    """الدالة الرئيسية"""
    print("=" * 60)
    print("[INFO] Starting EXE Build Process")
    print("=" * 60)
    
    # 1. Reset قاعدة البيانات
    reset_database()
    print()
    
    # 2. تنظيف ملفات البناء
    cleanup_build()
    print()
    
    # 3. بناء EXE
    success = build_exe()
    print()
    
    if success:
        print("=" * 60)
        print("[SUCCESS] PROCESS COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print(f"[INFO] App is ready at: {os.path.abspath('dist/DawarElOmda.exe')}")
        print("[TIP] Create a shortcut for this file on your desktop")
        print("[NOTE] Database will be empty on first run")
        print("=" * 60)
    else:
        print("=" * 60)
        print("[ERROR] Build failed")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()
