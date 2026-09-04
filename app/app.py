"""Точка входа.

Здесь важен порядок первых строк: переменная окружения должна быть выставлена
до загрузки Qt, а onnxruntime — импортирован раньше PyQt5.
"""

import os
import sys

# Одна плотность пикселей на всё приложение. Иначе при переносе окна между
# мониторами с разным масштабом Qt5 пересчитывает геометрию по WM_DPICHANGED
# и ломает раскладку: фиксированные размеры умножаются на коэффициент, окно
# растёт, элементы разъезжаются. Так же поступают Telegram и другие: рисуют
# в одном масштабе, а растягиванием на других мониторах занимается Windows.
# Настоящие пиксели экрана берутся у Windows напрямую — см. system/screen_capture.py
os.environ.setdefault("QT_QPA_PLATFORM", "windows:dpiawareness=1")

# onnxruntime обязан загрузиться раньше PyQt5: PyQt5 добавляет в путь поиска
# DLL свою копию msvc-рантайма (msvcp140.dll и соседние), и onnxruntime,
# импортированный после него, падает на инициализации библиотеки
import onnxruntime  # noqa: F401  (импорт нужен ради порядка загрузки DLL)

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QDialog

from paths import APP_ICON, missing_resources
from system.window_theme import set_app_id
from ui.dialogs import show_error
from ui.settings_window import SettingsDialog
from ui.styles import DARK_QSS

APP_ID = "lootlens"

# По умолчанию квадраты поверх игры не попадают в скриншоты и запись
# экрана — иначе программа увидела бы их при следующем распознавании.
# Для записи ролика запускать с ключом --allow-capture
ALLOW_CAPTURE_FLAG = "--allow-capture"



def main():
    # Все размеры в коде и в стилях считаются в логических пикселях, а Qt
    # умножает их на масштаб монитора. Без этого на экране со 150% интерфейс
    # выглядит иначе, чем на экране со 100%.
    # PassThrough обязателен: иначе Qt5 округляет 1.5 до 2.0 и всё становится
    # заметно крупнее, чем задумано системой.
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Иначе Windows считает окно частью интерпретатора и показывает на
    # панели задач иконку Python
    set_app_id(APP_ID)

    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_QSS)
    app.setWindowIcon(QIcon(APP_ICON))   # достаётся всем окнам разом

    # Модель и картинки в .exe не упакованы, они должны лежать рядом.
    # Проверяем до загрузки данных, иначе вместо понятного сообщения
    # пользователь получит обрыв при чтении первого же файла
    missing = missing_resources()
    if missing:
        show_error(
            None, "LootLens",
            "Не найдены папки с данными.",
            "Они должны лежать рядом с программой:\n\n%s"
            % "\n".join(missing),
        )
        return 1

    allow_capture = ALLOW_CAPTURE_FLAG in sys.argv

    # Импорт здесь, а не наверху: он загружает данные о предметах,
    # а до проверки выше делать это нельзя
    from ui.main_window import MainWindow

    # Настройки и выбор предметов ходят по кругу: из окна предметов можно
    # вернуться назад и настроить всё заново
    while True:
        settings_dialog = SettingsDialog()
        if settings_dialog.exec_() != QDialog.Accepted:
            # Настройки не подтверждены — окно выбора предметов не открываем
            return 0

        window = MainWindow(settings_dialog.settings(),
                            hide_overlay_from_capture=not allow_capture)
        window.show()
        app.exec_()  # вернётся, когда окно предметов закроется

        if not window.reopen_settings:
            return 0


if __name__ == "__main__":
    sys.exit(main())
