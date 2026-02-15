# -*- mode: python ; coding: utf-8 -*-
import os

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(
    ['main_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('backend', 'backend'),
        ('frontend', 'frontend'),

    ] + collect_data_files('escpos') + ([('icon.ico', '.')] if os.path.exists('icon.ico') else []),
    hiddenimports=[
        'uvicorn',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.logging',
        'fastapi',
        'fastapi.staticfiles',
        'fastapi.responses',
        'fastapi.middleware',
        'fastapi.middleware.cors',
        'websockets',
        'websockets.server',
        'pydantic',
        'pydantic.fields',
        'pydantic.types',
        'multipart',
        'sqlite3',
        'asyncio',
        'asyncio.windows_events',
        'reportlab',
        'reportlab.pdfgen',
        'reportlab.lib',
        'reportlab.lib.pagesizes',
        'reportlab.lib.units',
        'reportlab.pdfbase',
        'reportlab.pdfbase.ttfonts',
        'win32print',
        'win32api',
        'win32con',
        'pywintypes',
        'win32print.EnumPrinters',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',

        'PyQt6.QtNetwork',
        'PyQt6.QtPrintSupport',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'PIL.ImageTk',
        'arabic_reshaper',
        'bidi',
        'bidi.algorithm',
        'escpos',
        'escpos.printer',

    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DawarElOmda',  # EXE filename (using underscore for Windows compatibility)
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Disable UPX to avoid issues
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Hide console - opens browser instead
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,  # Application icon
    uac_admin=False,  # Don't require admin privileges
    version=None,  # Version info (can be added later)
)
