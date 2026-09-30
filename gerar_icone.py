# -*- coding: utf-8 -*-
"""Gera app.ico (identidade Autolinx) a partir de brand.app_icon(), para uso no PyInstaller."""
import os
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PyQt6.QtWidgets import QApplication

import brand

TAMANHOS = (16, 24, 32, 48, 64, 128, 256)


def gerar_icone(destino: Path) -> Path:
    app = QApplication.instance() or QApplication([])
    icone = brand.app_icon()

    tmp = destino.parent / "_icone_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    quadros = []
    for lado in TAMANHOS:
        arq = tmp / f"{lado}.png"
        icone.pixmap(lado, lado).save(str(arq), "PNG")
        quadros.append(Image.open(arq).convert("RGBA"))

    maior = max(quadros, key=lambda im: im.width)
    maior.save(destino, format="ICO", sizes=[(q.width, q.height) for q in quadros])
    shutil.rmtree(tmp, ignore_errors=True)
    return destino


if __name__ == "__main__":
    out = Path(__file__).parent / "app.ico"
    gerar_icone(out)
    print("Salvo em", out)
