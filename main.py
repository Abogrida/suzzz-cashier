"""
Main entry point for Cashier System
This file is used for both development and PyInstaller EXE build
"""
import sys
import os
import io

# Fix for Uvicorn creating loggers when sys.stdout/stderr is None (happens in windowed EXE)
if sys.stdout is None:
    sys.stdout = io.StringIO()
    sys.stdout.isatty = lambda: False

if sys.stderr is None:
    sys.stderr = io.StringIO()
    sys.stderr.isatty = lambda: False
    
# Change to backend directory
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
os.chdir(backend_dir)
sys.path.insert(0, backend_dir)

# Import and run the application
from server import app, get_local_ip, close_all_open_shifts, setup_shutdown_handlers
from sync_agent import sync_agent # Import Sync Agent
import uvicorn
import webbrowser
import threading

def open_browser():
    """Open browser after server starts (App Mode)"""
    import time
    time.sleep(1.5)
    url = "http://localhost:3000"
    
    # Try to find Chrome or Edge paths
    browser_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    ]
    
    found_browser = False
    for path in browser_paths:
        if os.path.exists(path):
            try:
                # Launch in App Mode (no address bar, feels like native app)
                subprocess.Popen([path, f"--app={url}"])
                found_browser = True
                break
            except:
                continue
                
    if not found_browser:
        # Fallback to default browser
        webbrowser.open(url)

import subprocess

def kill_process_on_port(port):
    """
    Kills any process listening on the specified port.
    Uses netstat to find the PID and taskkill to terminate it.
    """
    try:
        # Run netstat to find the process ID (PID)
        cmd = f'netstat -ano | findstr :{port}'
        # Use shell=True to allow piping
        try:
            output = subprocess.check_output(cmd, shell=True).decode()
        except subprocess.CalledProcessError:
            # Command failed usually means no process found
            return

        # Parse output to find PIDs
        pids = set()
        for line in output.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                if parts:
                    pid = parts[-1]
                    pids.add(pid)
        
        # Kill processes
        for pid in pids:
            # Skip if PID is 0 (System Idle Process) or current process (unlikely but safe)
            if pid == "0" or pid == str(os.getpid()):
                continue
                
            print(f"[INFO] Killing lingering process {pid} on port {port}...")
            try:
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except:
                pass
            
        if pids:
            import time
            time.sleep(1) # Wait for process to fully exit
            
    except Exception as e:
        print(f"[WARNING] Error cleaning up port {port}: {e}")

if __name__ == "__main__":
    # Ensure port 3000 is free before starting
    print("[INFO] Checking port 3000...")
    kill_process_on_port(3000)

    # Setup shutdown handlers (but don't auto-close shifts on startup)
    # setup_shutdown_handlers()  # Disabled - shifts should only be closed manually
    
    # Don't close open shifts from previous session - let them stay open
    # print("Checking for open shifts from previous session...")
    # close_all_open_shifts()  # Disabled
    
    
    # Start Sync Agent
    try:
        sync_agent.start()
    except Exception as e:
        print(f"[ERROR] Failed to start Sync Agent: {e}")

    local_ip = get_local_ip()
    print(f"\n{'='*50}")
    print(f"Cashier System Started!")
    print(f"Local Network: http://{local_ip}:3000")
    print(f"Local Access: http://localhost:3000")
    print(f"{'='*50}\n")
    
    # Open browser in a separate thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    try:
        # Start server
        uvicorn.run(app, host="0.0.0.0", port=3000, log_level="info")
    except KeyboardInterrupt:
        print("\n[INFO] Keyboard interrupt received...")
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        # Need user to see error in CLI window if it crashes immediately
        import time
        time.sleep(5)
        raise







