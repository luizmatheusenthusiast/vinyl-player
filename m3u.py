"""Salvar e abrir listas de reprodução no formato .m3u / .m3u8."""

from __future__ import annotations

import os
from pathlib import Path

from sources import is_url


def write_m3u(path, tracks) -> None:
    """Grava a lista; caminhos dentro da mesma pasta ficam relativos (a lista pode ser movida)."""
    path = Path(path)
    lines = ["#EXTM3U"]
    for track in tracks:
        if is_url(track):
            lines.append(str(track))
            continue
        try:
            entry = os.path.relpath(track, path.parent)
        except ValueError:  # Windows: outro disco
            entry = str(track)
        lines.append(entry.replace("\\", "/") if not Path(entry).is_absolute() else str(track))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_m3u(path) -> list[str]:
    """Lê a lista e devolve só os arquivos que existem."""
    path = Path(path)
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    result: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if is_url(line):
            result.append(line)
            continue
        candidate = Path(line.replace("\\", "/"))
        if not candidate.is_absolute():
            candidate = path.parent / candidate
        if candidate.is_file():
            result.append(str(candidate))
    return result
