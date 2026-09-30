# -*- coding: utf-8 -*-
"""Ponto de entrada do aplicativo Lista de I/O."""
import sys
from PyQt6.QtWidgets import QApplication

import brand
import theme
from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    theme.apply_theme(app)
    app.setWindowIcon(brand.app_icon())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
