"""Widget que desenha o disco de vinil girando, com a capa do álbum e o braço da agulha.

A vitrola pode ser mostrada de dois jeitos, escolhidos pelo tema (veja themes.py):
  - "top":  disco visto de cima (clássico);
  - "side": vitrola vista de lado, inclinada, com a base, o cenário e os objetos do tema.
Sem braço (mini player), mostra só o disco.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

from scenery import draw_backdrop, draw_props, qcolor
from themes import DEFAULT_THEME, THEMES, Theme

# ---------------------------------------------------------------- ajustes rápidos
DEGREES_PER_SECOND = 120.0  # velocidade do giro (um vinil real de 33 rpm faz ~198)
SPIN_EASING = 2.5           # quanto maior, mais rápido o disco acelera e freia
ARM_EASING = 4.0            # quanto maior, mais rápido o braço se move
TILT = 0.5                  # vista lateral: 1.0 = de cima, valores menores = mais "de lado"

# ---------------------------------------------------------------- geometria do braço
# Tudo em "raios do disco", a partir do centro do disco (y positivo = para baixo).
PIVOT_X, PIVOT_Y = 1.10, -0.95  # onde o braço é preso (canto superior direito)
ARM_LENGTH = 1.20               # comprimento do braço até a agulha
OUTER_GROOVE = 0.93             # onde a agulha pousa (borda do disco)
INNER_GROOVE = 0.42             # onde a agulha termina (perto do rótulo)

# ---------------------------------------------------------------- base da vitrola (vista lateral)
PLINTH_X0, PLINTH_X1 = -1.30, 1.70   # largura da base, em raios
PLINTH_Y0, PLINTH_Y1 = -1.25, 1.30   # profundidade da base (no plano, antes de inclinar)
PLINTH_THICKNESS = 0.30              # espessura da base (a "frente"), em raios


def _arm_angle_for_radius(distance: float) -> float:
    """Ângulo (em graus) do braço para a agulha ficar a `distance` do centro do disco."""
    d_pc = math.hypot(PIVOT_X, PIVOT_Y)                  # distância pivô -> centro
    phi = math.atan2(-PIVOT_Y, -PIVOT_X)                 # direção do pivô para o centro
    cos_a = (d_pc**2 + ARM_LENGTH**2 - distance**2) / (2 * d_pc * ARM_LENGTH)
    alpha = math.acos(max(-1.0, min(1.0, cos_a)))
    return math.degrees(phi - alpha)


ARM_OUTER = _arm_angle_for_radius(OUTER_GROOVE)  # agulha no começo da música
ARM_INNER = _arm_angle_for_radius(INNER_GROOVE)  # agulha no fim da música
ARM_REST = ARM_OUTER - 22.0                      # braço parado, fora do disco


class VinylWidget(QWidget):
    def __init__(self, parent=None, show_arm: bool = True):
        """`show_arm=False` desenha só o disco (usado no mini player, que é pequeno)."""
        super().__init__(parent)
        self._show_arm = show_arm
        self._theme: Theme = THEMES[DEFAULT_THEME]
        if show_arm:
            self.setMinimumSize(300, 280)

        self._cover: QPixmap | None = None
        self._full_cover = False  # False = capa no rótulo central; True = capa no disco todo

        self._angle = 0.0          # giro atual do disco
        self._speed = 0.0          # velocidade atual (graus/s); tem "inércia"
        self._rate = 1.0           # velocidade de reprodução (0,75x, 1x, 2x...): o disco acompanha
        self._arm = ARM_REST       # ângulo atual do braço
        self._playing = False
        self._progress = 0.0       # 0 = começo da música, 1 = fim

        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60 quadros por segundo
        self._timer.timeout.connect(self._tick)

    # ---------------------------------------------------------------- API pública
    def set_theme(self, theme: Theme):
        self._theme = theme
        self.update()

    def set_cover(self, pixmap: QPixmap | None):
        """Define a capa. Passe None para voltar ao rótulo padrão."""
        if pixmap is None or pixmap.isNull():
            self._cover = None
        else:
            # recorta um quadrado central para a capa caber certinho no círculo
            side = min(pixmap.width(), pixmap.height())
            x = (pixmap.width() - side) // 2
            y = (pixmap.height() - side) // 2
            self._cover = pixmap.copy(x, y, side, side)
        self.update()

    def set_full_cover(self, enabled: bool):
        self._full_cover = enabled
        self.update()

    def set_rate(self, rate: float):
        """Velocidade de reprodução: o disco gira mais rápido ou mais devagar junto."""
        self._rate = max(0.1, float(rate))
        self._ensure_animation()

    def set_playing(self, playing: bool):
        """Liga/desliga o giro. O braço desce quando toca e volta ao repouso quando para."""
        self._playing = playing
        self._ensure_animation()

    def set_progress(self, progress: float):
        """Posição da música (0 a 1). A agulha vai andando do começo para o centro do disco."""
        self._progress = max(0.0, min(1.0, progress))
        self._ensure_animation()

    # ---------------------------------------------------------------- animação
    def _target_arm(self) -> float:
        if not self._playing:
            return ARM_REST
        return ARM_OUTER + (ARM_INNER - ARM_OUTER) * self._progress

    def _ensure_animation(self):
        if not self._timer.isActive():
            self._clock.start()
            self._timer.start()

    def _tick(self):
        dt = min(self._clock.restart() / 1000.0, 0.1)

        target_speed = DEGREES_PER_SECOND * self._rate if self._playing else 0.0
        self._speed += (target_speed - self._speed) * min(1.0, dt * SPIN_EASING)
        self._angle = (self._angle + self._speed * dt) % 360.0

        target_arm = self._target_arm()
        self._arm += (target_arm - self._arm) * min(1.0, dt * ARM_EASING)

        settled = abs(self._arm - target_arm) < 0.05
        if not self._playing and self._speed < 1.0 and settled:
            self._speed = 0.0
            self._arm = target_arm
            self._timer.stop()
        self.update()

    # ---------------------------------------------------------------- desenho
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )

        if not self._show_arm:
            r = max(10.0, min(self.width(), self.height()) / 2 - 4)
            p.translate(self.width() / 2, self.height() / 2)
            self._draw_disc(p, r)
        elif self._theme.view == "side":
            self._paint_side(p)
        else:
            self._paint_top(p)
        p.end()

    def _paint_top(self, p: QPainter):
        """Disco visto de cima, com o braço ao lado."""
        # (o braço parado vai até 1,4 raio à direita do centro, por isso o espaço extra)
        r = max(20.0, min(self.width() / 2.6, self.height() / 2.3))
        p.translate(self.width() / 2 - 0.2 * r, self.height() / 2 + 0.085 * r)
        self._draw_disc(p, r)
        self._draw_arm(p, r)

    def _paint_side(self, p: QPainter):
        """Vitrola vista de lado: cenário, base, prato, disco inclinado girando e braço levantado."""
        t = self._theme
        k = TILT
        # o conjunto ocupa de -1,05 a 1,0 raio de altura (sobra espaço em cima para o cenário)
        r = max(20.0, min(self.width() / 3.15, self.height() / 2.1))
        ox = self.width() / 2 - 0.2 * r
        oy = self.height() / 2 + 0.025 * r

        left = PLINTH_X0 * r
        width = (PLINTH_X1 - PLINTH_X0) * r
        top = PLINTH_Y0 * k * r
        face_h = (PLINTH_Y1 - PLINTH_Y0) * k * r  # altura do tampo, já inclinado
        thick = PLINTH_THICKNESS * r
        bottom = top + face_h + thick
        corner = 0.07 * r

        draw_backdrop(p, t, self.width(), self.height(), r, ox, oy, top)  # estrelas, sol, raios...
        p.translate(ox, oy)
        draw_props(p, t, r, top)                                          # xícara, planta, planeta

        p.setPen(Qt.PenStyle.NoPen)

        # sombra na mesa
        p.setBrush(QColor(0, 0, 0, 70))
        p.drawRoundedRect(
            QRectF(left - 0.02 * r, top + 0.14 * r, width + 0.04 * r, face_h + thick + 0.04 * r),
            0.08 * r, 0.08 * r,
        )

        # brilho de neon em volta da base
        if t.glow:
            p.setBrush(Qt.BrushStyle.NoBrush)
            outline = QRectF(left, top, width, face_h + thick)
            for line_width, alpha in ((7, 16), (5, 28), (3, 48), (1.5, 95)):
                p.setPen(QPen(qcolor(t.glow, alpha), line_width * 0.01 * r))
                p.drawRoundedRect(outline, corner, corner)
            p.setPen(Qt.PenStyle.NoPen)

        # pés
        p.setBrush(QColor(t.wood_dark))
        for foot_x in (left + 0.10 * r, left + width - 0.32 * r):
            p.drawRoundedRect(QRectF(foot_x, bottom - 0.03 * r, 0.22 * r, 0.08 * r), 0.02 * r, 0.02 * r)

        # corpo (a parte da frente) e tampo
        p.setBrush(QColor(t.wood_front))
        p.drawRoundedRect(QRectF(left, top, width, face_h + thick), corner, corner)
        p.setBrush(QColor(t.wood_top))
        p.drawRoundedRect(QRectF(left, top, width, face_h), corner, corner)

        # veios da madeira (ou escovado do metal) e brilho da borda
        if t.grain > 0:
            p.setPen(QPen(QColor(0, 0, 0, t.grain_alpha), 1))
            for i in range(1, t.grain + 1):
                y = top + face_h * i / (t.grain + 1)
                p.drawLine(QPointF(left + 0.06 * r, y), QPointF(left + width - 0.06 * r, y))
        p.setPen(QPen(QColor(255, 255, 255, 50), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(left + 1, top + 1, width - 2, face_h - 2), corner, corner)
        p.setPen(QPen(QColor(0, 0, 0, 90), 1))
        p.drawLine(QPointF(left + 0.02 * r, top + face_h), QPointF(left + width - 0.02 * r, top + face_h))

        # filetes coloridos (neon, art déco, metal)
        if t.trim:
            p.setPen(QPen(qcolor(t.trim), max(1.2, 0.011 * r)))
            p.drawRoundedRect(
                QRectF(left + 0.03 * r, top + 0.03 * r, width - 0.06 * r, face_h - 0.06 * r),
                corner * 0.6, corner * 0.6,
            )
            p.drawLine(QPointF(left + 0.05 * r, top + face_h + 0.05 * r),
                       QPointF(left + width - 0.05 * r, top + face_h + 0.05 * r))
            if t.trim_double:
                p.setPen(QPen(qcolor(t.trim, 150), max(1.0, 0.006 * r)))
                p.drawRoundedRect(
                    QRectF(left + 0.065 * r, top + 0.065 * r, width - 0.13 * r, face_h - 0.13 * r),
                    corner * 0.4, corner * 0.4,
                )
                p.drawLine(QPointF(left + 0.05 * r, bottom - 0.05 * r),
                           QPointF(left + width - 0.05 * r, bottom - 0.05 * r))

        # ---- tudo que está "deitado" sobre o tampo é desenhado e depois inclinado ----
        p.save()
        p.scale(1.0, k)
        p.setPen(Qt.PenStyle.NoPen)

        # prato (um cilindro: lateral + tampa)
        platter_r = 1.06 * r
        depth = 0.06 * r / k
        p.setBrush(QColor(t.platter_dark))
        p.drawEllipse(QPointF(0, depth), platter_r, platter_r)
        p.drawRect(QRectF(-platter_r, 0, 2 * platter_r, depth))
        p.setBrush(QColor(t.platter_metal))
        p.drawEllipse(QPointF(0, 0), platter_r, platter_r)
        if t.glow:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(qcolor(t.glow, 170), 0.012 * r))
            p.drawEllipse(QPointF(0, 0), platter_r + 0.006 * r, platter_r + 0.006 * r)
            p.setPen(Qt.PenStyle.NoPen)

        self._draw_disc(p, r)
        self._draw_arm(p, r, lift=0.10 * r / k)  # o braço fica um pouco acima do disco
        p.restore()

        # ---- detalhes na frente da base: luz de "ligado" e botões ----
        p.setPen(Qt.PenStyle.NoPen)
        front_y = top + face_h + thick / 2
        led_x = left + 0.16 * r
        if self._playing:
            p.setBrush(qcolor(t.led, 70))
            p.drawEllipse(QPointF(led_x, front_y), 0.065 * r, 0.065 * r)
            p.setBrush(qcolor(t.led))
        else:
            p.setBrush(qcolor(t.led, 60))
        p.drawEllipse(QPointF(led_x, front_y), 0.032 * r, 0.032 * r)

        for knob_x in (left + width - 0.42 * r, left + width - 0.22 * r):
            p.setBrush(QColor(t.knob or t.brass))
            p.drawEllipse(QPointF(knob_x, front_y), 0.05 * r, 0.05 * r)
            p.setBrush(QColor(t.wood_dark))
            p.drawEllipse(QPointF(knob_x, front_y), 0.018 * r, 0.018 * r)

    def _draw_disc(self, p: QPainter, r: float):
        t = self._theme

        # sombra (fixa)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 70))
        p.drawEllipse(QPointF(0.03 * r, 0.045 * r), r, r)

        # ---- parte que gira ----
        p.save()
        p.rotate(self._angle)

        has_full_cover = self._full_cover and self._cover is not None

        if has_full_cover:
            disc_path = QPainterPath()
            disc_path.addEllipse(QPointF(0, 0), r, r)
            p.setClipPath(disc_path)
            p.drawPixmap(QRectF(-r, -r, 2 * r, 2 * r), self._cover, QRectF(self._cover.rect()))
            p.setClipping(False)
            groove_color = QColor(0, 0, 0, 45)
        else:
            p.setBrush(QColor(t.vinyl))
            p.drawEllipse(QPointF(0, 0), r, r)
            groove_color = QColor(255, 255, 255, 18)

        # sulcos do disco
        p.setPen(QPen(groove_color, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        rad = r * 0.38
        step = max(3.0, r * 0.025)
        while rad < r * 0.97:
            p.drawEllipse(QPointF(0, 0), rad, rad)
            rad += step

        # rótulo central
        if not has_full_cover:
            lr = r * 0.34
            if self._cover is not None:
                label_path = QPainterPath()
                label_path.addEllipse(QPointF(0, 0), lr, lr)
                p.setClipPath(label_path)
                p.drawPixmap(
                    QRectF(-lr, -lr, 2 * lr, 2 * lr), self._cover, QRectF(self._cover.rect())
                )
                p.setClipping(False)
            else:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(t.label_color))
                p.drawEllipse(QPointF(0, 0), lr, lr)
                # marquinha para dar para ver o giro quando não há capa
                p.setBrush(QColor(240, 230, 210))
                p.drawEllipse(QPointF(0, -lr * 0.6), lr * 0.1, lr * 0.1)

        # furo central
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t.bg))
        p.drawEllipse(QPointF(0, 0), r * 0.035, r * 0.035)

        p.restore()

        # ---- brilho (fixo, não gira) ----
        shine = QConicalGradient(QPointF(0, 0), 45)
        transparent = QColor(255, 255, 255, 0)
        glow = QColor(255, 255, 255, 40)
        shine.setColorAt(0.00, transparent)
        shine.setColorAt(0.08, glow)
        shine.setColorAt(0.16, transparent)
        shine.setColorAt(0.50, transparent)
        shine.setColorAt(0.58, glow)
        shine.setColorAt(0.66, transparent)
        shine.setColorAt(1.00, transparent)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(shine))
        p.drawEllipse(QPointF(0, 0), r, r)

    # ---------------------------------------------------------------- braço da agulha
    def _draw_arm(self, p: QPainter, r: float, lift: float = 0.0):
        """`lift` > 0 (vista lateral): o braço fica suspenso, preso numa coluna acima da base."""
        px, py = PIVOT_X * r, PIVOT_Y * r
        t = self._theme

        self._draw_arm_pass(p, r, lift, shadow=True)
        if lift > 0:
            self._draw_pivot_base(p, r, lift)  # a coluna fica atrás do braço
        self._draw_arm_pass(p, r, lift, shadow=False)
        if lift == 0:
            self._draw_pivot_base(p, r, 0.0)   # vista de cima: a base cobre a ponta do braço

        # tampa do pivô
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t.arm_metal))
        p.drawEllipse(QPointF(px, py - lift), 0.05 * r, 0.05 * r)

    def _draw_arm_pass(self, p: QPainter, r: float, lift: float, shadow: bool):
        t = self._theme
        px, py = PIVOT_X * r, PIVOT_Y * r
        arm_width = max(3.0, 0.03 * r)
        metal = QColor(0, 0, 0, 60) if shadow else QColor(t.arm_metal)
        dark = QColor(0, 0, 0, 60) if shadow else QColor(t.arm_dark)

        p.save()
        if shadow:
            p.translate(px + 0.03 * r, py + 0.045 * r)  # a sombra cai na base, sem o "lift"
        else:
            p.translate(px, py - lift)
        p.rotate(self._arm)

        # contrapeso (atrás do pivô)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(dark)
        p.drawRoundedRect(QRectF(-0.24 * r, -0.055 * r, 0.12 * r, 0.11 * r), 3, 3)

        # haste do braço
        p.setPen(QPen(metal, arm_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(-0.14 * r, 0), QPointF((ARM_LENGTH - 0.10) * r, 0))

        # cabeça com a agulha (a ponta fica exatamente em ARM_LENGTH)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(dark)
        p.drawRoundedRect(QRectF((ARM_LENGTH - 0.17) * r, -0.05 * r, 0.17 * r, 0.10 * r), 3, 3)
        p.restore()

    def _draw_pivot_base(self, p: QPainter, r: float, lift: float):
        px, py = PIVOT_X * r, PIVOT_Y * r
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._theme.arm_dark))
        if lift > 0:
            p.drawRect(QRectF(px - 0.11 * r, py - lift, 0.22 * r, lift))   # coluna
            p.drawEllipse(QPointF(px, py - lift), 0.11 * r, 0.11 * r)      # topo da coluna
        p.drawEllipse(QPointF(px, py), 0.11 * r, 0.11 * r)                 # base no tampo
