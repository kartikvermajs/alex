# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import sys
import os

block_cipher = None

added_files = [
    ('models/vosk-model-small-en-us', 'models/vosk-model-small-en-us'),
    ('models/kokoro', 'models/kokoro'),
]

# Collect model assets and loaders
added_files += collect_data_files('faster_whisper')
added_files += collect_data_files('ctranslate2')
added_files += collect_data_files('kokoro_onnx')
added_files += collect_data_files('espeakng_loader')

hidden_imports = [
    'kokoro_onnx',
    'espeakng_loader',
    'faster_whisper',
    'ctranslate2',
    'vosk',
    'sounddevice',
    'soundfile',
    'pyttsx3',
    'pyttsx3.drivers',
    'pyttsx3.drivers.sapi5',
    'comtypes',
    'psutil',
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'win32com',
    'win32com.client',
    'pythoncom',
]

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
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
    name='Alex',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Alex',
)
