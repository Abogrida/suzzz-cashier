from PyInstaller.utils.hooks import collect_data_files, collect_all

datas = [
    ('backend', 'backend'),
    ('frontend', 'frontend'),
    ('tablet_server.py', '.'),
    ('icon.ico', '.'),
    ('image.png', '.'),
    ('dinning-table.png', '.'),
    *collect_data_files('escpos'),
]
binaries = []
hiddenimports = [
    'engineio.async_drivers.threading',
    'arabic_reshaper',
    'bidi.algorithm',
    'sqlite3',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'init_menu_data',
    'backend.init_menu_data',
    'win32print',
    'win32api',
    'escpos',
    'escpos.printer',
]

# Collect all resources for fastAPI and uvicorn
for package in ['fastapi', 'uvicorn', 'starlette', 'pydantic', 'email_validator']:
    try:
        tmp_ret = collect_all(package)
        datas += tmp_ret[0]
        binaries += tmp_ret[1]
        hiddenimports += tmp_ret[2]
    except Exception:
        pass

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name='دوار_العمده',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='دوار_العمده',
)
