# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

textual_submodules = collect_submodules('textual')
textual_datas = collect_data_files('textual')

a = Analysis(
    ['tui_llama_server/cli.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('tui_llama_server/ui/styles.tcss', 'tui_llama_server/ui'),
        *textual_datas,
    ],
    hiddenimports=[
        *textual_submodules,
        'rich',
        'psutil',
        'gguf',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PIL',
        'matplotlib',
        'scipy',
        'tkinter',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'IPython',
        'notebook',
        'sphinx',
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='tui-llama-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
