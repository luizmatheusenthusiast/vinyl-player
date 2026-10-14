"""Temas visuais do Vinyl Player.

Cada tema define as cores da janela e como a vitrola é desenhada:
  - view "side": vitrola vista de lado (inclinada), com a base e o cenário;
  - view "top":  disco visto de cima, no estilo escuro original.
Para criar um tema novo, copie um dos temas abaixo, mude as cores e coloque em THEMES.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from string import Template


@dataclass(frozen=True)
class Theme:
    key: str
    label: str          # nome mostrado no menu Visual > Tema
    view: str           # "side" ou "top"

    # --- janela ---
    bg: str
    bg_alt: str
    list_bg: str
    panel: str
    panel_hover: str
    border: str
    text: str
    muted: str
    disabled: str
    accent: str
    accent_hover: str
    on_accent: str      # cor do texto e dos ícones sobre a cor de destaque

    # --- disco e braço ---
    label_color: str    # rótulo do disco quando não há capa
    arm_metal: str
    arm_dark: str

    # --- ícones, disco e detalhes ---
    icon: str = "#f2f2f2"     # cor dos ícones sobre o fundo da janela
    vinyl: str = "#121212"    # cor do disco
    led: str = "#ff504a"      # luz de "ligado" na frente da base
    knob: str = ""            # botões na frente da base (vazio = usa "brass")

    # --- vitrola vista de lado ---
    wood_top: str = "#9a6a40"      # tampo da base
    wood_front: str = "#6b4326"    # frente da base
    wood_dark: str = "#3f2514"     # pés e sombras
    platter_metal: str = "#b4b4ba"
    platter_dark: str = "#5a5a60"
    brass: str = "#c9a24a"
    grain: int = 8                 # linhas de veio do tampo (0 = liso)
    grain_alpha: int = 22
    trim: str = ""                 # filete colorido na borda da base
    trim_double: bool = False      # filete duplo (art déco)
    glow: str = ""                 # brilho de neon em volta da base e do prato

    # --- cenário ---
    backdrop: str = ""             # "stars", "moon", "sun" ou "sunburst"
    props: str = ""                # objetos atrás da base: "mug", "plant", "planet"


VITROLA = Theme(
    key="vitrola",
    label="Vitrola (madeira clássica)",
    view="side",
    bg="#2a1d16", bg_alt="#33241a", list_bg="#32231a",
    panel="#4a3424", panel_hover="#5c4230", border="#664a35",
    text="#f1e6d2", muted="#b59f84", disabled="#8a7560",
    accent="#b5651d", accent_hover="#cc7a2e", on_accent="#fff8ec",
    label_color="#c97a2b", arm_metal="#d9c28a", arm_dark="#4a3a22",
    icon="#f6ecda",
)

CLASSICO = Theme(
    key="classico",
    label="Clássico (disco visto de cima)",
    view="top",
    bg="#1c1c1f", bg_alt="#25252a", list_bg="#232327",
    panel="#2d2d33", panel_hover="#3a3a42", border="#3a3a42",
    text="#e8e8e8", muted="#9a9aa5", disabled="#6a6a72",
    accent="#aa2832", accent_hover="#c4323d", on_accent="#ffffff",
    label_color="#aa2832", arm_metal="#cdcdd2", arm_dark="#46464c",
)

NEON = Theme(
    key="neon",
    label="Neon Noturno (synthwave)",
    view="side",
    bg="#0d0b1e", bg_alt="#15122e", list_bg="#120f28",
    panel="#231c4a", panel_hover="#32286a", border="#41328a",
    text="#f3e9ff", muted="#a597dc", disabled="#6e63a0",
    accent="#e0187f", accent_hover="#ff3d9a", on_accent="#ffffff",
    label_color="#00cfe8", arm_metal="#9ff3ff", arm_dark="#2a2550",
    icon="#f3e9ff", vinyl="#080410", led="#00ffa3", knob="#ff2e97",
    wood_top="#241b52", wood_front="#150f33", wood_dark="#06040f",
    platter_metal="#3a3470", platter_dark="#171236",
    grain=0, trim="#00e5ff", glow="#ff2e97",
    backdrop="sun",
)

MINIMAL = Theme(
    key="minimal",
    label="Minimal Branco (claro)",
    view="side",
    bg="#f4f2ee", bg_alt="#ebe8e2", list_bg="#fbfaf8",
    panel="#e6e2da", panel_hover="#d9d4ca", border="#cdc7ba",
    text="#2b2b2b", muted="#7a766d", disabled="#aaa59b",
    accent="#e8591a", accent_hover="#f26b2d", on_accent="#ffffff",
    label_color="#e8591a", arm_metal="#c9c9ce", arm_dark="#55555b",
    icon="#2b2b2b", vinyl="#151515", led="#e8591a", knob="#e8591a",
    wood_top="#fbfaf6", wood_front="#e1ddd3", wood_dark="#a8a398",
    platter_metal="#d4d4d8", platter_dark="#9d9da3",
    grain=0,
)

DECO = Theme(
    key="deco",
    label="Art Déco Dourado",
    view="side",
    bg="#12100c", bg_alt="#1a1712", list_bg="#17140f",
    panel="#2a2418", panel_hover="#3a3120", border="#6b5a2e",
    text="#f3e6c4", muted="#b8a574", disabled="#7d7050",
    accent="#c9a227", accent_hover="#ddb83a", on_accent="#1a1408",
    label_color="#c9a227", arm_metal="#e6c768", arm_dark="#5a4818",
    icon="#f3e6c4", vinyl="#0b0b0b", led="#ffb347", knob="#c9a227",
    wood_top="#1c1a16", wood_front="#0e0d0a", wood_dark="#050504",
    platter_metal="#d4b45a", platter_dark="#7a6020",
    grain=0, trim="#c9a227", trim_double=True,
    backdrop="sunburst",
)

LOFI = Theme(
    key="lofi",
    label="Lo-fi Café (aconchegante)",
    view="side",
    bg="#2b2236", bg_alt="#342a42", list_bg="#30263e",
    panel="#46385a", panel_hover="#574770", border="#6a5a86",
    text="#f6e8ee", muted="#c1adc9", disabled="#8d7b9a",
    accent="#e8799a", accent_hover="#f08fae", on_accent="#2b1425",
    label_color="#f08aa5", arm_metal="#f6e8ee", arm_dark="#7a6290",
    icon="#f6e8ee", vinyl="#2e1f45", led="#9af0c4", knob="#e8799a",
    wood_top="#d9b48f", wood_front="#b58a62", wood_dark="#7a5a3a",
    platter_metal="#eadcf0", platter_dark="#a894ae",
    grain=6, grain_alpha=20,
    backdrop="moon", props="mug,plant",
)

COSMOS = Theme(
    key="cosmos",
    label="Cosmos (espacial)",
    view="side",
    bg="#060a1a", bg_alt="#0b1230", list_bg="#0a1030",
    panel="#16224d", panel_hover="#1f2f66", border="#2c3f85",
    text="#e6efff", muted="#8fa4d9", disabled="#566596",
    accent="#3a7bff", accent_hover="#5a93ff", on_accent="#ffffff",
    label_color="#6a4cff", arm_metal="#cfe0ff", arm_dark="#2a3a6a",
    icon="#e6efff", vinyl="#0a0e22", led="#6dffd5", knob="#7fb2ff",
    wood_top="#1d2a52", wood_front="#121a38", wood_dark="#070b1c",
    platter_metal="#9fb4e8", platter_dark="#3b4a7a",
    grain=10, grain_alpha=14, trim="#7fb2ff", glow="#3a7bff",
    backdrop="stars", props="planet",
)

THEMES: dict[str, Theme] = {
    t.key: t for t in (VITROLA, CLASSICO, NEON, MINIMAL, DECO, LOFI, COSMOS)
}
DEFAULT_THEME = VITROLA.key


def get_theme(key) -> Theme:
    """Devolve o tema pelo nome; se o nome não existir, usa o padrão."""
    return THEMES.get(key) or THEMES[DEFAULT_THEME]


_WINDOW_STYLE = Template(
    """
QWidget { background: $bg; color: $text; font-size: 14px; }
QLabel#muted { color: $muted; font-size: 12px; }
QPushButton { background: $panel; border: 1px solid $border; border-radius: 6px; padding: 7px 12px; }
QPushButton:hover { background: $panel_hover; }
QPushButton:disabled { color: $disabled; background: $bg_alt; }
QPushButton#primary { background: $accent; border: 1px solid $accent_hover; color: $on_accent; font-weight: bold; }
QPushButton#primary:hover { background: $accent_hover; }
QPushButton#play { background: $accent; border: none; border-radius: 24px; padding: 0; }
QPushButton#play:hover { background: $accent_hover; }
QPushButton#transport { background: transparent; border: none; border-radius: 18px; padding: 0; }
QPushButton#transport:hover { background: $panel_hover; }
QPushButton#mode { background: transparent; border: none; border-radius: 18px; padding: 0; }
QPushButton#mode:hover { background: $panel_hover; }
QPushButton#mode:checked { background: $accent; }
QListWidget { background: $list_bg; border: 1px solid $border; border-radius: 6px; }
QListWidget::item { padding: 4px; }
QListWidget::item:selected { background: $accent; color: $on_accent; }
QLineEdit { background: $list_bg; border: 1px solid $border; border-radius: 6px; padding: 5px 8px; }
QSlider::groove:horizontal { height: 4px; background: $border; border-radius: 2px; }
QSlider::handle:horizontal { background: $text; width: 12px; margin: -5px 0; border-radius: 6px; }
QSlider::sub-page:horizontal { background: $accent; border-radius: 2px; }
QMenuBar { background: $bg; color: $text; }
QMenuBar::item { background: transparent; padding: 5px 10px; }
QMenuBar::item:selected { background: $panel_hover; }
QMenu { background: $panel; color: $text; border: 1px solid $border; }
QMenu::item { padding: 6px 24px; }
QMenu::item:selected { background: $accent; color: $on_accent; }
QMenu::item:disabled { color: $disabled; }
QMenu::separator { height: 1px; background: $border; margin: 4px 8px; }
QToolTip { background: $panel; color: $text; border: 1px solid $border; }
"""
)

_MINI_STYLE = Template(
    """
QWidget { background: transparent; color: $text; font-size: 13px; }
QLabel#title { font-weight: bold; }
QLabel#muted { color: $muted; font-size: 11px; }
QPushButton { background: transparent; border: none; border-radius: 14px; padding: 0; }
QPushButton:hover { background: $panel_hover; }
QPushButton#play { background: $accent; border-radius: 17px; }
QPushButton#play:hover { background: $accent_hover; }
QPushButton#close:hover { background: $accent; }
QToolTip { background: $panel; color: $text; border: 1px solid $border; }
QMenu { background: $panel; border: 1px solid $border; }
QMenu::item { padding: 6px 20px; }
QMenu::item:selected { background: $accent; color: $on_accent; }
QMenu::separator { height: 1px; background: $border; margin: 4px 8px; }
"""
)


def build_stylesheet(theme: Theme) -> str:
    """Folha de estilo da janela principal."""
    return _WINDOW_STYLE.substitute(asdict(theme))


def mini_stylesheet(theme: Theme) -> str:
    """Folha de estilo do mini player (fundo transparente: quem pinta é o paintEvent)."""
    return _MINI_STYLE.substitute(asdict(theme))
