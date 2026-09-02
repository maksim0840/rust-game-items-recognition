import os
import sys

# Одна плотность пикселей на всё приложение. Иначе при переносе окна между
# мониторами с разным масштабом Qt5 пересчитывает геометрию по WM_DPICHANGED
# и ломает раскладку: фиксированные размеры умножаются на коэффициент, окно
# растёт, элементы разъезжаются. Так же поступают Telegram и другие: рисуют
# в одном масштабе, а растягиванием на других мониторах занимается Windows.
# Настоящие пиксели экрана берутся у Windows напрямую — см. screen_capture.py
os.environ.setdefault("QT_QPA_PLATFORM", "windows:dpiawareness=1")

# onnxruntime обязан загрузиться раньше PyQt5: PyQt5 добавляет в путь поиска
# DLL свою копию msvc-рантайма (msvcp140.dll и соседние), и onnxruntime,
# импортированный после него, падает на инициализации библиотеки
import onnxruntime  # noqa: F401  (импорт нужен ради порядка загрузки DLL)

from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtWidgets import QApplication, QDialog, QMainWindow

from game_overlay import GameOverlay
from items_browser import ItemsBrowser
from monitors import QtMonitors
from overlay import Overlay
from recognition import InventoryGrid, InventoryScanner, ItemRecognitionModel
from rust_items import distribute_items_into_categories, items
from scan_panel import ScanPanel
from settings_window import SettingsDialog

APP_DIR = os.path.dirname(os.path.abspath(__file__))
# В QSS путь всегда через прямые слэши, даже на Windows
CHECK_ICON = os.path.join(APP_DIR, "source", "ui", "check.svg").replace("\\", "/")
DASH_ICON = os.path.join(APP_DIR, "source", "ui", "dash.svg").replace("\\", "/")

DARK_QSS = """
QWidget {
    background-color: #151b1c;
    color: #c9d1cf;
    font-family: "Segoe UI", Arial, sans-serif;
}

#toolbar {
    background-color: #1b2325;
    border-bottom: 1px solid #0e1314;
}

#tabsBar {
    background-color: transparent;
}

QPushButton#categoryTab {
    background-color: #2a3436;
    color: #b7c2bf;
    border: none;
    border-radius: 4px;
    padding: 11px 21px;
    font-size: 16px;
    font-weight: 600;
    letter-spacing: 1.5px;
}

QPushButton#categoryTab:hover {
    background-color: #35413f;
    color: #e4ece9;
}

QPushButton#categoryTab:checked {
    background-color: #6d8f33;
    color: #f2f7e8;
}

QLineEdit#search {
    background-color: #2a3436;
    border: 1px solid #0e1314;
    border-radius: 3px;
    padding: 6px 10px;
    color: #e4ece9;
    selection-background-color: #6d8f33;
}

QLineEdit#search:focus {
    border: 1px solid #6d8f33;
}

#actionBar {
    background-color: #18201f;
    border-bottom: 1px solid #0e1314;
}

QPushButton#actionButton {
    background-color: #2a3436;
    color: #cfd8d6;
    border: 1px solid #0e1314;
    border-radius: 3px;
    padding: 6px 12px;
    font-size: 12px;
}

QPushButton#actionButton:hover {
    background-color: #35413f;
    color: #e4ece9;
    border: 1px solid #6d8f33;
}

QPushButton#settingsButton {
    background-color: #2a3436;
    color: #b7c2bf;
    border: 1px solid #0e1314;
    border-radius: 4px;
    padding: 9px 14px;
    font-size: 13px;
}

QPushButton#settingsButton:hover {
    background-color: #35413f;
    color: #e4ece9;
    border: 1px solid #6d8f33;
}

QPushButton#settingsButton:pressed {
    background-color: #6d8f33;
    color: #f2f7e8;
}

QPushButton#actionButton:pressed {
    background-color: #6d8f33;
    color: #f2f7e8;
}

QLabel#counter {
    color: #6f7b78;
    font-size: 12px;
    padding-right: 6px;
}

QCheckBox#selectAllCheck {
    color: #cfd8d6;
    font-size: 12px;
    spacing: 7px;
}

QCheckBox#selectAllCheck:disabled {
    color: #56605e;
}

QCheckBox#selectAllCheck::indicator {
    width: 16px;
    height: 16px;
    border: 2px solid #556260;
    border-radius: 3px;
    background-color: #2a3436;
}

QCheckBox#selectAllCheck::indicator:hover {
    border: 2px solid #6d8f33;
}

QCheckBox#selectAllCheck::indicator:checked {
    background-color: #6d8f33;
    border: 2px solid #9ec24a;
    image: url(__CHECK_ICON__);
}

/* Выделена лишь часть показанных предметов */
QCheckBox#selectAllCheck::indicator:indeterminate {
    background-color: #46592a;
    border: 2px solid #6d8f33;
    image: url(__DASH_ICON__);
}

QPushButton#selectButton {
    background-color: #6d8f33;
    color: #f2f7e8;
    border: none;
    border-radius: 3px;
    padding: 6px 16px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#selectButton:hover {
    background-color: #7ea23c;
}

QPushButton#selectButton:pressed {
    background-color: #5c7a2b;
}

QLabel#itemCheck {
    background-color: rgba(10, 14, 15, 180);
    border: 2px solid #556260;
    border-radius: 4px;
    color: transparent;
    font-size: 15px;
    font-weight: 700;
}

QLabel#itemCheck[selected="true"] {
    background-color: #6d8f33;
    border: 2px solid #9ec24a;
    color: #f2f7e8;
}

QLabel#emptyLabel {
    color: #6f7b78;
    font-size: 14px;
}

#itemsGrid {
    background-color: #151b1c;
}

QFrame#itemCard {
    background-color: #1d2527;
    border: 1px solid transparent;
    border-radius: 4px;
}

QFrame#itemCard:hover {
    background-color: #283335;
    border: 1px solid #6d8f33;
}

QFrame#itemCard[selected="true"] {
    background-color: #26301f;
    border: 1px solid #6d8f33;
}

QFrame#itemCard[selected="true"]:hover {
    background-color: #2f3c25;
    border: 1px solid #9ec24a;
}

QFrame#itemCard QLabel {
    background-color: transparent;
}

QLabel#itemName {
    color: #b7c2bf;
}

QScrollBar:vertical {
    background: #151b1c;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #3a4749;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #6d8f33;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: #3a4749;
    border-radius: 4px;
    min-width: 30px;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

#settingsDialog {
    background-color: #151b1c;
}

QLabel#settingsTitle {
    color: #e4ece9;
    font-size: 19px;
    font-weight: 600;
}

QLabel#settingsHint {
    color: #8b9793;
    font-size: 12px;
}

QLabel#settingsSection {
    color: #9ec24a;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 1px;
    padding-top: 6px;
}

QLabel#settingsLabel {
    color: #cfd8d6;
    font-size: 13px;
}

QLabel#settingsPath {
    color: #66716e;
    font-size: 11px;
    font-style: italic;
}

QLabel#settingsTimes {
    color: #8b9793;
    font-size: 14px;
}

QSpinBox#settingsInput, QDoubleSpinBox#settingsInput {
    background-color: #2a3436;
    border: 1px solid #0e1314;
    border-radius: 3px;
    padding: 6px 8px;
    min-width: 92px;
    color: #e4ece9;
    font-size: 13px;
    selection-background-color: #6d8f33;
}

QSpinBox#settingsInput:focus, QDoubleSpinBox#settingsInput:focus {
    border: 1px solid #6d8f33;
}

/* Разрешение не вводится, а показывается: значение должно оставаться
   читаемым, но поле не должно выглядеть редактируемым */
QSpinBox#settingsInput:disabled, QDoubleSpinBox#settingsInput:disabled {
    background-color: #212a2b;
    border: 1px solid #0e1314;
    color: #8b9793;
}

QComboBox#settingsCombo {
    background-color: #2a3436;
    border: 1px solid #0e1314;
    border-radius: 3px;
    padding: 6px 8px;
    color: #e4ece9;
    font-size: 13px;
}

QComboBox#settingsCombo:hover {
    border: 1px solid #6d8f33;
}

QComboBox#settingsCombo::drop-down {
    border: none;
    width: 20px;
}

QComboBox#settingsCombo QAbstractItemView {
    background-color: #1b2325;
    border: 1px solid #6d8f33;
    color: #cfd8d6;
    selection-background-color: #6d8f33;
    selection-color: #f2f7e8;
    outline: none;
}

QCheckBox#settingsCheck {
    color: #cfd8d6;
    font-size: 13px;
    spacing: 8px;
}

/* Режим не выбирается, поэтому выключенная галочка выглядит так же,
   как включённая — иначе она читалась бы как «неактивно» */
QCheckBox#settingsCheck:disabled {
    color: #cfd8d6;
}

QCheckBox#settingsCheck::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #556260;
    border-radius: 3px;
    background-color: #2a3436;
}

QCheckBox#settingsCheck::indicator:checked,
QCheckBox#settingsCheck::indicator:checked:disabled {
    background-color: #6d8f33;
    border: 2px solid #9ec24a;
    image: url(__CHECK_ICON__);
}

QLabel#settingsNote {
    color: #b8a05c;
    font-size: 11px;
}

QPushButton#confirmButton {
    background-color: #6d8f33;
    color: #f2f7e8;
    border: none;
    border-radius: 4px;
    padding: 11px 18px;
    font-size: 14px;
    font-weight: 600;
}

QPushButton#confirmButton:hover {
    background-color: #7ea23c;
}

QPushButton#confirmButton:pressed {
    background-color: #5c7a2b;
}

/* Панель лежит на своей подложке, поэтому её содержимое фон не рисует */
#scanPanel, #scanPanel QLabel, #scanPanel QCheckBox {
    background-color: transparent;
}

QPushButton#panelClose {
    background-color: transparent;
    color: #6f7b78;
    border: none;
    border-radius: 3px;
    font-size: 15px;
    font-weight: 600;
}

QPushButton#panelClose:hover {
    background-color: #2a3436;
    color: #e4ece9;
}

QPushButton#panelClose:pressed {
    background-color: #6d8f33;
    color: #f2f7e8;
}

QLabel#scanTitle {
    color: #e4ece9;
    font-size: 18px;
    font-weight: 600;
}

QLabel#scanSection {
    color: #9ec24a;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    padding-top: 4px;
}

QLabel#scanLabel {
    color: #cfd8d6;
    font-size: 13px;
}

QLabel#scanStatus {
    color: #8b9793;
    font-size: 12px;
    font-style: italic;
}

QFrame#scanSeparator {
    color: #2a3436;
    max-height: 1px;
}

QCheckBox#scanCheck {
    color: #cfd8d6;
    font-size: 13px;
    spacing: 8px;
}

QCheckBox#scanCheck::indicator {
    width: 17px;
    height: 17px;
    border: 2px solid #556260;
    border-radius: 3px;
    background-color: #2a3436;
}

QCheckBox#scanCheck::indicator:hover {
    border: 2px solid #6d8f33;
}

QCheckBox#scanCheck::indicator:checked {
    background-color: #6d8f33;
    border: 2px solid #9ec24a;
    image: url(__CHECK_ICON__);
}

QPushButton#bindButton {
    background-color: #2a3436;
    color: #e4ece9;
    border: 1px solid #0e1314;
    border-radius: 3px;
    padding: 7px 10px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton#bindButton:hover {
    border: 1px solid #6d8f33;
}

/* Ждём нажатия клавиши */
QPushButton#bindButton[capturing="true"] {
    background-color: #46592a;
    border: 1px solid #9ec24a;
    color: #f2f7e8;
}

QPushButton#bindReset {
    background-color: transparent;
    color: #6f7b78;
    border: none;
    font-size: 14px;
}

QPushButton#bindReset:hover {
    color: #e4ece9;
}

QLabel#resultMatched {
    color: #9ec24a;
    font-size: 15px;
    font-weight: 600;
}

QLabel#resultUndefined {
    color: #c2a04a;
    font-size: 15px;
    font-weight: 600;
}

QLabel#resultNotMatched {
    color: #b7c2bf;
    font-size: 15px;
    font-weight: 600;
}

#overlay {
    background: transparent;
}

QFrame#overlayPanel {
    background-color: #1b2325;
    border: 1px solid #6d8f33;
    border-radius: 6px;
}

QMessageBox {
    background-color: #1b2325;
}

QMessageBox QLabel {
    color: #e4ece9;
    font-size: 13px;
}

QMessageBox QPushButton {
    background-color: #6d8f33;
    color: #f2f7e8;
    border: none;
    border-radius: 3px;
    padding: 7px 20px;
    font-size: 13px;
    font-weight: 600;
    min-width: 80px;
}

QMessageBox QPushButton:hover {
    background-color: #7ea23c;
}

QToolTip {
    background-color: #1b2325;
    color: #e4ece9;
    border: 1px solid #6d8f33;
    padding: 4px;
}
""".replace("__CHECK_ICON__", CHECK_ICON).replace("__DASH_ICON__", DASH_ICON)


class MainWindow(QMainWindow):
    def __init__(self, game_settings=None):
        super().__init__()
        self.setWindowTitle("Rust Items Detection")
        self.resize(1200, 760)

        # Настройки игры, подтверждённые в стартовом окне
        self.game_settings = game_settings or {}

        # Ставится, когда пользователь просит вернуться к настройкам:
        # main() смотрит на него после закрытия окна
        self.reopen_settings = False

        # Координаты последнего распознавания
        self.last_scan = None

        # Размер окна в логических пикселях. При переезде на монитор с другим
        # масштабом Qt пересчитывает геометрию по-своему, и окно скачет —
        # поэтому запоминаем задуманный размер и восстанавливаем его
        self._logical_size = self.size()
        self._logical_ratio = self.devicePixelRatioF()
        self._adjusting_geometry = False
        self._watched_window = None

        categories = distribute_items_into_categories(items)

        self.items_browser = ItemsBrowser(categories, self)
        self.items_browser.item_clicked.connect(self.on_item_clicked)
        self.setCentralWidget(self.items_browser)

        # Полупрозрачный слой поверх окна: скрыт, пока не вызван show_overlay()
        self.overlay = Overlay(self)
        self.items_browser.select_requested.connect(self.overlay.show_overlay)
        self.items_browser.settings_requested.connect(self.back_to_settings)

        # Панель управления распознаванием живёт внутри полупрозрачного слоя
        self.scan_panel = ScanPanel(self.overlay)
        self.scan_panel.scan_requested.connect(self.run_scan)
        self.scan_panel.clear_requested.connect(self.clear_scan)
        self.scan_panel.display_changed.connect(self.apply_display_flags)
        self.scan_panel.close_requested.connect(self.overlay.hide_overlay)
        self.overlay.set_content(self.scan_panel)

        # Прозрачное окно поверх игры: живёт ровно столько же, сколько панель
        self.game_overlay = GameOverlay(
            QtMonitors.screen_for(self.game_settings.get("screen_name"))
        )
        self.overlay.opened.connect(self.game_overlay.show_overlay)
        self.overlay.closed.connect(self.game_overlay.hide_overlay)

        # Модель весит 112 МБ, поэтому создаём сканер при первом запуске,
        # а не при открытии окна
        self.scanner = None

    def on_item_clicked(self, label, item):
        # TODO: обработка выбора предмета
        pass

    def _ensure_scanner(self):
        if self.scanner is None:
            self.scan_panel.set_status("Загружается модель распознавания…")
            QApplication.processEvents()
            self.scanner = InventoryScanner.from_settings(
                InventoryGrid(), ItemRecognitionModel(), self.game_settings
            )
        return self.scanner

    def run_scan(self):
        """Снимает экран и считает, сколько выбранных предметов на нём нашлось."""
        labels = set(self.items_browser.selected_labels())
        if not labels:
            self.scan_panel.set_status(
                "Не выбрано ни одного предмета — закройте панель и отметьте нужные"
            )
            return

        # Старые квадраты убираем до снимка: они и устарели, и не должны
        # попасть в кадр, даже если исключение из захвата не сработало
        self.clear_scan()
        QApplication.processEvents()

        try:
            scanner = self._ensure_scanner()
            self.scan_panel.set_status("Распознавание…")
            QApplication.processEvents()

            screenshot = scanner.make_screenshot()
            matched, undefined, not_matched = scanner.find_classes_on_screenshot(
                screenshot, labels
            )
        except Exception as exc:
            # Съехавшее разрешение, отключённый монитор, сбой модели — что угодно
            # из этого не должно ронять приложение прямо во время игры
            self.scan_panel.set_status(str(exc))
            return

        self.last_scan = (matched, undefined, not_matched)
        self.scan_panel.set_results(len(matched), len(undefined), len(not_matched))

        self.apply_display_flags()
        self.game_overlay.set_boxes(matched, undefined, not_matched)

    def clear_scan(self):
        self.last_scan = None
        self.scan_panel.clear_results()
        self.game_overlay.clear_boxes()

    def apply_display_flags(self):
        """Флажки панели управляют и строками счётчиков, и квадратами на экране."""
        matched, undefined, not_matched = self.scan_panel.display_flags()
        self.game_overlay.set_visible_groups(matched, undefined, not_matched)

    # --- размер окна при переезде между мониторами ------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        handle = self.windowHandle()
        if handle is not None and handle is not self._watched_window:
            self._watched_window = handle
            handle.screenChanged.connect(self._on_screen_changed)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Запоминаем только то, что изменил пользователь. Пересчёт из-за
        # переезда на монитор с другим масштабом приходит с новым DPR —
        # такой размер запоминать нельзя, иначе он подменит задуманный
        if self._adjusting_geometry or self.devicePixelRatioF() != self._logical_ratio:
            return
        self._logical_size = event.size()

    def _on_screen_changed(self, screen):
        """Возвращает окну прежний логический размер на новом мониторе.

        В момент сигнала размер ещё старый — Qt пересчитает его сразу после.
        Поэтому не правим ничего здесь, а становимся в очередь следом за ним.
        """
        target = self._logical_size
        if screen is not None:
            # Не больше, чем помещается на новом экране
            available = screen.availableGeometry().size()
            target = QSize(
                min(target.width(), available.width()),
                min(target.height(), available.height()),
            )

        self._adjusting_geometry = True
        QTimer.singleShot(0, lambda: self._finish_geometry_fix(target))

    def _finish_geometry_fix(self, target):
        if self.size() != target:
            self.resize(target)
        self._logical_size = target
        self._logical_ratio = self.devicePixelRatioF()
        self._adjusting_geometry = False

    def back_to_settings(self):
        """Закрывает окно; main() увидит флаг и снова покажет настройки."""
        self.reopen_settings = True
        self.close()


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

    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_QSS)

    # Настройки и выбор предметов ходят по кругу: из окна предметов можно
    # вернуться назад и настроить всё заново
    while True:
        settings_dialog = SettingsDialog()
        if settings_dialog.exec_() != QDialog.Accepted:
            # Настройки не подтверждены — окно выбора предметов не открываем
            return 0

        window = MainWindow(settings_dialog.settings())
        window.show()
        app.exec_()  # вернётся, когда окно предметов закроется

        if not window.reopen_settings:
            return 0


if __name__ == "__main__":
    sys.exit(main())
