"""Cenário em volta da vitrola: estrelas, lua, sol neon, raios art déco, xícara, planta e planeta.

Tudo é desenhado em código (sem imagens), então acompanha o tamanho da janela.
`draw_backdrop` desenha o fundo, em coordenadas da janela; `draw_props` desenha os objetos
que ficam atrás da base, em coordenadas da vitrola (origem no centro do disco).
"""

from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainterPath, QPen, QPolygonF

from themes import Theme


def qcolor(hex_color: str, alpha: int = 255) -> QColor:
    color = QColor(hex_color)
    color.setAlpha(alpha)
    return color


# ---------------------------------------------------------------- fundo (coordenadas da janela)
def draw_backdrop(p, theme: Theme, width: float, height: float, r: float,
                  ox: float, oy: float, plinth_top: float):
    """`ox, oy` = onde está o centro do disco na janela; `plinth_top` = altura do tampo (relativa a oy)."""
    kind = theme.backdrop
    if not kind:
        return
    sky = oy + plinth_top - 2  # altura livre entre o topo da janela e a base
    if sky < 0.2 * r:
        return
    center_x = ox + 0.2 * r    # meio da base
    p.setPen(Qt.PenStyle.NoPen)

    if kind in ("stars", "moon"):
        _stars(p, theme, width, sky)
        if kind == "moon":
            _moon(p, theme, ox - 0.35 * r, sky, r)
    elif kind == "sun":
        _sun(p, theme, center_x, oy + plinth_top + 0.05 * r, sky, r)
    elif kind == "sunburst":
        _sunburst(p, theme, center_x, oy + plinth_top + 0.10 * r, sky, r)


def _stars(p, theme, width, sky):
    rng = random.Random(7)
    for _ in range(int(width * sky / 2200)):
        x, y = rng.uniform(0, width), rng.uniform(0, sky)
        size = rng.choice((0.7, 0.9, 1.2, 1.6))
        p.setBrush(qcolor(theme.text, rng.randint(70, 230)))
        p.drawEllipse(QPointF(x, y), size, size)


def _moon(p, theme, x, sky, r):
    radius = min(0.2 * r, sky * 0.3)
    y = sky * 0.42
    p.setBrush(qcolor("#f6e8c8"))
    p.drawEllipse(QPointF(x, y), radius, radius)
    p.setBrush(qcolor(theme.bg))  # a "mordida" que faz o formato de lua crescente
    p.drawEllipse(QPointF(x + 0.45 * radius, y - 0.2 * radius), 0.9 * radius, 0.9 * radius)


def _sun(p, theme, cx, cy, sky, r):
    radius = min(0.62 * r, sky + 0.05 * r)
    if radius < 0.25 * r:
        return
    p.setBrush(qcolor(theme.accent, 34))                       # brilho em volta
    p.drawEllipse(QPointF(cx, cy), radius * 1.2, radius * 1.2)

    gradient = QLinearGradient(QPointF(cx, cy - radius), QPointF(cx, cy + radius))
    gradient.setColorAt(0.0, qcolor("#ffe36e"))
    gradient.setColorAt(0.55, qcolor("#ff6a9a"))
    gradient.setColorAt(1.0, qcolor(theme.accent))
    p.setBrush(QBrush(gradient))
    p.drawEllipse(QPointF(cx, cy), radius, radius)

    p.setBrush(qcolor(theme.bg))                                # listras do sol
    for i in range(5):
        y = cy - radius * (0.52 - 0.13 * i)
        p.drawRect(QRectF(cx - radius, y, 2 * radius, radius * (0.03 + 0.022 * i)))


def _sunburst(p, theme, cx, cy, sky, r):
    radius = min(0.9 * r, sky + 0.1 * r)
    if radius < 0.25 * r:
        return
    p.setBrush(qcolor(theme.accent, 40))                        # raios (leque)
    for k in range(0, 12, 2):
        start = -180 + k * 15
        points = [QPointF(cx, cy)]
        steps = 6
        for s in range(steps + 1):
            a = math.radians(start + 15 * s / steps)
            points.append(QPointF(cx + radius * math.cos(a), cy + radius * math.sin(a)))
        p.drawPolygon(QPolygonF(points))

    p.setBrush(Qt.BrushStyle.NoBrush)                           # arcos
    for factor, alpha in ((0.34, 120), (0.5, 80)):
        p.setPen(QPen(qcolor(theme.accent, alpha), max(1.0, 0.012 * r)))
        p.drawEllipse(QPointF(cx, cy), radius * factor, radius * factor)
    p.setPen(Qt.PenStyle.NoPen)


# ---------------------------------------------------------------- objetos (coordenadas da vitrola)
def draw_props(p, theme: Theme, r: float, top: float):
    """Objetos em cima da mesa, atrás da base. `top` = y do tampo da base."""
    p.setPen(Qt.PenStyle.NoPen)
    for kind in (k.strip() for k in theme.props.split(",")):
        if kind == "mug":
            _mug(p, theme, 1.45 * r, top + 0.05 * r, r)
        elif kind == "plant":
            _plant(p, -1.08 * r, top + 0.05 * r, r)
        elif kind == "planet":
            _planet(p, theme, 1.25 * r, top - 0.26 * r, r)


def _mug(p, theme, x, base, r):
    p.setPen(QPen(qcolor(theme.text, 95), max(1.5, 0.018 * r), Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap))                     # fumaça
    p.setBrush(Qt.BrushStyle.NoBrush)
    for dx in (-0.06 * r, 0.0, 0.06 * r):
        steam = QPainterPath()
        steam.moveTo(x + dx, base - 0.36 * r)
        steam.cubicTo(x + dx - 0.05 * r, base - 0.44 * r, x + dx + 0.05 * r, base - 0.52 * r,
                      x + dx, base - 0.60 * r)
        p.drawPath(steam)

    p.setPen(QPen(qcolor(theme.accent), max(2.0, 0.03 * r)))    # alça
    p.drawEllipse(QPointF(x + 0.15 * r, base - 0.17 * r), 0.06 * r, 0.075 * r)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(qcolor(theme.accent))                            # corpo
    p.drawRoundedRect(QRectF(x - 0.14 * r, base - 0.30 * r, 0.28 * r, 0.32 * r), 0.04 * r, 0.04 * r)
    p.setBrush(qcolor("#f6e8ee", 90))
    p.drawEllipse(QPointF(x, base - 0.30 * r), 0.14 * r, 0.035 * r)   # borda
    p.setBrush(qcolor("#4a2c1a"))
    p.drawEllipse(QPointF(x, base - 0.30 * r), 0.115 * r, 0.026 * r)  # café


def _plant(p, x, base, r):
    p.setPen(Qt.PenStyle.NoPen)
    pot_top = base - 0.2 * r
    leaves = (("#5fbf8a", -55), ("#7bd4a0", -28), ("#5fbf8a", 0), ("#7bd4a0", 28), ("#5fbf8a", 55))
    for color, angle in leaves:
        p.save()
        p.translate(x, pot_top)
        p.rotate(angle)
        p.setBrush(qcolor(color))
        p.drawEllipse(QPointF(0, -0.15 * r), 0.05 * r, 0.15 * r)
        p.restore()
    p.setBrush(qcolor("#c77d5a"))                               # vaso
    p.drawPolygon(QPolygonF([
        QPointF(x - 0.11 * r, pot_top), QPointF(x + 0.11 * r, pot_top),
        QPointF(x + 0.08 * r, base), QPointF(x - 0.08 * r, base),
    ]))


def _planet(p, theme, x, y, r):
    radius = 0.24 * r
    tilt = math.radians(-18)

    def ring_point(degrees):
        a = math.radians(degrees)
        rx, ry = 0.42 * r * math.cos(a), 0.09 * r * math.sin(a)
        return QPointF(x + rx * math.cos(tilt) - ry * math.sin(tilt),
                       y + rx * math.sin(tilt) + ry * math.cos(tilt))

    ring_pen = QPen(qcolor("#b9a8ff", 190), max(1.5, 0.028 * r), Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(ring_pen)                                          # parte de trás do anel
    p.drawPolyline(QPolygonF([ring_point(d) for d in range(180, 361, 6)]))

    p.setPen(Qt.PenStyle.NoPen)
    gradient = QLinearGradient(QPointF(x, y - radius), QPointF(x, y + radius))
    gradient.setColorAt(0.0, qcolor("#9d86ff"))
    gradient.setColorAt(1.0, qcolor("#4a2fd6"))
    p.setBrush(QBrush(gradient))
    p.drawEllipse(QPointF(x, y), radius, radius)

    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(ring_pen)                                          # parte da frente do anel
    p.drawPolyline(QPolygonF([ring_point(d) for d in range(0, 181, 6)]))

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(qcolor(theme.muted, 200))                        # lua pequena
    p.drawEllipse(QPointF(x - 0.62 * r, y - 0.16 * r), 0.055 * r, 0.055 * r)
