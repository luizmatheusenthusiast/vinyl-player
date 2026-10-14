"""Ícones desenhados em código (claros, nítidos em qualquer tamanho e iguais no Windows e no Ubuntu)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

KINDS = (
    "play", "pause", "prev", "next", "rewind", "forward",
    "shuffle", "repeat", "repeat_one", "close", "restore",
)


def _poly(*points: tuple[float, float]) -> QPolygonF:
    return QPolygonF([QPointF(x, y) for x, y in points])


def _line_pen(color: QColor, width: float = 2.0) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def make_icon(kind: str, color: str = "#f2f2f2", on_color: str | None = None, size: int = 48) -> QIcon:
    """kind: play, pause, prev, next, rewind, forward, shuffle, repeat, repeat_one, close, restore.

    `color` é a cor normal; `on_color` (opcional) é a cor quando o botão está aceso (marcado).
    """
    icon = QIcon(_pixmap(kind, color, size))
    if on_color:
        icon.addPixmap(_pixmap(kind, on_color, size), QIcon.Mode.Normal, QIcon.State.On)
    return icon


def _pixmap(kind: str, color: str, size: int) -> QPixmap:
    if kind not in KINDS:
        raise ValueError(f"ícone desconhecido: {kind}")

    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 24.0, size / 24.0)  # desenhamos numa grade de 24x24
    paint = QColor(color)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(paint)

    if kind == "play":
        p.drawPolygon(_poly((8, 5), (8, 19), (19, 12)))
    elif kind == "pause":
        p.drawRoundedRect(QRectF(6, 5, 4, 14), 1, 1)
        p.drawRoundedRect(QRectF(14, 5, 4, 14), 1, 1)
    elif kind == "prev":
        p.drawRoundedRect(QRectF(5, 5, 2.5, 14), 1, 1)
        p.drawPolygon(_poly((19, 5), (19, 19), (8.5, 12)))
    elif kind == "next":
        p.drawPolygon(_poly((5, 5), (5, 19), (15.5, 12)))
        p.drawRoundedRect(QRectF(16.5, 5, 2.5, 14), 1, 1)
    elif kind == "rewind":  # ◀◀
        p.drawPolygon(_poly((12, 6), (12, 18), (3.5, 12)))
        p.drawPolygon(_poly((20.5, 6), (20.5, 18), (12, 12)))
    elif kind == "forward":  # ▶▶
        p.drawPolygon(_poly((3.5, 6), (3.5, 18), (12, 12)))
        p.drawPolygon(_poly((12, 6), (12, 18), (20.5, 12)))
    elif kind == "shuffle":  # duas setas que se cruzam
        p.setPen(_line_pen(paint))
        p.setBrush(Qt.BrushStyle.NoBrush)
        down = QPainterPath()
        down.moveTo(3.5, 7)
        down.lineTo(8, 7)
        down.cubicTo(13, 7, 11, 17, 16, 17)
        down.lineTo(17.5, 17)
        up = QPainterPath()
        up.moveTo(3.5, 17)
        up.lineTo(8, 17)
        up.cubicTo(13, 17, 11, 7, 16, 7)
        up.lineTo(17.5, 7)
        p.drawPath(down)
        p.drawPath(up)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(paint)
        p.drawPolygon(_poly((16.5, 13.5), (16.5, 20.5), (21.5, 17)))
        p.drawPolygon(_poly((16.5, 3.5), (16.5, 10.5), (21.5, 7)))
    elif kind in ("repeat", "repeat_one"):  # laço com duas setas
        p.setPen(_line_pen(paint))
        p.setBrush(Qt.BrushStyle.NoBrush)
        top = QPainterPath()
        top.moveTo(4.5, 13)
        top.lineTo(4.5, 11)
        top.quadTo(4.5, 7, 8.5, 7)
        top.lineTo(15.5, 7)
        bottom = QPainterPath()
        bottom.moveTo(19.5, 11)
        bottom.lineTo(19.5, 13)
        bottom.quadTo(19.5, 17, 15.5, 17)
        bottom.lineTo(8.5, 17)
        p.drawPath(top)
        p.drawPath(bottom)
        if kind == "repeat_one":  # o numerozinho "1" no meio
            p.setPen(_line_pen(paint, 1.8))
            p.drawLine(QPointF(12, 9.8), QPointF(12, 14.2))
            p.drawLine(QPointF(10.4, 11.3), QPointF(12, 9.8))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(paint)
        p.drawPolygon(_poly((15.2, 4), (15.2, 10), (20, 7)))
        p.drawPolygon(_poly((8.8, 14), (8.8, 20), (4, 17)))
    elif kind == "close":
        p.setPen(_line_pen(paint, 2.2))
        p.drawLine(QPointF(7, 7), QPointF(17, 17))
        p.drawLine(QPointF(17, 7), QPointF(7, 17))
    elif kind == "restore":
        p.setPen(_line_pen(paint))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(5.5, 6.5, 13, 11), 2, 2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(paint)
        p.drawRect(QRectF(5.5, 6.5, 13, 3))  # barra de título da "janela"

    p.end()
    return pix
