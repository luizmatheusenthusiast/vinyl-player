"""Leitura das informações da música e busca automática da capa.

A capa é procurada em dois lugares:
  1. dentro do próprio arquivo de música (capa embutida nas tags);
  2. na pasta do CD/álbum (cover.jpg, folder.jpg, capa.png, front.jpg...).
Este arquivo não depende do Qt, então pode ser testado sozinho.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from pathlib import Path

try:
    import mutagen
    from mutagen.flac import Picture
except ImportError:  # sem o mutagen o programa funciona, só não lê as tags
    mutagen = None
    Picture = None

AUDIO_EXTENSIONS = {".mp3", ".flac", ".ogg", ".oga", ".opus", ".wav", ".m4a", ".aac", ".wma"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# nomes de arquivo que costumam ser a capa da frente
GOOD_NAMES = ("cover", "folder", "front", "album", "capa", "frente", "artwork", "albumart")
# nomes que costumam ser outra coisa (verso, encarte, miniatura...)
BAD_NAMES = ("back", "traseira", "verso", "tray", "inlay", "booklet", "encarte", "thumb", "small")
# subpastas onde os scans do CD costumam ficar
ART_FOLDERS = {"artwork", "scans", "scan", "covers", "cover", "capa", "capas", "art", "images"}

MIN_IMAGE_BYTES = 5 * 1024  # ignora ícones minúsculos


@dataclass
class TrackInfo:
    title: str = ""
    artist: str = ""
    album: str = ""
    cover_data: bytes | None = None  # bytes da imagem embutida, se houver


# ---------------------------------------------------------------------- pasta do CD
def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _score(path: Path) -> int:
    stem = path.stem.lower()
    score = 0
    if any(word in stem for word in GOOD_NAMES):
        score += 10
    if stem in GOOD_NAMES:
        score += 5
    if any(word in stem for word in BAD_NAMES):
        score -= 20
    return score


def _best_image_in(folder: Path) -> Path | None:
    try:
        entries = list(folder.iterdir())
    except OSError:
        return None
    images = [
        p
        for p in entries
        if p.is_file()
        and p.suffix.lower() in IMAGE_EXTENSIONS
        and not p.name.startswith(".")
        and _size(p) >= MIN_IMAGE_BYTES
    ]
    if not images:
        return None
    best = max(images, key=lambda p: (_score(p), _size(p)))
    return best if _score(best) >= 0 else None  # só tem "verso"/"encarte"? então nada


def _looks_like_disc_folder(folder: Path) -> bool:
    """Pastas como 'CD1', 'Disc 2', 'Disco 1' ficam dentro da pasta do álbum."""
    return re.match(r"^(cd|disc|disco|disk)\s*[-_ ]?\d+", folder.name, re.IGNORECASE) is not None


def find_folder_cover(audio_path) -> Path | None:
    """Procura a imagem da capa na pasta da música (e na pasta do álbum, se for 'CD1')."""
    folder = Path(audio_path).parent

    candidates = [folder]
    try:
        candidates += [d for d in folder.iterdir() if d.is_dir() and d.name.lower() in ART_FOLDERS]
    except OSError:
        pass
    if _looks_like_disc_folder(folder):
        candidates.append(folder.parent)

    for candidate in candidates:
        found = _best_image_in(candidate)
        if found is not None:
            return found
    return None


# ---------------------------------------------------------------------- tags do arquivo
def _first(value) -> str:
    if not value:
        return ""
    if isinstance(value, (list, tuple)):
        value = value[0]
    return str(value).strip()


def _embedded_cover(path) -> bytes | None:
    audio = mutagen.File(path)
    if audio is None:
        return None

    # FLAC e parecidos
    pictures = getattr(audio, "pictures", None)
    if pictures:
        front = [pic for pic in pictures if pic.type == 3]
        return (front or list(pictures))[0].data

    tags = audio.tags
    if tags is None:
        return None

    # MP3 (ID3)
    getall = getattr(tags, "getall", None)
    if getall is not None:
        apics = getall("APIC")
        if apics:
            front = [a for a in apics if a.type == 3]
            return (front or apics)[0].data
        return None

    # M4A / MP4
    if "covr" in tags:
        covers = tags["covr"]
        if covers:
            return bytes(covers[0])

    # OGG / Opus
    for encoded in tags.get("metadata_block_picture", []):
        return Picture(base64.b64decode(encoded)).data

    return None


def read_track_info(path) -> TrackInfo:
    """Lê título, artista, álbum e a capa embutida. Nunca dá erro: na dúvida, volta vazio."""
    info = TrackInfo()
    if mutagen is None:
        return info

    try:
        easy = mutagen.File(path, easy=True)
        if easy is not None and easy.tags:
            info.title = _first(easy.tags.get("title"))
            info.artist = _first(easy.tags.get("artist"))
            info.album = _first(easy.tags.get("album"))
    except Exception:
        pass

    try:
        info.cover_data = _embedded_cover(path)
    except Exception:
        pass

    return info


# ---------------------------------------------------------------------- listas de músicas
def natural_key(text: str):
    """Ordem 'natural': faixa2 vem antes de faixa10."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def list_audio_files(folder) -> list[Path]:
    """Todas as músicas de uma pasta (incluindo subpastas como CD1/CD2), em ordem."""
    folder = Path(folder)
    files = [
        p
        for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS and not p.name.startswith(".")
    ]
    return sorted(files, key=lambda p: natural_key(str(p.relative_to(folder))))
