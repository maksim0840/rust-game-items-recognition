"""Тёмная тема приложения.

Одна таблица стилей на все окна: её ставит QApplication при запуске, и она
достаётся каждому виджету по objectName. Вынесена отдельно, потому что
занимала две трети точки входа.
"""

import os

from paths import UI_ASSETS_DIR

# В QSS путь всегда через прямые слэши, даже на Windows
CHECK_ICON = os.path.join(UI_ASSETS_DIR, "check.svg").replace("\\", "/")
DASH_ICON = os.path.join(UI_ASSETS_DIR, "dash.svg").replace("\\", "/")

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

#loadingSpinner {
    background-color: rgba(21, 27, 28, 235);
    border: 1px solid #2a3436;
    border-radius: 8px;
}

#loadingSpinner QLabel {
    background-color: transparent;
}

QLabel#spinnerText {
    color: #b7c2bf;
    font-size: 12px;
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

/* Глобальное правило QWidget красит фон и меткам внутри окна сообщения,
   из-за чего вокруг текста и иконки видны тёмные прямоугольники */
QMessageBox QLabel, QMessageBox QFrame {
    background-color: transparent;
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
