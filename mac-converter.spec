# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['clipboard_hotkey.py'],
    pathex=[],
    binaries=[],
    datas=[('icon-v1.png', '.')],
    hiddenimports=[
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        'pystray._win32',
        'win32com.client',
        'win32event',
        'win32api',
        'winerror',
        'truststore',
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
    name='MAC-Converter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # F34: UPX disabled — trades ~30% binary size for far fewer AV false positives
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon-v1.ico',
)
