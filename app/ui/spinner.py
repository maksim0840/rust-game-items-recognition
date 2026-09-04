"""Индикатор загрузки поверх содержимого.

Показывает, что программа занята, а не зависла. Крутится только если
событийный цикл свободен, поэтому долгую работу нужно резать на порции —
иначе анимация замрёт ровно тогда, когда она нужнее всего.
"""

import os

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QMovie
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

from paths import UI_ASSETS_DIR

SPINNER_GIF = os.path.join(UI_ASSETS_DIR, "loading_circle.gif")

SPINNER_SIZE = 56


class LoadingSpinner(QWidget):
    """Крутящийся кружок с подписью. Прячется, пока не позван."""

    def __init__(self, parent=None, text="Загрузка…", size=SPINNER_SIZE):
        super().__init__(parent)
        self.setObjectName("loadingSpinner")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        # Без этого фон и рамка из стилей не рисуются у голого QWidget,
        # и кружок висел бы прямо поверх карточек без подложки
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        self.icon_label = QLabel(self)
        self.icon_label.setObjectName("spinnerIcon")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setFixedSize(size, size)

        self._movie = QMovie(SPINNER_GIF)
        if self._movie.isValid():
            self._movie.setScaledSize(QSize(size, size))
            self.icon_label.setMovie(self._movie)
        layout.addWidget(self.icon_label, 0, Qt.AlignHCenter)

        self.text_label = QLabel(text, self)
        self.text_label.setObjectName("spinnerText")
        self.text_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.text_label)

        self.hide()

    def set_text(self, text):
        self.text_label.setText(text)

    def start(self):
        if self.isVisible():
            return
        self.show()
        self.raise_()
        if self._movie.isValid():
            self._movie.start()

    def stop(self):
        if self._movie.isValid():
            self._movie.stop()
        self.hide()

    def center_on(self, rect):
        """Ставит индикатор по центру переданной области."""
        size = self.sizeHint()
        self.setGeometry(
            rect.x() + (rect.width() - size.width()) // 2,
            rect.y() + (rect.height() - size.height()) // 2,
            size.width(),
            size.height(),
        )
