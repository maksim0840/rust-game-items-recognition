"""Пути к ресурсам приложения.

Собраны в одном месте намеренно: модули лежат по подпапкам, и если каждый
будет считать корень от своего __file__, пути разъедутся при любом переносе
файла. Здесь корень вычисляется один раз.

Модель и картинки предметов весят под полгигабайта и в .exe не упаковываются —
папки model и source должны лежать рядом с исполняемым файлом.
"""

import os
import sys

if getattr(sys, "frozen", False):
    # Собранный .exe: __file__ указывал бы внутрь временной папки распаковки,
    # поэтому корнем считаем директорию самого исполняемого файла
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_DIR = os.path.join(APP_DIR, "model")

SOURCE_DIR = os.path.join(APP_DIR, "source")
ITEMS_IMAGES_DIR = os.path.join(SOURCE_DIR, "items")
UI_ASSETS_DIR = os.path.join(SOURCE_DIR, "ui")

APP_ICON = os.path.join(UI_ASSETS_DIR, "logo.ico")


def missing_resources():
    """Папки, без которых программа не запустится. Пустой список — всё на месте."""
    return [path for path in (MODEL_DIR, ITEMS_IMAGES_DIR, UI_ASSETS_DIR)
            if not os.path.isdir(path)]
