#!/usr/bin/env bash
# Cria o instalador do Vinyl Player para Ubuntu (arquivo .deb).
# Como usar:   bash build_linux.sh
set -euo pipefail
cd "$(dirname "$0")"

NAME="vinyl-player"
# a versão vem da variável APP_VERSION (usada pelo GitHub) ou do arquivo version.py
VERSION="${APP_VERSION:-$(sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' version.py)}"

echo "============================================================"
echo "  Criando o instalador do Vinyl Player para Ubuntu (.deb)"
echo "  (a primeira vez demora alguns minutos; pode deixar rodando)"
echo "============================================================"

# --- 1. ferramentas do sistema ---------------------------------------------
need=()
command -v python3 >/dev/null || need+=(python3)
command -v dpkg-deb >/dev/null || need+=(dpkg-dev)
tmp_venv="$(mktemp -d)"
python3 -m venv "$tmp_venv/t" >/dev/null 2>&1 || need+=(python3-venv)
rm -rf "$tmp_venv"
if [ "${#need[@]}" -gt 0 ]; then
    echo "[1/4] Instalando ferramentas que faltam: ${need[*]} (vai pedir sua senha)"
    sudo apt-get update
    sudo apt-get install -y "${need[@]}"
else
    echo "[1/4] Ferramentas do sistema: ok"
fi
ARCH="$(dpkg --print-architecture)"

# --- 2. ambiente Python e programa -----------------------------------------
echo "[2/4] Preparando o ambiente..."
[ -d .venv ] || python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

echo "[3/4] Gerando o programa..."
pyinstaller --noconfirm --clean --windowed --name "$NAME" --add-data "assets:assets" main.py

# --- 3. pacote .deb ---------------------------------------------------------
echo "[4/4] Montando o pacote .deb..."
PKG="build/deb/${NAME}_${VERSION}_${ARCH}"
rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" "$PKG/opt/$NAME" "$PKG/usr/bin" \
         "$PKG/usr/share/applications" "$PKG/usr/share/icons/hicolor/256x256/apps"

cp -r "dist/$NAME/." "$PKG/opt/$NAME/"
ln -s "/opt/$NAME/$NAME" "$PKG/usr/bin/$NAME"
cp assets/icon.png "$PKG/usr/share/icons/hicolor/256x256/apps/$NAME.png"

cat > "$PKG/usr/share/applications/$NAME.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Vinyl Player
Comment=Tocador de música com disco de vinil girando
Exec=$NAME %F
Icon=$NAME
Terminal=false
Categories=AudioVideo;Audio;Player;
MimeType=audio/mpeg;audio/flac;audio/ogg;audio/x-wav;audio/mp4;audio/x-flac;
StartupWMClass=vinyl-player
EOF

SIZE_KB="$(du -sk "$PKG/opt" | cut -f1)"
cat > "$PKG/DEBIAN/control" <<EOF
Package: $NAME
Version: $VERSION
Section: sound
Priority: optional
Architecture: $ARCH
Installed-Size: $SIZE_KB
Depends: libxcb-cursor0, libxkbcommon-x11-0, libgl1
Maintainer: Vinyl Player <vinyl-player@localhost>
Description: Tocador de música com disco de vinil girando
 Mostra a capa do álbum girando como um disco de vinil, com braço de agulha.
 Encontra a capa sozinho dentro da música ou na pasta do CD.
EOF

find "$PKG" -type d -exec chmod 0755 {} +
OUT="${NAME}_${VERSION}_${ARCH}.deb"
dpkg-deb --root-owner-group --build "$PKG" "$OUT"

echo
echo "============================================================"
echo "  PRONTO!  Seu instalador: $(pwd)/$OUT"
echo "  Para instalar, dê dois cliques nele (abre a Central de"
echo "  Programas) ou rode:  sudo apt install ./$OUT"
echo "  Depois é só procurar por \"Vinyl Player\" no menu de aplicativos."
echo "============================================================"
