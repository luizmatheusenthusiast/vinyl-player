"""Guarda e recupera "onde eu parei": lista de músicas, faixa atual e posição."""

from __future__ import annotations

import json
import os

from sources import is_url


def encode(playlist: list[str], index: int, position_ms: int, titles: dict | None = None) -> str:
    web = {p: t for p, t in (titles or {}).items() if p in playlist}
    return json.dumps(
        {"playlist": list(playlist), "index": int(index), "position": int(max(0, position_ms)), "titles": web},
        ensure_ascii=False,
    )


def decode(text) -> dict | None:
    """Devolve {"playlist", "index", "position"} só com músicas que ainda existem, ou None."""
    try:
        data = json.loads(str(text))
        files = [p for p in data["playlist"] if isinstance(p, str)]
        index = int(data["index"])
        position = max(0, int(data["position"]))
    except (ValueError, KeyError, TypeError):
        return None
    if not files or not (0 <= index < len(files)):
        return None
    current = files[index]
    kept = [p for p in files if is_url(p) or os.path.isfile(p)]
    if not kept:
        return None
    if current in kept:
        index = kept.index(current)
    else:
        index, position = 0, 0
    titles = data.get("titles") if isinstance(data.get("titles"), dict) else {}
    return {"playlist": kept, "index": index, "position": position,
            "titles": {p: str(t) for p, t in titles.items() if p in kept}}
