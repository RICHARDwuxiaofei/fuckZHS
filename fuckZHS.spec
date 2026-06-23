# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all, collect_submodules

# Collect all data and submodules for openai and its core dependencies
openai_deps = collect_all('openai')
httpx_deps = collect_all('httpx')
pydantic_deps = collect_all('pydantic')
anyio_deps = collect_all('anyio')

# Combine collected datas and binaries
extra_datas = []
extra_binaries = []
for deps in (openai_deps, httpx_deps, pydantic_deps, anyio_deps):
    extra_datas.extend(deps[0])   # datas
    extra_binaries.extend(deps[1])  # binaries

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('meta.json', '.')] + extra_datas,
    hiddenimports=[
        # Core modules
        'PIL', 'PIL.Image', 'PIL.ImageOps',
        'Crypto', 'Crypto.Cipher',
        'tiktoken',
        'requests',
        # openai & friends (explicit as fallback)
        'openai',
        'openai._compat',
        'openai.lib',
        'openai.lib._parsers',
        'openai.resources',
        'openai.resources.models',
        'openai.resources.chat',
        'openai.resources.completions',
        'httpx',
        'httpx._config',
        'httpx._client',
        'httpx._transports',
        'httpcore',
        'httpcore._async',
        'httpcore._sync',
        'anyio',
        'anyio._backends',
        'anyio._backends._asyncio',
        'anyio.streams',
        'sniffio',
        'idna',
        'jiter',
        'pydantic',
        'pydantic_core',
        # Crypto submodules
        'Crypto.Cipher.AES',
        'Crypto.Util.Padding',
        'Crypto.Util._raw_api',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Add extra binaries from collected packages
a.binaries += extra_binaries

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='fuckZHS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='fuckZHS',
)