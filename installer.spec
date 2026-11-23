# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ['installer.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('dist/AldeloComandero.exe', '.'),
        ('config.json', '.'),
        ('app.ico', '.'),
    ],
    hiddenimports=[],
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
    name='InstaladorServicioAldelo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    uac_admin=True,
    icon='app.ico'
)
