#!/usr/bin/env python3
"""Build ``app.ico`` from the pharmacy logo.

Windows wants one .ico holding several sizes: 16 px for the taskbar's small
icons up to 256 px for the large-icon view. Qt's image writer only emits one
size per file, so the ICO container is assembled here — each entry is a PNG,
which Windows has accepted since Vista.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter

SIZES = (16, 24, 32, 48, 64, 128, 256)


def png_bytes(image: QImage, size: int) -> bytes:
    scaled = image.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    canvas = QImage(size, size, QImage.Format_ARGB32)
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    painter.drawImage((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
    painter.end()

    # The QByteArray must outlive the QBuffer that writes into it.
    storage = QByteArray()
    buffer = QBuffer(storage)
    buffer.open(QBuffer.WriteOnly)
    canvas.save(buffer, "PNG")
    buffer.close()
    return bytes(storage)


_app: QGuiApplication | None = None


def build(source: Path, destination: Path) -> Path:
    global _app  # a Qt application has to exist — and stay alive — to paint
    _app = QGuiApplication.instance() or QGuiApplication(["make_icon"])
    image = QImage(str(source))
    if image.isNull():
        raise SystemExit(f"Cannot read {source}")

    frames = [(size, png_bytes(image, size)) for size in SIZES]
    header = struct.pack("<HHH", 0, 1, len(frames))
    directory = b""
    offset = len(header) + 16 * len(frames)
    payload = b""
    for size, data in frames:
        directory += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,
            0 if size >= 256 else size,
            0,
            0,
            1,
            32,
            len(data),
            offset,
        )
        payload += data
        offset += len(data)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(header + directory + payload)
    return destination


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    logo = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        root.parent / "pharmacy_desktop" / "resources" / "pharmacy-logo.png"
    )
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else root / "app.ico"
    print("Wrote", build(logo, output))
