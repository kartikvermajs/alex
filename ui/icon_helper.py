"""Icon generator utility for Alex UI and system tray."""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap


def create_alex_icon(size: int = 64, active: bool = True) -> QIcon:
    """Creates a clean, modern vector-drawn icon for Alex."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Background circle
    rect = QRectF(2, 2, size - 4, size - 4)
    bg_color = QColor(24, 26, 32)
    border_color = QColor(79, 140, 255) if active else QColor(100, 100, 100)

    painter.setBrush(bg_color)
    painter.setPen(border_color)
    painter.drawEllipse(rect)

    # Stylized "A" letter inside
    painter.setPen(QColor(255, 255, 255) if active else QColor(180, 180, 180))
    font = QFont("Segoe UI", int(size * 0.45), QFont.Bold)
    painter.setFont(font)
    painter.drawText(rect, Qt.AlignCenter, "A")

    # Small status indicator dot
    dot_size = size * 0.22
    dot_rect = QRectF(size - dot_size - 2, size - dot_size - 2, dot_size, dot_size)
    dot_color = QColor(46, 204, 113) if active else QColor(231, 76, 60)
    painter.setBrush(dot_color)
    painter.setPen(QColor(24, 26, 32))
    painter.drawEllipse(dot_rect)

    painter.end()
    return QIcon(pixmap)
