# -*- mode: python ; coding: utf-8 -*-
import os
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
    'pystray',
    'pystray._util.win32',
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

def _get_paddle_excludes():
    try:
        spec_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        spec_dir = os.getcwd()
    paddle_dir = os.path.join(spec_dir, '.venv', 'Lib', 'site-packages', 'paddle')
    if not os.path.isdir(paddle_dir):
        return []
    exclude_patterns = [
        'distributed', 'incubate', 'static', 'cuda', 'tensorrt',
        'api_tracer', 'cinn_config', 'cost_model', 'hapi',
        'dataset', 'geometric', 'metric', 'profiler', 'quantization',
        'reader', 'optimizer', 'decomposition', 'sparse', 'pir',
    ]
    excludes = []
    for item in sorted(os.listdir(paddle_dir)):
        dp = os.path.join(paddle_dir, item)
        if os.path.isdir(dp) and os.path.exists(os.path.join(dp, '__init__.py')):
            if not item.startswith('_') and not item.startswith('.'):
                for pattern in exclude_patterns:
                    if pattern in item.lower():
                        excludes.append('paddle.' + item)
                        break
    return excludes


excludes = _get_paddle_excludes()

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