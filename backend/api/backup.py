from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import shutil
import os
import sys
import sqlite3
import time
from db import DB_PATH, get_db, init_db

router = APIRouter()

def get_table_columns(cursor, table_name):
    """Get list of column names for a table"""
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        return [row[1] for row in cursor.fetchall()]
    except:
        return []

import zipfile

@router.get("/download")
async def download_backup():
    """Download the current database backup (Full System: DB + Images)"""
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Database not found")
    
    timestamp = int(time.time())
    zip_filename = f"full_system_backup_{timestamp}.zip"
    zip_path = os.path.join(os.path.dirname(DB_PATH), zip_filename)
    
    try:
        # Determine image directory
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            images_dir = os.path.join(base_dir, "images")
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            images_dir = os.path.join(base_dir, "frontend", "static", "images")

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 1. Add Database
            zipf.write(DB_PATH, arcname="cashier.db")
            
            # 2. Add Images (if exist)
            if os.path.exists(images_dir):
                for root, dirs, files in os.walk(images_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Archive name should be relative to images folder
                        # e.g. images/products/1.jpg
                        rel_path = os.path.relpath(file_path, os.path.dirname(images_dir))
                        zipf.write(file_path, arcname=rel_path)
            
        return FileResponse(
            zip_path, 
            filename=zip_filename,
            media_type="application/zip",
            background=BackgroundTasks().add_task(os.remove, zip_path)
        )
    except Exception as e:
        if os.path.exists(zip_path):
            try: os.remove(zip_path)
            except: pass
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")

@router.get("/download-menu")
async def download_menu_backup():
    """Download ONLY menu data (Categories, Products, Additions)"""
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Database not found")
    
    timestamp = int(time.time())
    temp_db_path = f"menu_backup_{timestamp}.db"
    
    try:
        # Connect to main DB
        src_conn = sqlite3.connect(DB_PATH)
        src_conn.row_factory = sqlite3.Row
        
        # Create temp DB
        dest_conn = sqlite3.connect(temp_db_path)
        
        # Copy tables
        tables_to_copy = ['categories', 'products', 'product_additions']
        
        for table in tables_to_copy:
            # Get schema from source
            src_cursor = src_conn.cursor()
            src_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
            schema_row = src_cursor.fetchone()
            
            if schema_row:
                create_sql = schema_row[0]
                dest_conn.execute(create_sql)
                
                # Copy data
                rows = src_conn.execute(f"SELECT * FROM {table}").fetchall()
                if rows:
                    placeholders = ','.join(['?'] * len(rows[0]))
                    dest_conn.executemany(f"INSERT INTO {table} VALUES ({placeholders})", [tuple(row) for row in rows])
        
        dest_conn.commit()
        src_conn.close()
        dest_conn.close()
        
        return FileResponse(
            temp_db_path,
            filename=f"menu_backup_{timestamp}.db",
            media_type="application/x-sqlite3",
            background=BackgroundTasks().add_task(os.remove, temp_db_path)
        )
        
    except Exception as e:
        if os.path.exists(temp_db_path):
            try: os.remove(temp_db_path)
            except: pass
        raise HTTPException(status_code=500, detail=f"Menu backup failed: {str(e)}")

@router.post("/restore-full")
async def restore_full_backup(file: UploadFile = File(...)):
    """Restore full system from backup (Supports .zip for DB+Images or legacy .db)"""
    is_zip = file.filename.endswith('.zip')
    is_db = file.filename.endswith('.db')
    
    if not (is_zip or is_db):
        raise HTTPException(status_code=400, detail="Invalid file format. Must be .zip or .db")
    
    # Save uploaded file to temp
    temp_path = f"{DB_PATH}.restore_temp"
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Determine paths
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            images_dir = os.path.join(base_dir, "images")
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            images_dir = os.path.join(base_dir, "frontend", "static", "images")

        if is_zip:
            # Handle ZIP Restore
            try:
                with zipfile.ZipFile(temp_path, 'r') as zipf:
                    # Validate contents
                    if "cashier.db" not in zipf.namelist():
                         raise Exception("Invalid backup: cashier.db not found in zip")
                    
                    # 1. Restore DB
                    # Extract single file to temp location first
                    zipf.extract("cashier.db", os.path.dirname(temp_path))
                    extracted_db = os.path.join(os.path.dirname(temp_path), "cashier.db")
                    
                    # Backup current DB
                    timestamp = int(time.time())
                    backup_path = f"{DB_PATH}.{timestamp}.bak"
                    shutil.copy2(DB_PATH, backup_path)
                    
                    # Replace DB
                    max_retries = 5
                    for i in range(max_retries):
                        try:
                            shutil.move(extracted_db, DB_PATH)
                            break
                        except PermissionError:
                            if i == max_retries - 1:
                                raise Exception("Database is locked. Restart app.")
                            time.sleep(1)

                    # Apply schema updates (migrations)
                    try:
                        print("Applying schema updates to restored database...")
                        init_db()
                        print("Schema updates applied successfully.")
                    except Exception as e:
                        print(f"Warning: Schema update failed after restore: {e}")
                            
                    # 2. Restore Images
                    # Filter for image files
                    for member in zipf.namelist():
                        if member.startswith("images/") and not member.endswith("/"):
                            # Safety check: Prevent directory traversal
                            if ".." in member: continue
                            
                            # Extract path logic
                            # member is "images/products/x.jpg"
                            # We want to extract to our images_dir (".../images")
                            # But zipf.extract extracts full path.
                            
                            # We need to manually write files to ensure correct target
                            source = zipf.open(member)
                            # Remove "images/" prefix for target
                            rel_target = member[7:] # strip "images/"
                            target_path = os.path.join(images_dir, rel_target)
                            
                            # Create dirs
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            
                            with open(target_path, "wb") as target_file:
                                shutil.copyfileobj(source, target_file)
                                
                return {"status": "success", "message": "Full system (DB + Images) restored successfully. Please restart the application."}
                
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid ZIP file: {str(e)}")

        else:
            # Handle Legacy DB Restore
            # Verify valid SQLite
            try:
                conn = sqlite3.connect(temp_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                if not cursor.fetchall(): raise Exception("Empty DB")
                conn.close()
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid database file: {str(e)}")
            
            # Backup current
            timestamp = int(time.time())
            backup_path = f"{DB_PATH}.{timestamp}.bak"
            shutil.copy2(DB_PATH, backup_path)
            
            # Replace
            max_retries = 5
            for i in range(max_retries):
                try:
                    shutil.move(temp_path, DB_PATH)
                    break
                except PermissionError:
                    if i == max_retries - 1:
                        raise HTTPException(status_code=500, detail="Database locked.")
                    time.sleep(1)

            # Apply schema updates (migrations)
            try:
                print("Applying schema updates to restored database...")
                init_db()
                print("Schema updates applied successfully.")
            except Exception as e:
                print(f"Warning: Schema update failed after restore: {e}")
                    
            return {"status": "success", "message": "Database restored successfully. Please restart the application."}
        
    except Exception as e:
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass
        raise HTTPException(status_code=500, detail=f"Restore failed: {str(e)}")

@router.post("/restore-menu")
async def restore_menu_backup(file: UploadFile = File(...)):
    """Restore ONLY menu (Categories, Products, Additions) with Robust Schema Matching"""
    if not file.filename.endswith('.db'):
        raise HTTPException(status_code=400, detail="Invalid file format. Must be .db")
    
    temp_path = f"{DB_PATH}.menu_restore_temp"
    try:
        # Save uploaded file
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Connect to uploaded DB (Source)
        src_conn = sqlite3.connect(temp_path)
        src_conn.row_factory = sqlite3.Row
        src_cursor = src_conn.cursor()
        
        # Connect to current DB (Destination)
        dest_conn = sqlite3.connect(DB_PATH)
        dest_cursor = dest_conn.cursor()
        
        tables_to_restore = ['categories', 'products', 'product_additions']
        
        try:
            for table in tables_to_restore:
                # Check if table exists in source
                try:
                    src_cursor.execute(f"SELECT * FROM {table} LIMIT 1")
                except:
                    continue # Table doesn't exist in backup, skip
                
                # Get columns for both
                src_columns = get_table_columns(src_cursor, table)
                dest_columns = get_table_columns(dest_cursor, table)
                
                # Find common columns
                common_columns = list(set(src_columns) & set(dest_columns))
                
                if not common_columns:
                    continue
                
                # Build dynamic query
                cols_str = ", ".join(common_columns)
                placeholders = ", ".join(["?"] * len(common_columns))
                
                # Get data from source
                src_cursor.execute(f"SELECT {cols_str} FROM {table}")
                rows = src_cursor.fetchall()
                
                for row in rows:
                    values = [row[col] for col in common_columns]
                    
                    # Construct UPSERT query based on table
                    if table == 'categories':
                        query = f"""
                            INSERT INTO categories ({cols_str}) VALUES ({placeholders})
                            ON CONFLICT(id) DO UPDATE SET name=excluded.name
                        """
                    elif table == 'products':
                        # Build dynamic UPDATE set
                        update_set = ", ".join([f"{col}=excluded.{col}" for col in common_columns if col != 'id'])
                        query = f"""
                            INSERT INTO products ({cols_str}) VALUES ({placeholders})
                            ON CONFLICT(id) DO UPDATE SET {update_set}
                        """
                    elif table == 'product_additions':
                        query = f"INSERT OR IGNORE INTO product_additions ({cols_str}) VALUES ({placeholders})"
                    
                    try:
                        dest_cursor.execute(query, values)
                    except Exception as row_error:
                        print(f"Error restoring row in {table}: {row_error}")
                        continue
                        
            dest_conn.commit()
            
        finally:
            src_conn.close()
            dest_conn.close()
            
        return {"status": "success", "message": "Menu restored successfully (Smart Schema Match)"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Menu restore failed: {str(e)}")
    finally:
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass
