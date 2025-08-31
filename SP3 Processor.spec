# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['process_sp3.py'],
    pathex=[],
    binaries=[],
    datas=[('D:\\vremya-ch\\Progs\\PY\\sp3\\gnss_env\\Lib\\site-packages\\allantools\\allantools_info.json', 'allantools'),],
    hiddenimports=['scipy._cyutility', 'scipy._lib.messagestream', 'scipy.signal', 'allantools'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SP3 Processor',
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
