
# Core application definition
# Separated to avoid circular imports between main.py and api modules
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import sys

# Determine base directory
if getattr(sys, 'frozen', False):
    # Running as compiled EXE
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Running as script
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Create FastAPI app
app = FastAPI(title="دوار العمده - نظام إدارة المطعم")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_base_dir():
    return BASE_DIR

def get_static_dir():
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = BASE_DIR
    return os.path.join(base_path, "frontend", "static")
