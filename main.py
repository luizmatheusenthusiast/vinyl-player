"""Vinyl Player: tocador de música com disco de vinil girando.

Rode com:  python main.py
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QEvent, QSettings, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QStyle,
    QVBoxLayout,
    QWidget,
)

import m3u
import session
import sources
from covers import (
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    TrackInfo,
    find_folder_cover,
    list_audio_files,
    read_track_info,
)
from icons import make_icon
from mini_player import MiniPlayer
from playqueue import PlayQueue, Repeat
from sleeptimer import SleepTimer
from themes import DEFAULT_THEME, THEMES, build_stylesheet, get_theme
from version import APP_VERSION
from vinyl_widget import VinylWidget

APP_NAME = "Vinyl Player"

AUDIO_FILTER = "Músicas (*.mp3 *.flac *.ogg *.oga *.opus *.wav *.m4a *.aac *.wma);;Todos os arquivos (*)"
IMAGE_FILTER = "Imagens (*.png *.jpg *.jpeg *.webp *.bmp);;Todos os arquivos (*)"
PLAYLIST_FILTER = "Listas de reprodução (*.m3u *.m3u8);;Todos os arquivos (*)"

HINT_EMPTY = "Arraste uma pasta de CD/álbum ou músicas para cá"
SEEK_STEP_MS = 10_000     # botões de avançar/voltar 10 segundos
RESTART_AFTER_MS = 3_000  # "voltar" depois de 3 s de música recomeça a faixa, em vez de ir à anterior
VOLUME_STEP = 5           # roda do mouse: de 5 em 5

SPEEDS = ((0.75, "0,75×  (lento)"), (1.0, "1×  (normal)"), (1.25, "1,25×"), (1.5, "1,5×  (rápido)"))
SLEEP_CHOICES = (15, 30, 45, 60, 90)  # minutos

REPEAT_TIPS = {
    Repeat.OFF: "Repetir: desligado (R)",
    Repeat.ALL: "Repetir: toda a lista (R)",
    Repeat.ONE: "Repetir: só esta música (R)",
}


def resource_path(relative: str) -> Path:
    """Caminho de um arquivo do programa, tanto rodando o código quanto instalado."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def fmt_time(ms: int) -> str:
    s = max(0, ms) // 1000
    return f"{s // 60}:{s % 60:02d}"


class SeekSlider(QSlider):
    """Barra de progresso: um clique em qualquer ponto pula direto para lá."""

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.maximum() > 0:
            value = QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(), int(event.position().x()), max(1, self.width())
            )
            self.setValue(value)
            self.sliderMoved.emit(value)
        super().mousePressEvent(event)


class ClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class PlayerWindow(QMainWindow):
    # avisos vindos de threads (busca de endereços da internet): chegam na janela com segurança
    web_resolved = Signal(object, str)   # (lista de Entry ou None, mensagem de erro)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(resource_path("assets/icon.png"))))
        self.resize_to_screen()
        self.setAcceptDrops(True)

        self.settings = QSettings("VinylPlayer", "VinylPlayer")

        self.playlist: list[str] = []
        self.titles: dict[str, str] = {}  # nomes das músicas da internet (endereço -> título)
        self.index = -1
        self.queue = PlayQueue()  # decide a ordem: aleatório, repetir, próxima, anterior
        self.current_info = TrackInfo()
        self.custom_cover: QPixmap | None = None  # capa que o usuário escolheu
        self.theme = get_theme(self.settings.value("theme", DEFAULT_THEME))
        self.sleep = SleepTimer()
        self.rate = 1.0
        self.show_remaining = bool(self.settings.value("show_remaining", False, type=bool))
        self.stage_mode = False
        self._pending_seek = 0       # posição a retomar depois que a música carregar
        self._icon_kinds: dict = {}  # botão -> (tipo do ícone, com cor de "aceso")

        # --- áudio ---
        self.audio = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio)

        # --- interface ---
        self.vinyl = VinylWidget()

        self.title_label = QLabel("Vinyl Player")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold;")

        self.artist_label = QLabel(HINT_EMPTY)
        self.artist_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artist_label.setWordWrap(True)

        self.cover_note = QLabel("")
        self.cover_note.setObjectName("muted")
        self.cover_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_note.setWordWrap(True)

        self.pos_slider = SeekSlider(Qt.Orientation.Horizontal)
        self.pos_slider.setToolTip("Clique ou arraste para avançar ou voltar na música")
        self.time_label = ClickableLabel("0:00 / 0:00")
        self.time_label.setObjectName("muted")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setToolTip("Clique para alternar entre tempo total e tempo restante")
        self.time_label.setCursor(Qt.CursorShape.PointingHandCursor)

        self.status_label = QLabel("")
        self.status_label.setObjectName("muted")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # --- botões de reprodução (ícones próprios; as cores seguem o tema) ---
        self.btn_shuffle = self._tool_button("shuffle", "Ordem aleatória (S)", "mode", checkable=True)
        self.btn_prev = self._tool_button("prev", "Música anterior (Ctrl + ←)")
        self.btn_back = self._tool_button("rewind", "Voltar 10 segundos (Shift + ←)")
        self.btn_play = self._tool_button("play", "Tocar / pausar (barra de espaço)", "play", size=48)
        self.btn_fwd = self._tool_button("forward", "Avançar 10 segundos (Shift + →)")
        self.btn_next = self._tool_button("next", "Próxima música (Ctrl + →)")
        self.btn_repeat = self._tool_button("repeat", REPEAT_TIPS[Repeat.OFF], "mode", checkable=True)

        self.transport_row = QWidget()
        transport = QHBoxLayout(self.transport_row)
        transport.setContentsMargins(0, 0, 0, 0)
        transport.setSpacing(6)
        transport.addStretch()
        for button in (
            self.btn_shuffle, self.btn_prev, self.btn_back, self.btn_play,
            self.btn_fwd, self.btn_next, self.btn_repeat,
        ):
            transport.addWidget(button)
        transport.addStretch()

        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setFixedWidth(220)
        self.volume.setToolTip("Volume (também funciona com a roda do mouse)")
        self.volume_row = QWidget()
        volume_row = QHBoxLayout(self.volume_row)
        volume_row.setContentsMargins(0, 0, 0, 0)
        volume_row.addStretch()
        volume_row.addWidget(QLabel("Volume"))
        volume_row.addWidget(self.volume)
        volume_row.addStretch()

        self.btn_folder = QPushButton("Abrir pasta / CD…")
        self.btn_folder.setObjectName("primary")
        self.btn_folder.setToolTip("Escolha a pasta de um CD ou álbum: a capa é encontrada sozinha (Ctrl + O)")
        self.btn_open = QPushButton("Abrir músicas…")
        self.btn_open.setToolTip("Escolha uma ou várias músicas")
        self.actions_row = QWidget()
        actions = QHBoxLayout(self.actions_row)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.addWidget(self.btn_folder, stretch=2)
        actions.addWidget(self.btn_open, stretch=2)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Procurar na lista…")
        self.search.setClearButtonEnabled(True)

        self.list = QListWidget()
        self.list.setToolTip("Dê dois cliques em uma música para tocar. Botão direito: mais opções")
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.footer = QLabel(
            "Espaço: tocar/pausar  ·  S: aleatório  ·  R: repetir  ·  "
            "Ctrl+←/→: música  ·  Shift+←/→: 10 s  ·  M: mudo  ·  F11: modo palco"
        )
        self.footer.setObjectName("muted")
        self.footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(self.vinyl, stretch=3)
        layout.addWidget(self.title_label)
        layout.addWidget(self.artist_label)
        layout.addWidget(self.cover_note)
        layout.addWidget(self.pos_slider)
        layout.addWidget(self.time_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.transport_row)
        layout.addWidget(self.volume_row)
        layout.addWidget(self.actions_row)
        layout.addWidget(self.search)
        layout.addWidget(self.list, stretch=2)
        layout.addWidget(self.footer)

        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)

        # partes que somem no modo palco
        self._stage_hidden = (
            self.cover_note, self.status_label, self.volume_row, self.actions_row,
            self.search, self.list, self.footer,
        )

        self._build_menus()

        # --- volume e modos lembrados da última vez ---
        saved_volume = self.settings.value("volume", 70, type=int)
        self.volume.setValue(saved_volume)
        self.apply_volume()

        shuffle_on = bool(self.settings.value("shuffle", False, type=bool))
        self.btn_shuffle.setChecked(shuffle_on)
        self.queue.set_shuffle(shuffle_on)
        try:
            self.queue.repeat = Repeat(str(self.settings.value("repeat", "off")))
        except ValueError:
            self.queue.repeat = Repeat.OFF

        # --- mini player: aparece no canto da tela quando o programa é minimizado ---
        self.mini = MiniPlayer()
        self.mini.play_clicked.connect(self.toggle_play)
        self.mini.next_clicked.connect(self.next_track)
        self.mini.prev_clicked.connect(self.prev_track)
        self.mini.restore_clicked.connect(self.restore_from_mini)
        self.mini.close_clicked.connect(self.quit_app)
        self.web_resolved.connect(self.on_web_resolved)

        # --- ligações (sinais) ---
        self.btn_folder.clicked.connect(self.open_folder)
        self.btn_open.clicked.connect(self.open_files)
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_next.clicked.connect(self.next_track)
        self.btn_prev.clicked.connect(self.prev_track)
        self.btn_back.clicked.connect(lambda: self.seek_by(-SEEK_STEP_MS))
        self.btn_fwd.clicked.connect(lambda: self.seek_by(SEEK_STEP_MS))
        self.btn_shuffle.toggled.connect(self.on_shuffle_toggled)
        self.btn_repeat.clicked.connect(self.on_repeat_clicked)
        self.list.itemDoubleClicked.connect(lambda item: self.play_index(self.list.row(item)))
        self.list.customContextMenuRequested.connect(self.on_list_menu)
        self.search.textChanged.connect(self.filter_list)
        self.volume.valueChanged.connect(self.on_volume)
        self.time_label.clicked.connect(self.toggle_remaining)

        self.pos_slider.sliderMoved.connect(self.player.setPosition)
        self.player.positionChanged.connect(self.on_position)
        self.player.durationChanged.connect(lambda d: self.pos_slider.setRange(0, d))
        self.player.playbackStateChanged.connect(self.on_state)
        self.player.mediaStatusChanged.connect(self.on_status)
        self.player.errorOccurred.connect(self.on_error)

        # --- atalhos que não estão nos menus ---
        for keys, action in (
            ("Space", self.toggle_play),
            ("Escape", self.leave_stage),
        ):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.activated.connect(action)

        # relógio do timer de dormir (só faz algo quando o timer está ligado)
        self.tick = QTimer(self)
        self.tick.setInterval(500)
        self.tick.timeout.connect(self.on_tick)
        self.tick.start()

        self.on_full_cover(bool(self.settings.value("full_cover", False, type=bool)))
        self.apply_theme(self.theme.key, save=False)

    def resize_to_screen(self):
        """Tamanho inicial mais quadrado (640×720), sempre menor que a tela para nada ficar cortado."""
        width, height = 640, 720
        screen = QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            width = min(width, int(area.width() * 0.9))
            height = min(height, int(area.height() * 0.88))  # sobra espaço para a barra de título e o painel
        self.resize(width, height)

    # ---------------------------------------------------------------- menus
    def _action(self, menu, text, slot, shortcut=None, checkable=False, checked=False, group=None):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        if checkable:
            action.setCheckable(True)
            action.setChecked(checked)
        if group is not None:
            group.addAction(action)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _build_menus(self):
        bar = self.menuBar()

        file_menu = bar.addMenu("&Arquivo")
        self._action(file_menu, "Abrir pasta / CD…", self.open_folder, "Ctrl+O")
        self._action(file_menu, "Abrir músicas…", self.open_files, "Ctrl+Shift+O")
        self._action(file_menu, "Abrir endereço (link, pasta de servidor, caminho)…", self.open_address, "Ctrl+L")
        self._action(file_menu, "Abrir lista de reprodução (.m3u)…", self.open_playlist_file)
        self._action(file_menu, "Salvar lista de reprodução…", self.save_playlist_file, "Ctrl+S")
        file_menu.addSeparator()
        self._action(file_menu, "Sair", self.quit_app, "Ctrl+Q")

        play_menu = bar.addMenu("&Reprodução")
        self.act_play = self._action(play_menu, "Tocar / pausar", self.toggle_play)
        self._action(play_menu, "Próxima música", self.next_track, "Ctrl+Right")
        self._action(play_menu, "Música anterior", self.prev_track, "Ctrl+Left")
        self._action(play_menu, "Avançar 10 segundos", lambda: self.seek_by(SEEK_STEP_MS), "Shift+Right")
        self._action(play_menu, "Voltar 10 segundos", lambda: self.seek_by(-SEEK_STEP_MS), "Shift+Left")
        play_menu.addSeparator()
        self._action(play_menu, "Ordem aleatória", lambda: self.btn_shuffle.click(), "S")
        self._action(play_menu, "Repetir (desligado → lista → uma música)", lambda: self.btn_repeat.click(), "R")
        self.act_mute = self._action(play_menu, "Mudo", self.toggle_mute, "M", checkable=True)
        play_menu.addSeparator()

        speed_menu = play_menu.addMenu("Velocidade")
        speed_group = QActionGroup(self)
        speed_group.setExclusive(True)
        for value, label in SPEEDS:
            self._action(speed_menu, label, lambda checked=False, v=value: self.set_speed(v),
                         checkable=True, checked=(value == 1.0), group=speed_group)

        sleep_menu = play_menu.addMenu("Timer de dormir")
        for minutes in SLEEP_CHOICES:
            self._action(sleep_menu, f"Parar em {minutes} minutos",
                         lambda checked=False, m=minutes: self.start_sleep(m))
        sleep_menu.addSeparator()
        self._action(sleep_menu, "Cancelar timer", self.cancel_sleep)

        view_menu = bar.addMenu("&Visual")
        theme_menu = view_menu.addMenu("Tema")
        self.theme_group = QActionGroup(self)
        self.theme_group.setExclusive(True)
        self.theme_actions: dict = {}
        for theme in THEMES.values():
            act = self._action(theme_menu, theme.label, lambda checked=False, k=theme.key: self.apply_theme(k),
                               checkable=True, checked=(theme.key == self.theme.key), group=self.theme_group)
            self.theme_actions[theme.key] = act
        view_menu.addSeparator()
        self.act_full = self._action(view_menu, "Capa ocupa o disco todo", self.on_full_cover, checkable=True)
        self._action(view_menu, "Trocar capa…", self.choose_cover)
        self.act_auto = self._action(view_menu, "Capa automática", self.use_auto_cover)
        self.act_auto.setEnabled(False)
        view_menu.addSeparator()
        self._action(view_menu, "Modo palco (tela cheia)", self.toggle_stage, "F11")

        help_menu = bar.addMenu("A&juda")
        self._action(help_menu, f"Sobre o {APP_NAME}", self.show_about, "F1")

    def _tool_button(self, icon_kind, tooltip, object_name="transport", size=38, checkable=False):
        button = QPushButton()
        button.setIconSize(QSize(int(size * 0.58), int(size * 0.58)))
        button.setFixedSize(size, size)
        button.setObjectName(object_name)
        button.setToolTip(tooltip)
        button.setCheckable(checkable)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._icon_kinds[button] = (icon_kind, checkable)
        return button

    # ---------------------------------------------------------------- tema
    def refresh_icons(self):
        """Ícones nas cores do tema: escuros no tema claro, claros nos escuros."""
        t = self.theme
        self.icon_play = make_icon("play", t.on_accent)
        self.icon_pause = make_icon("pause", t.on_accent)
        self.icon_repeat = make_icon("repeat", t.icon, t.on_accent)
        self.icon_repeat_one = make_icon("repeat_one", t.icon, t.on_accent)
        for button, (kind, lights_up) in self._icon_kinds.items():
            if button is self.btn_play or button is self.btn_repeat:
                continue
            button.setIcon(make_icon(kind, t.icon, t.on_accent if lights_up else None))
        self.update_repeat_button()
        self.update_play_icon()

    def apply_theme(self, key: str, save: bool = True):
        self.theme = get_theme(key)
        QApplication.instance().setStyleSheet(build_stylesheet(self.theme))
        self.vinyl.set_theme(self.theme)
        self.mini.set_theme(self.theme)
        self.refresh_icons()
        action = getattr(self, "theme_actions", {}).get(self.theme.key)
        if action is not None:
            action.setChecked(True)
        if save:
            self.settings.setValue("theme", self.theme.key)

    # ---------------------------------------------------------------- abrir músicas
    def last_dir(self) -> str:
        return str(self.settings.value("last_dir", str(Path.home())))

    def remember_dir(self, path: str):
        self.settings.setValue("last_dir", path)

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Escolha a pasta do CD / álbum", self.last_dir())
        if not folder:
            return
        self.remember_dir(folder)
        files = list_audio_files(folder)
        if not files:
            QMessageBox.information(
                self, APP_NAME, "Não encontrei músicas nessa pasta.\nTente escolher a pasta que contém os arquivos de áudio."
            )
            return
        self.set_playlist(files)

    def open_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Escolha as músicas", self.last_dir(), AUDIO_FILTER)
        if not files:
            return
        self.remember_dir(str(Path(files[0]).parent))
        self.set_playlist(files)

    def open_playlist_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir lista de reprodução", self.last_dir(), PLAYLIST_FILTER)
        if not path:
            return
        self.remember_dir(str(Path(path).parent))
        try:
            files = m3u.read_m3u(path)
        except OSError:
            files = []
        if not files:
            QMessageBox.information(self, APP_NAME, "Não encontrei nenhuma música nessa lista.")
            return
        self.set_playlist(files)

    def save_playlist_file(self):
        if not self.playlist:
            QMessageBox.information(self, APP_NAME, "A lista está vazia: abra uma pasta ou músicas primeiro.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar lista de reprodução", str(Path(self.last_dir()) / "minha-lista.m3u8"), PLAYLIST_FILTER
        )
        if not path:
            return
        if not path.lower().endswith((".m3u", ".m3u8")):
            path += ".m3u8"
        try:
            m3u.write_m3u(path, self.playlist)
            self.status_label.setText(f"Lista salva: {Path(path).name}")
        except OSError:
            QMessageBox.information(self, APP_NAME, "Não consegui salvar a lista nesse lugar.")

    def display_name(self, path: str) -> str:
        if sources.is_url(path):
            return self.titles.get(path) or sources.display_name(path)
        return Path(path).stem

    def open_address(self):
        """Ctrl+L: cola um link (música, rádio, lista, pasta de servidor, Drive, Dropbox) ou o caminho de uma pasta."""
        clip = QApplication.clipboard().text().strip()
        text, ok = QInputDialog.getText(
            self,
            "Abrir endereço",
            "Cole um link da internet ou o caminho de uma pasta/arquivo:\n"
            "• rádio online (link do stream) ou link direto de música\n"
            "• lista .m3u / .pls\n"
            "• Google Drive ou Dropbox (arquivo compartilhado)\n"
            "• pasta de um servidor (link terminado em /): procura nas subpastas também",
            text=clip if sources.is_url(clip) else "",
        )
        if ok:
            self.open_location(text)

    def open_location(self, text: str):
        text = text.strip().strip('"')
        if not text:
            return
        if sources.is_url(text):
            self.status_label.setText("Procurando as músicas…")

            def work():
                try:
                    entries, error = sources.resolve(text), ""
                except sources.SourceError as exc:
                    entries, error = None, str(exc)
                except Exception:
                    entries, error = None, "Algo deu errado ao abrir esse endereço."
                self.web_resolved.emit(entries, error)

            threading.Thread(target=work, daemon=True).start()
            return
        path = Path(text).expanduser()
        if path.exists():
            self.open_paths([path])
        else:
            QMessageBox.information(self, APP_NAME, "Não encontrei esse caminho. Confira se ele está certo.")

    def on_web_resolved(self, entries, error: str):
        self.status_label.setText("")
        if error or not entries:
            QMessageBox.information(self, APP_NAME, error or "Não encontrei músicas nesse endereço.")
            return
        titles = {e.url: e.title for e in entries}
        self.set_playlist([e.url for e in entries], titles=titles)

    def open_paths(self, paths):
        """Abre o que for dado (pastas, músicas, listas .m3u ou uma imagem de capa)."""
        audio: list = []
        images: list[Path] = []
        for raw in paths:
            if sources.is_url(str(raw)):
                self.open_location(str(raw))
                continue
            path = Path(raw)
            if path.is_dir():
                audio += list_audio_files(path)
            elif path.suffix.lower() in AUDIO_EXTENSIONS:
                audio.append(path)
            elif path.suffix.lower() in (".m3u", ".m3u8"):
                try:
                    audio += m3u.read_m3u(path)
                except OSError:
                    pass
            elif path.suffix.lower() in IMAGE_EXTENSIONS:
                images.append(path)
        if audio:
            self.set_playlist(audio)
        if images:
            self.set_custom_cover(images[0])

    def set_playlist(self, paths, autoplay: bool = True, start: int | None = None, position: int = 0,
                     titles: dict | None = None):
        self.player.stop()
        self.titles = dict(titles or {})
        self.playlist = [str(p) for p in paths]
        self.index = -1
        self.list.clear()
        self.list.addItems([self.display_name(p) for p in self.playlist])
        self.search.clear()
        self.queue.reset(len(self.playlist))
        if not self.playlist:
            return
        i = self.queue.pick_start() if start is None else start
        self.queue.jump_to(i)
        self._pending_seek = position
        self.load_track(i, play=autoplay)

    # ---------------------------------------------------------------- lista: procurar e remover
    def filter_list(self, text: str):
        needle = text.strip().lower()
        for row in range(len(self.playlist)):
            item = self.list.item(row)
            if item is not None:
                item.setHidden(bool(needle) and needle not in self.display_name(self.playlist[row]).lower())

    def on_list_menu(self, pos):
        item = self.list.itemAt(pos)
        if item is None:
            return
        row = self.list.row(item)
        menu = QMenu(self)
        menu.addAction("Tocar agora", lambda: self.play_index(row))
        menu.addAction("Remover da lista", lambda: self.remove_row(row))
        menu.exec(self.list.mapToGlobal(pos))

    def remove_row(self, row: int):
        if not (0 <= row < len(self.playlist)):
            return
        was_current = row == self.index
        was_playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        del self.playlist[row]
        self.list.takeItem(row)
        self.queue.reset(len(self.playlist))
        if not self.playlist:
            self.player.stop()
            self.index = -1
            return
        if was_current:
            self.player.stop()
            new = min(row, len(self.playlist) - 1)
            self.queue.jump_to(new)
            self.load_track(new, play=was_playing)
        else:
            if row < self.index:
                self.index -= 1
            self.queue.jump_to(self.index)
            self.list.setCurrentRow(self.index)

    # ---------------------------------------------------------------- escolher a música
    def play_index(self, i: int):
        """O usuário escolheu a música `i` (clique na lista, ou o começo de uma lista nova)."""
        self.queue.jump_to(i)
        self.load_track(i)

    def load_track(self, i: int, play: bool = True):
        if not (0 <= i < len(self.playlist)):
            return
        self.index = i
        path = self.playlist[i]
        self.list.setCurrentRow(i)

        is_web = sources.is_url(path)
        if is_web:
            info = self.current_info = TrackInfo()
            title = self.display_name(path)
            subtitle = "Da internet"
        else:
            info = self.current_info = read_track_info(path)
            title = info.title or Path(path).stem
            subtitle = " — ".join(x for x in (info.artist, info.album) if x)
        self.title_label.setText(title)
        self.artist_label.setText(subtitle)
        self.mini.set_info(title, subtitle)
        self.setWindowTitle(f"{title} — {APP_NAME}")
        self.refresh_cover()

        self.vinyl.set_progress(0.0)
        self.player.setSource(QUrl(path) if is_web else QUrl.fromLocalFile(path))
        if play:
            self.player.play()
        self.save_session()

    def next_track(self):
        """Pular para a próxima música (no aleatório, uma sorteada)."""
        if not self.playlist:
            return
        i = self.queue.next()
        if i is not None:
            self.load_track(i)

    def prev_track(self):
        """Voltar: depois de 3 s de música recomeça a faixa; senão vai para a anterior."""
        if not self.playlist:
            return
        if self.player.position() > RESTART_AFTER_MS:
            self.player.setPosition(0)
            return
        i = self.queue.previous()
        if i is None:
            self.player.setPosition(0)  # não há anterior: só recomeça
        else:
            self.load_track(i)

    def seek_by(self, delta_ms: int):
        """Avança ou volta alguns segundos dentro da música."""
        if self.index < 0:
            return
        duration = self.player.duration()
        target = self.player.position() + delta_ms
        if duration > 0:
            target = min(target, max(0, duration - 500))
        self.player.setPosition(max(0, target))

    # ---------------------------------------------------------------- modos: aleatório e repetir
    def on_shuffle_toggled(self, enabled: bool):
        self.queue.set_shuffle(enabled)
        self.settings.setValue("shuffle", enabled)
        self.btn_shuffle.setToolTip("Ordem aleatória: ligada (S)" if enabled else "Ordem aleatória: desligada (S)")

    def on_repeat_clicked(self):
        self.queue.cycle_repeat()
        self.settings.setValue("repeat", self.queue.repeat.value)
        self.update_repeat_button()

    def update_repeat_button(self):
        mode = self.queue.repeat
        self.btn_repeat.setIcon(self.icon_repeat_one if mode is Repeat.ONE else self.icon_repeat)
        self.btn_repeat.setChecked(mode is not Repeat.OFF)
        self.btn_repeat.setToolTip(REPEAT_TIPS[mode])

    # ---------------------------------------------------------------- controles
    def toggle_play(self):
        if self.index < 0:
            if self.playlist:
                self.play_index(self.queue.pick_start())
            else:
                self.open_folder()
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def update_play_icon(self):
        playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self.btn_play.setIcon(self.icon_pause if playing else self.icon_play)

    def on_state(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.vinyl.set_playing(playing)  # o disco gira e a agulha desce só tocando
        self.mini.set_playing(playing)
        self.btn_play.setIcon(self.icon_pause if playing else self.icon_play)

    def on_status(self, status):
        """Música carregada (retoma a posição salva) ou terminada (decide a próxima)."""
        if status == QMediaPlayer.MediaStatus.LoadedMedia and self._pending_seek:
            self.player.setPosition(self._pending_seek)
            self._pending_seek = 0
            return
        if status != QMediaPlayer.MediaStatus.EndOfMedia:
            return
        i = self.queue.next(auto=True)
        if i is None:
            return  # acabou a lista
        if i == self.index:
            self.player.setPosition(0)  # repetir a mesma música
            self.player.play()
        else:
            self.load_track(i)

    def on_position(self, pos: int):
        duration = self.player.duration()
        if not self.pos_slider.isSliderDown():
            self.pos_slider.setValue(pos)
        if self.show_remaining and duration > 0:
            self.time_label.setText(f"{fmt_time(pos)} / -{fmt_time(duration - pos)}")
        else:
            self.time_label.setText(f"{fmt_time(pos)} / {fmt_time(duration)}")
        if duration > 0:
            self.vinyl.set_progress(pos / duration)

    def toggle_remaining(self):
        self.show_remaining = not self.show_remaining
        self.settings.setValue("show_remaining", self.show_remaining)
        self.on_position(self.player.position())

    # ---------------------------------------------------------------- volume e mudo
    def apply_volume(self):
        """Volume real = barra × fade do timer de dormir."""
        self.audio.setVolume(self.volume.value() / 100 * self.sleep.volume_factor())

    def on_volume(self, value: int):
        self.apply_volume()
        self.settings.setValue("volume", value)

    def toggle_mute(self, checked: bool | None = None):
        muted = checked if isinstance(checked, bool) else not self.audio.isMuted()
        self.audio.setMuted(muted)
        self.act_mute.setChecked(muted)
        self.status_label.setText("Mudo" if muted else "")

    def wheelEvent(self, event):
        """Roda do mouse sobre a janela: volume."""
        delta = event.angleDelta().y()
        if delta:
            step = VOLUME_STEP if delta > 0 else -VOLUME_STEP
            self.volume.setValue(max(0, min(100, self.volume.value() + step)))
            event.accept()

    # ---------------------------------------------------------------- velocidade
    def set_speed(self, rate: float):
        self.rate = rate
        self.player.setPlaybackRate(rate)
        self.vinyl.set_rate(rate)  # o disco gira mais rápido ou mais devagar junto
        self.mini.set_rate(rate)

    # ---------------------------------------------------------------- timer de dormir
    def start_sleep(self, minutes: int):
        self.sleep.start(minutes)
        self.status_label.setText(f"Vai parar em {self.sleep.label()}")

    def cancel_sleep(self):
        self.sleep.cancel()
        self.apply_volume()
        self.status_label.setText("")

    def on_tick(self):
        if not self.sleep.active:
            return
        if self.sleep.expired():
            self.player.pause()
            self.cancel_sleep()  # devolve o volume para a próxima vez que tocar
            self.status_label.setText("Timer de dormir: boa noite!")
            return
        self.apply_volume()
        self.status_label.setText(f"Vai parar em {self.sleep.label()}")

    def on_error(self, error, message):
        if error != QMediaPlayer.Error.NoError:
            if sources.is_url(self.playlist[self.index] if 0 <= self.index < len(self.playlist) else ""):
                self.artist_label.setText(f"Não consegui tocar este endereço da internet. ({message})")
            else:
                self.artist_label.setText("Não consegui tocar este arquivo. Tente a próxima música.")

    # ---------------------------------------------------------------- capa
    def show_cover(self, pixmap: QPixmap | None):
        """Mostra a capa no disco grande e no do mini player."""
        self.vinyl.set_cover(pixmap)
        self.mini.set_cover(pixmap)

    def on_full_cover(self, enabled: bool = False):
        self.settings.setValue("full_cover", bool(enabled))
        self.act_full.setChecked(bool(enabled))
        self.vinyl.set_full_cover(bool(enabled))
        if hasattr(self, "mini"):
            self.mini.set_full_cover(bool(enabled))

    def refresh_cover(self):
        """Escolhe a capa: a sua > a embutida na música > a da pasta do CD > nenhuma."""
        if self.custom_cover is not None:
            self.show_cover(self.custom_cover)
            self.cover_note.setText("Capa: a imagem que você escolheu")
            return

        if self.current_info.cover_data:
            pixmap = QPixmap()
            if pixmap.loadFromData(self.current_info.cover_data):
                self.show_cover(pixmap)
                self.cover_note.setText("Capa: encontrada dentro da música")
                return

        if 0 <= self.index < len(self.playlist) and not sources.is_url(self.playlist[self.index]):
            found = find_folder_cover(self.playlist[self.index])
            if found is not None:
                pixmap = QPixmap(str(found))
                if not pixmap.isNull():
                    self.show_cover(pixmap)
                    self.cover_note.setText(f"Capa: {found.name} (da pasta do CD)")
                    return

        self.show_cover(None)
        self.cover_note.setText("Não achei a capa. Arraste uma imagem para cá ou use Visual > Trocar capa…")

    def choose_cover(self):
        path, _ = QFileDialog.getOpenFileName(self, "Escolha a imagem da capa", self.last_dir(), IMAGE_FILTER)
        if path:
            self.set_custom_cover(Path(path))

    def set_custom_cover(self, path: Path):
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            QMessageBox.information(self, APP_NAME, "Não consegui abrir essa imagem.")
            return
        self.custom_cover = pixmap
        self.act_auto.setEnabled(True)
        self.refresh_cover()

    def use_auto_cover(self):
        """Volta a procurar a capa sozinho (dentro da música ou na pasta do CD)."""
        self.custom_cover = None
        self.act_auto.setEnabled(False)
        self.refresh_cover()

    # ---------------------------------------------------------------- modo palco
    def toggle_stage(self):
        self.stage_mode = not self.stage_mode
        for widget in self._stage_hidden:
            widget.setVisible(not self.stage_mode)
        self.menuBar().setVisible(not self.stage_mode)
        if self.stage_mode:
            self.showFullScreen()
        else:
            self.showNormal()

    def leave_stage(self):
        if self.stage_mode:
            self.toggle_stage()

    # ---------------------------------------------------------------- sobre
    def show_about(self):
        QMessageBox.about(
            self,
            f"Sobre o {APP_NAME}",
            f"<b>{APP_NAME}</b> {APP_VERSION}<br><br>"
            "Um tocador de música em que a capa do álbum gira como um disco de vinil.<br><br>"
            "Dicas: arraste uma pasta de CD para a janela; ao minimizar, aparece o mini player "
            "no canto da tela; F11 liga o modo palco.",
        )

    # ---------------------------------------------------------------- retomar de onde parou
    def save_session(self):
        if not self.playlist:
            return
        position = self.player.position() if self.index >= 0 else 0
        self.settings.setValue("session", session.encode(self.playlist, self.index, position, self.titles))

    def restore_session(self) -> bool:
        data = session.decode(self.settings.value("session", ""))
        if data is None:
            return False
        self.set_playlist(data["playlist"], autoplay=False, start=data["index"], position=data["position"],
                          titles=data["titles"])
        return True

    # ---------------------------------------------------------------- arrastar e soltar
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() if u.isLocalFile() else u.toString() for u in event.mimeData().urls()]
        self.open_paths(paths)
        event.acceptProposedAction()

    # ---------------------------------------------------------------- mini player
    def changeEvent(self, event):
        """Minimizou: a música continua e aparece o mini player no canto da tela."""
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                if self.index >= 0:  # só faz sentido se há música carregada
                    self.mini.show_in_corner()
            else:
                self.mini.hide()
        super().changeEvent(event)

    def restore_from_mini(self):
        self.mini.hide()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_app(self):
        """Botão X do mini player (ou Arquivo > Sair): guarda onde parou, para a música e fecha."""
        self.save_session()
        self.player.stop()
        self.mini.hide()
        QApplication.quit()

    def closeEvent(self, event):
        self.save_session()
        self.player.stop()
        self.mini.hide()
        event.accept()


def main():
    if sys.platform.startswith("linux"):
        # No Ubuntu, o modo "xcb" deixa o mini player ficar no canto e sempre por cima;
        # se o xcb não existir, o Qt cai automaticamente para o Wayland.
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb;wayland")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setDesktopFileName("vinyl-player")
    app.setStyle("Fusion")

    win = PlayerWindow()  # aplica o tema salvo (cores) logo ao abrir
    win.show()

    if len(sys.argv) > 1:
        # "Abrir com o Vinyl Player" (clique direito numa música) passa os arquivos aqui
        win.open_paths(sys.argv[1:])
    else:
        win.restore_session()  # volta para onde a última sessão parou (sem começar a tocar)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
