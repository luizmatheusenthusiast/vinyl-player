"""Endereços da internet: links diretos, rádios, listas .m3u/.pls, Google Drive, Dropbox e pastas de servidores.

Lógica sem Qt (dá para testar sozinha). Uma pasta de servidor (endereço terminado em "/") é
percorrida com as subpastas, procurando músicas, desde que o servidor mostre a lista de arquivos.
"""

from __future__ import annotations

import http.client
import posixpath
import re
from html.parser import HTMLParser
from dataclasses import dataclass
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

PLAYLIST_SUFFIXES = (".m3u", ".m3u8", ".pls")
MAX_PLAYLIST_ITEMS = 500
MAX_DOWNLOAD = 1_000_000  # só baixamos listas pequenas (1 MB), nunca músicas inteiras
USER_AGENT = "VinylPlayer/1.1 (+music player)"


class SourceError(Exception):
    """Erro com mensagem já pronta para mostrar ao usuário."""


@dataclass(frozen=True)
class Entry:
    title: str
    url: str


def is_url(text) -> bool:
    return str(text).strip().lower().startswith(("http://", "https://"))


def normalize_url(url: str) -> str:
    """Transforma links de "compartilhar" do Drive e do Dropbox em links de download direto."""
    url = url.strip()
    parts = urlparse(url)
    host = (parts.hostname or "").lower()

    if host == "drive.google.com":
        m = re.search(r"/file/d/([\w-]+)", parts.path)
        file_id = m.group(1) if m else (parse_qs(parts.query).get("id") or [""])[0]
        if "/folders/" in parts.path or "/drive/folders" in parts.path:
            raise SourceError(
                "O Google Drive não deixa programas lerem pastas sem uma chave de acesso. Opções: "
                "instale o Google Drive para computador (ou use o rclone) para a pasta aparecer no "
                "seu computador e abra-a com Arquivo → Abrir pasta; ou use o link de cada arquivo."
            )
        if not file_id:
            raise SourceError("Não entendi esse link do Google Drive.")
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    if host.endswith("dropbox.com"):
        query = {k: v[0] for k, v in parse_qs(parts.query).items() if k not in ("dl", "raw")}
        query["dl"] = "1"
        return urlunparse(parts._replace(query=urlencode(query)))

    return url


def display_name(url: str) -> str:
    """Nome legível para um endereço: o nome do arquivo, ou o site."""
    parts = urlparse(url)
    name = unquote(posixpath.basename(parts.path))
    name = posixpath.splitext(name)[0] if name else ""
    return name or parts.hostname or url


def is_playlist_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith(PLAYLIST_SUFFIXES)


def parse_playlist_text(text: str, base_url: str = "") -> list[Entry]:
    """Lê o texto de uma lista .m3u/.m3u8 ou .pls e devolve as entradas (endereços relativos viram completos)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    entries: list[Entry] = []

    if lines and lines[0].lower().startswith("[playlist]"):
        files: dict[str, str] = {}
        titles: dict[str, str] = {}
        for ln in lines[1:]:
            m = re.match(r"(?i)(file|title)(\d+)\s*=\s*(.*)", ln)
            if m:
                (files if m.group(1).lower() == "file" else titles)[m.group(2)] = m.group(3).strip()
        for number in sorted(files, key=int):
            target = urljoin(base_url, files[number]) if base_url else files[number]
            entries.append(Entry(titles.get(number) or display_name(target), target))
        return entries[:MAX_PLAYLIST_ITEMS]

    pending_title = ""
    for ln in lines:
        if ln.startswith("#"):
            if ln.upper().startswith("#EXTINF:") and "," in ln:
                pending_title = ln.split(",", 1)[1].strip()
            continue
        target = urljoin(base_url, ln) if base_url else ln
        entries.append(Entry(pending_title or display_name(target), target))
        pending_title = ""
    return entries[:MAX_PLAYLIST_ITEMS]


def fetch_text(url: str, timeout: float = 15.0) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 (só http/https chegam aqui)
            raw = response.read(MAX_DOWNLOAD)
    except Exception as exc:  # rede fora, 404, certificado...
        raise SourceError(f"Não consegui abrir o endereço ({exc.__class__.__name__}). Confira o link e a internet.") from exc
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


AUDIO_SUFFIXES = (".mp3", ".flac", ".ogg", ".oga", ".opus", ".wav", ".m4a", ".aac", ".wma")
MAX_FOLDER_DEPTH = 6     # quantos níveis de subpastas descer
MAX_FOLDER_PAGES = 120   # no máximo tantas pastas visitadas
MAX_FOLDER_FILES = 1000  # no máximo tantas músicas


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)


def parse_listing(html: str, page_url: str, root_url: str) -> tuple[list[str], list[str]]:
    """Lê a página de lista de arquivos de um servidor: devolve (músicas, subpastas) dentro de `root_url`."""
    parser = _LinkParser()
    parser.feed(html)
    root = urlparse(root_url)
    page = urlparse(page_url)
    files: list[str] = []
    folders: list[str] = []
    for href in parser.links:
        if href.startswith(("?", "#", "mailto:", "javascript:")):
            continue  # links de ordenar colunas etc.
        absolute = urljoin(page_url, href).split("#")[0].split("?")[0]
        target = urlparse(absolute)
        if target.scheme not in ("http", "https") or target.netloc != root.netloc:
            continue
        if not target.path.startswith(root.path):
            continue  # nunca sobe para fora da pasta pedida ("Parent Directory")
        if target.path == page.path:
            continue
        if target.path.endswith("/"):
            folders.append(absolute)
        elif target.path.lower().endswith(AUDIO_SUFFIXES):
            files.append(absolute)
    return list(dict.fromkeys(files)), list(dict.fromkeys(folders))


def _natural_key(text: str):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", unquote(text))]


def crawl_folder(root_url: str, fetch=None) -> list[Entry]:
    """Percorre uma pasta de servidor e suas subpastas atrás de músicas (na ordem natural: CD1 antes de CD2)."""
    fetch = fetch or fetch_text
    entries: list[Entry] = []
    seen: set[str] = set()
    pages = 0

    def walk(url: str, depth: int):
        nonlocal pages
        if url in seen or pages >= MAX_FOLDER_PAGES or len(entries) >= MAX_FOLDER_FILES:
            return
        seen.add(url)
        pages += 1
        try:
            html = fetch(url)
        except SourceError:
            if url == root_url:
                raise
            return  # uma subpasta com problema não derruba o resto
        files, folders = parse_listing(html, url, root_url)
        for file_url in sorted(files, key=_natural_key):
            if len(entries) >= MAX_FOLDER_FILES:
                return
            entries.append(Entry(display_name(file_url), file_url))
        if depth < MAX_FOLDER_DEPTH:
            for folder_url in sorted(folders, key=_natural_key):
                walk(folder_url, depth + 1)

    walk(root_url, 0)
    if not entries:
        raise SourceError(
            "Não encontrei músicas nessa pasta da internet. O servidor precisa mostrar a lista de "
            "arquivos (página \"Index of /…\") e o link deve terminar com /"
        )
    return entries


AUDIO_TYPES = ("audio/", "application/ogg", "video/ogg", "application/x-mpegurl-audio")
PLAYLIST_TYPES = ("audio/x-mpegurl", "audio/mpegurl", "application/x-mpegurl", "application/vnd.apple.mpegurl",
                  "audio/x-scpls", "application/pls+xml")
_URL_IN_PAGE = re.compile(r"""https?:(?:\\?/){2}[^\s"'<>()\\]+(?:\\/[^\s"'<>()\\]*)*""")


def probe(url: str, timeout: float = 12.0) -> tuple[str, str, str]:
    """Descobre o que há no endereço SEM baixar a música (rádio é infinita).

    Devolve (tipo, texto, nome): tipo = "stream" (áudio/rádio), "playlist" (texto de lista) ou "html" (página).
    """
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        response = urlopen(request, timeout=timeout)  # noqa: S310 (só http/https)
    except http.client.BadStatusLine:
        return "stream", "", ""  # Shoutcast antigo responde "ICY 200 OK", que não é HTTP de verdade
    except Exception as exc:
        raise SourceError(f"Não consegui abrir o endereço ({exc.__class__.__name__}). Confira o link e a internet.") from exc
    with response:
        headers = response.headers
        ctype = (headers.get("Content-Type") or "").split(";")[0].strip().lower()
        name = (headers.get("icy-name") or "").strip()
        if name or headers.get("icy-metaint") or headers.get("icy-br"):
            return "stream", "", name
        looks_playlist = ctype in PLAYLIST_TYPES or is_playlist_url(url)
        if looks_playlist or ctype in ("text/html", "application/xhtml+xml", "text/plain"):
            raw = response.read(MAX_DOWNLOAD)
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")
            if looks_playlist or text.lstrip().startswith(("#EXTM3U", "[playlist]")):
                return "playlist", text, ""
            return "html", text, ""
        return "stream", "", ""  # áudio ou tipo desconhecido: o player tenta tocar


def find_streams_in_page(html: str, page_url: str) -> list[str]:
    """Procura, numa página de rádio, o endereço do áudio (<audio>, <source>, links .mp3/.aac/.m3u/.pls)."""
    found: list[str] = []
    for raw in _URL_IN_PAGE.findall(html):
        candidate = raw.replace("\\/", "/").rstrip(".,;")
        path = urlparse(candidate).path.lower()
        if path.endswith(AUDIO_SUFFIXES + PLAYLIST_SUFFIXES + (".m3u8",)):
            found.append(candidate)
    parser = _LinkParser()
    parser.feed(html)
    for tag_src in re.findall(r"""<(?:audio|source)[^>]+src=["']([^"']+)["']""", html, flags=re.I):
        found.append(urljoin(page_url, tag_src))
    return list(dict.fromkeys(found))


def _is_hls(text: str) -> bool:
    return "#EXT-X-" in text  # lista HLS: o player toca a própria lista, não os pedacinhos


def resolve(text: str) -> list[Entry]:
    """Transforma o que o usuário colou em uma lista de músicas tocáveis."""
    url = text.strip()
    if not is_url(url):
        raise SourceError("O endereço precisa começar com http:// ou https://")
    url = normalize_url(url)
    path = urlparse(url).path.lower()
    if path.endswith(AUDIO_SUFFIXES):  # arquivo de música conhecido: toca direto
        return [Entry(display_name(url), url)]

    kind, body, name = probe(url)
    if kind == "stream":
        return [Entry(name or display_name(url), url)]
    if kind == "playlist":
        if _is_hls(body):
            return [Entry(display_name(url), url)]
        entries = [e for e in parse_playlist_text(body, url) if is_url(e.url)]
        if not entries:
            raise SourceError("Essa lista não tem nenhum endereço de música.")
        return entries

    # página da web: pasta de servidor (lista de arquivos) ou página de rádio com player
    files, folders = parse_listing(body, url, url) if path.endswith("/") else ([], [])
    if files or folders:
        return crawl_folder(url)
    streams = find_streams_in_page(body, url)
    if streams:
        return resolve_streams(streams)
    raise SourceError(
        "Esse link é uma página da web, não o endereço do áudio. Em rádios online, procure o link do "
        "\"stream\" (costuma terminar em .mp3, .aac, .m3u ou .pls, ou ter uma porta como :8000) "
        "na própria página da rádio e cole esse."
    )


def resolve_streams(urls: list[str]) -> list[Entry]:
    """Endereços achados dentro de uma página: listas viram suas músicas; o resto toca direto."""
    entries: list[Entry] = []
    for item in urls[:10]:
        if is_playlist_url(item) and not item.lower().endswith(".m3u8"):
            try:
                entries += [e for e in parse_playlist_text(fetch_text(item), item) if is_url(e.url)]
            except SourceError:
                continue
        else:
            entries.append(Entry(display_name(item), item))
    if not entries:
        raise SourceError("Achei links na página, mas nenhum funcionou como áudio.")
    return entries
