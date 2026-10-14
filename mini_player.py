"""Mini player: janelinha flutuante no canto da tela, mostrada quando o programa é minimizado.

Tem um disco pequeno girando, o nome da música, os botões de tocar/pausar e trocar de faixa,
um botão para reabrir a janela grande e um botão para fechar o programa.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from icons import make_icon
from themes import DEFAULT_THEME, THEMES, Theme, mini_stylesheet
from vinyl_widget import VinylWidget

MARGIN = 16        # distância da borda da tela
WIDTH, HEIGHT = 340, 96
TEXT_WIDTH = 188   # largura disponível para o título e o artista


class MiniPlayer(QWidget):
    play_clicked = Signal()
    next_clicked = Signal()
    prev_clicked = Signal()
    restore_clicked = Signal()  # reabrir a janela grande
    close_clicked = Signal()    # fechar o programa

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.Tool                    # não aparece como outro programa na barra
            | Qt.WindowType.FramelessWindowHint   # sem moldura do sistema
            | Qt.WindowType.WindowStaysOnTopHint, # fica por cima das outras janelas
        )
        self.settings = QSettings("VinylPlayer", "VinylPlayer")  # o mesmo arquivo da janela principal
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Vinyl Player")
        self.setFixedSize(WIDTH, HEIGHT)
        self._theme: Theme = THEMES[DEFAULT_THEME]
        self.setStyleSheet(mini_stylesheet(self._theme))
        self.setToolTip("Arraste para mover  ·  clique direito para mais opções")

        self._kinds: dict = {}  # botão -> tipo de ícone (para refazer as cores ao trocar de tema)
        self._playing = False
        self.icon_play = make_icon("play", self._theme.on_accent)
        self.icon_pause = make_icon("pause", self._theme.on_accent)

        # --- disco pequeno (sem o braço da agulha) ---
        self.vinyl = VinylWidget(show_arm=False)
        self.vinyl.setFixedSize(76, 76)

        # --- textos ---
        self.title = QLabel("Vinyl Player")
        self.title.setObjectName("title")
        self.title.setFixedWidth(TEXT_WIDTH)
        self.artist = QLabel("")
        self.artist.setObjectName("muted")
        self.artist.setFixedWidth(TEXT_WIDTH)

        # --- botões ---
        self.btn_prev = self._button("prev", "Música anterior", 28)
        self.btn_play = self._button("play", "Tocar / pausar", 34)
        self.btn_play.setObjectName("play")
        self.btn_next = self._button("next", "Próxima música", 28)
        self.btn_expand = self._button("restore", "Abrir o Vinyl Player", 24)
        self.btn_close = self._button("close", "Fechar o programa", 24)
        self.btn_close.setObjectName("close")

        controls = QHBoxLayout()
        controls.setSpacing(4)
        controls.addWidget(self.btn_prev)
        controls.addWidget(self.btn_play)
        controls.addWidget(self.btn_next)
        controls.addStretch()

        middle = QVBoxLayout()
        middle.setSpacing(2)
        middle.addWidget(self.title)
        middle.addWidget(self.artist)
        middle.addStretch()
        middle.addLayout(controls)

        right = QVBoxLayout()
        right.setSpacing(4)
        right.addWidget(self.btn_close)
        right.addWidget(self.btn_expand)
        right.addStretch()

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)
        root.addWidget(self.vinyl)
        root.addLayout(middle, stretch=1)
        root.addLayout(right)

        self.btn_play.clicked.connect(self.play_clicked)
        self.btn_next.clicked.connect(self.next_clicked)
        self.btn_prev.clicked.connect(self.prev_clicked)
        self.btn_expand.clicked.connect(self.restore_clicked)
        self.btn_close.clicked.connect(self.close_clicked)

        # guarda a posição só depois que o usuário para de arrastar
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._save_position)

    def _button(self, icon_kind: str, tooltip: str, size: int) -> QPushButton:
        button = QPushButton()
        button.setIcon(make_icon(icon_kind, self._theme.icon))
        self._kinds[button] = icon_kind
        button.setIconSize(QSize(int(size * 0.7), int(size * 0.7)))
        button.setFixedSize(size, size)
        button.setToolTip(tooltip)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    # ---------------------------------------------------------------- o que a janela principal envia
    def set_info(self, title: str, subtitle: str = ""):
        self._set_elided(self.title, title or "Vinyl Player")
        self._set_elided(self.artist, subtitle)

    def set_theme(self, theme: Theme):
        self._theme = theme
        self.setStyleSheet(mini_stylesheet(theme))
        self.vinyl.set_theme(theme)
        self._refresh_icons()
        self.update()

    def _refresh_icons(self):
        """Os ícones usam a cor do tema (escuros no tema claro, claros nos escuros)."""
        t = self._theme
        self.icon_play = make_icon("play", t.on_accent)
        self.icon_pause = make_icon("pause", t.on_accent)
        for button, kind in self._kinds.items():
            if button is not self.btn_play:
                button.setIcon(make_icon(kind, t.icon))
        self.btn_play.setIcon(self.icon_pause if self._playing else self.icon_play)

    def set_rate(self, rate: float):
        self.vinyl.set_rate(rate)

    def set_cover(self, pixmap):
        self.vinyl.set_cover(pixmap)

    def set_full_cover(self, enabled: bool):
        self.vinyl.set_full_cover(enabled)

    def set_playing(self, playing: bool):
        self._playing = playing
        self.vinyl.set_playing(playing)
        self.btn_play.setIcon(self.icon_pause if playing else self.icon_play)

    def _set_elided(self, label: QLabel, text: str):
        metrics = QFontMetrics(label.font())
        label.setText(metrics.elidedText(text, Qt.TextElideMode.ElideRight, TEXT_WIDTH))
        label.setToolTip(text if text else "")

    # ---------------------------------------------------------------- mostrar / esconder
    def show_in_corner(self):
        """Mostra o mini player onde o usuário o deixou da última vez (ou no canto da tela)."""
        if not self.isVisible():
            self.move(self._start_position())
            self.show()

    def _start_position(self) -> QPoint:
        """Última posição escolhida pelo usuário, ou o canto inferior direito da tela."""
        try:
            x = int(self.settings.value("mini_x"))
            y = int(self.settings.value("mini_y"))
            if QGuiApplication.screenAt(QPoint(x + 20, y + 20)) is not None:
                return QPoint(x, y)
        except (TypeError, ValueError):
            pass
        area = QGuiApplication.primaryScreen().availableGeometry()
        return QPoint(
            area.right() - WIDTH - MARGIN + 1,
            area.bottom() - HEIGHT - MARGIN + 1,
        )

    def moveEvent(self, event):
        if self.isVisible():
            self._save_timer.start()
        super().moveEvent(event)

    def _save_position(self):
        self.settings.setValue("mini_x", self.x())
        self.settings.setValue("mini_y", self.y())

    # ---------------------------------------------------------------- visual e mouse
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(self._theme.border), 1))
        background = QColor(self._theme.bg)
        background.setAlpha(245)
        p.setBrush(background)
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 14, 14)
        p.end()

    def mousePressEvent(self, event):
        """Arrastar com o botão esquerdo move a janelinha (funciona no Windows, X11 e Wayland)."""
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.windowHandle()
            if handle is not None:
                handle.startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction("Abrir o Vinyl Player", self.restore_clicked.emit)
        menu.addAction("Tocar / pausar", self.play_clicked.emit)
        menu.addAction("Próxima música", self.next_clicked.emit)
        menu.addAction("Música anterior", self.prev_clicked.emit)
        menu.addSeparator()
        menu.addAction("Fechar o programa", self.close_clicked.emit)
        menu.exec(event.globalPos())
