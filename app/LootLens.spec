# -*- mode: python ; coding: utf-8 -*-
"""Сборка LootLens.

Модель и картинки предметов в сборку не входят: 
папки model и source должны лежать рядом с готовым exe.

Собирать так (из папки app):
    pyinstaller --noconfirm --clean --distpath . --workpath build LootLens.spec

Готовый LootLens.exe появляется прямо здесь, рядом с папками model и source,
поэтому запускается сразу без копирования данных.
"""

import os

# PyQt5 везёт с собой msvc-рантайм 2019 года (14.26), а onnxruntime собран под
# более новый. При обычном запуске это лечится порядком импорта, но в сборке
# все библиотеки лежат в одной папке, и onnxruntime всё равно подхватывает
# копию от PyQt5 — падает с "DLL load failed ... onnxruntime_pybind11_state".
# Поэтому выкидываем копии PyQt5 и кладём вместо них системные.
RUNTIME_DLLS = [
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "concrt140.dll",
]

SYSTEM32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")


# SPECPATH — папка этого файла, PyInstaller подставляет её сам.
# Через неё пути не зависят от того, откуда запущена сборка
a = Analysis(
    [os.path.join(SPECPATH, "app.py")],
    pathex=[SPECPATH],       # где искать пакеты ui, system, detection
    binaries=[],
    datas=[],                # модель и картинки не упаковываем
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

# --- подмена устаревшего рантайма -------------------------------------------

stale = {name.lower() for name in RUNTIME_DLLS}
kept = [item for item in a.binaries if os.path.basename(item[0]).lower() not in stale]

replaced = []
for name in RUNTIME_DLLS:
    system_copy = os.path.join(SYSTEM32, name)
    if os.path.exists(system_copy):
        kept.append((name, system_copy, "BINARY"))
        replaced.append(name)

print("Заменено библиотек рантайма на системные: %d из %d"
      % (len(replaced), len(RUNTIME_DLLS)))
for name in RUNTIME_DLLS:
    if name not in replaced:
        print("  внимание: %s не найдена в System32, оставлена версия из пакета" % name)

a.binaries = kept

# ----------------------------------------------------------------------------

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="LootLens",
    icon=os.path.join(SPECPATH, "source", "ui", "logo.ico"),
    console=False,           # без окна консоли
    debug=False,
    strip=False,
    upx=False,
    bootloader_ignore_signals=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
