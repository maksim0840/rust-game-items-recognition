"""Окна сообщений в оформлении приложения.

Стандартный QMessageBox приходит со светлой системной рамкой и не знает про
тёмную тему, поэтому собираем его здесь: разом ставим оформление, тёмную рамку
и человеческую подпись на кнопке.
"""

from PyQt5.QtWidgets import QMessageBox

from system.window_theme import apply_dark_title_bar


def _build(parent, icon, title, text, informative, button_text):
    box = QMessageBox(parent)
    box.setObjectName("appMessage")
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(text)
    if informative:
        box.setInformativeText(informative)
    box.setStandardButtons(QMessageBox.Ok)
    box.button(QMessageBox.Ok).setText(button_text)

    # winId() создаёт нативное окно — без него красить рамку нечему
    box.winId()
    apply_dark_title_bar(box)
    return box


def show_warning(parent, title, text, informative="", button_text="Понятно"):
    return _build(parent, QMessageBox.Warning, title, text,
                  informative, button_text).exec_()


def show_error(parent, title, text, informative="", button_text="OK"):
    return _build(parent, QMessageBox.Critical, title, text,
                  informative, button_text).exec_()
