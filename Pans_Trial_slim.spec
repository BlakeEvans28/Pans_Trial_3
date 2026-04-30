# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path(SPECPATH).resolve()


a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / 'assets'), 'assets'),
        (str(project_root / 'audio'), 'audio'),
    ],
    hiddenimports=[
        'multiplayer',
        'multiplayer.local_room',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'numpy',
        'pandas',
        'pytest',
        'PIL',
        'pillow',
        'cairosvg',
        'freetype',
        'tqdm',
        'pydantic',
        'psutil',
    ],
    noarchive=False,
    optimize=0,
)

excluded_data_patterns = (
    'pygame_gui\\data\\NotoSansSC-',
    'pygame_gui\\data\\NotoSansKR-',
    'pygame_gui\\data\\NotoSansJP-',
)

a.datas = [
    item for item in a.datas
    if not any(pattern in item[0].replace('/', '\\') for pattern in excluded_data_patterns)
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Pans_Trial',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
