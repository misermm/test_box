# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('.venv/Lib/site-packages/paddle/libs', 'paddle/libs'), ('models', 'models')]
binaries = []
hiddenimports = [
    'image_to_pdf',
    'file_splitter',
    'zip_encoder',
    'generate_file',
    'generate_text',
    'generate_person',
    'url_codec',
    'http_client',
    'json_fmt',
]
tmp_ret = collect_all('PIL')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('cv2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pyclipper')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('shapely')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('paddlex')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

excludes = [
    'paddle.distributed',
    'paddle.incubate',
    'paddle.static',
    'paddle.cuda',
    'paddle.tensorrt',
]

upx_exclude = [
    'common.dll', 'libblas.dll', 'libgfortran-3.dll', 'libiomp5md.dll',
    'liblapack.dll', 'libquadmath-0.dll', 'mkldnn.dll', 'mklml.dll',
    'phi.dll', 'warpctc.dll', 'warprnnt.dll',
]


a = Analysis(
    ['toolbox.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
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
    name='TestToolbox',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=upx_exclude,
    runtime_tmpdir='cache',
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version.txt',
    icon=['icon.ico'],
)