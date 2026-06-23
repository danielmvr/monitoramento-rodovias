"""Coleta de noticias via Google News RSS (sem chave de API)."""
import time
import urllib.parse
import datetime as dt

import feedparser

from .config import PALAVRAS_BUSCA, normalizar

try:
    import requests
except ImportError:
    requests = None

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")

GNEWS = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={gl}:pt-419"


def _fetch_url(url, timeout=20):
    """Baixa o conteudo de uma URL. Retorna bytes (ou b'' em caso de falha)."""
    if requests is not None:
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
            r.raise_for_status()
            return r.content
        except Exception:
            return b""
    # fallback: feedparser baixa sozinho
    return b""


def montar_query(alias, janela_dias):
    grupo = " OR ".join(PALAVRAS_BUSCA)
    termo = f'"{alias}" ({grupo}) when:{int(janela_dias)}d'
    return urllib.parse.quote(termo)


def url_busca(alias, cfg):
    app = cfg["app"]
    q = montar_query(alias, app.get("janela_dias", 7))
    hl = urllib.parse.quote(app.get("idioma_news", "pt-BR"))
    gl = urllib.parse.quote(app.get("pais_news", "BR"))
    return GNEWS.format(q=q, hl=hl, gl=gl)


def _parse_data(entry):
    for campo in ("published_parsed", "updated_parsed"):
        val = entry.get(campo)
        if val:
            try:
                return dt.datetime(*val[:6])
            except Exception:
                pass
    return None


def _fonte(entry):
    src = entry.get("source")
    if isinstance(src, dict):
        return src.get("title") or ""
    try:
        return entry.source.title
    except Exception:
        return ""


def buscar_alias(alias, cfg, fetch_fn=None):
    """Retorna lista de entradas cruas (dicts) para um alias de rodovia/cidade."""
    fetch_fn = fetch_fn or _fetch_url
    url = url_busca(alias, cfg)
    raw = fetch_fn(url)
    feed = feedparser.parse(raw) if raw else feedparser.parse(url)
    itens = []
    limite = cfg["app"].get("max_por_consulta", 8)
    for e in feed.entries[: max(1, limite) * 2]:
        itens.append({
            "titulo": (e.get("title") or "").strip(),
            "link": (e.get("link") or "").strip(),
            "descricao": e.get("summary", "") or e.get("description", ""),
            "publicado": _parse_data(e),
            "fonte": _fonte(e),
        })
    return itens[:limite]


def contem_problema(texto, palavras_problema):
    n = normalizar(texto)
    return any(normalizar(p) in n for p in palavras_problema)


def coletar(cfg, fetch_fn=None, sleep_s=1.0, status_cb=None):
    """Coleta por todas as rodovias (e hubs, se habilitado). Retorna lista
    de itens crus com a origem da busca (rodovia/hub) anexada e ja filtrados
    por relevancia + deduplicados."""
    palavras = cfg.get("palavras_problema", [])
    alvos = []
    for r in cfg.get("rodovias", []):
        for alias in (r.get("aliases") or [r["nome"]]):
            alvos.append(("rodovia", r["nome"], alias, r))
    if cfg["app"].get("buscar_hubs", True):
        for h in cfg.get("hubs", []):
            alias = f'{h["nome"]} rodovia'
            alvos.append(("hub", h["nome"], alias, h))

    vistos = set()
    resultado = []
    total = len(alvos)
    for i, (tipo, nome, alias, meta) in enumerate(alvos):
        if status_cb:
            status_cb(i + 1, total, f"{nome} ({alias})")
        try:
            entradas = buscar_alias(alias, cfg, fetch_fn=fetch_fn)
        except Exception:
            entradas = []
        for e in entradas:
            blob = f'{e["titulo"]} {e["descricao"]}'
            if not contem_problema(blob, palavras):
                continue
            # tem que mencionar a via (alias/nome) ou a cidade do hub
            ref = normalizar(nome) in normalizar(blob) or \
                normalizar(alias) in normalizar(blob)
            if tipo == "rodovia" and not ref:
                # aceita se mencionar qualquer alias da rodovia
                ref = any(normalizar(a) in normalizar(blob)
                          for a in (meta.get("aliases") or []))
            if not ref:
                continue
            chave = normalizar(e["titulo"])[:80]
            if chave in vistos or e["link"] in vistos:
                continue
            vistos.add(chave)
            vistos.add(e["link"])
            e = dict(e)
            e["origem_tipo"] = tipo
            e["origem_nome"] = nome
            e["origem_meta"] = meta
            resultado.append(e)
        if sleep_s:
            time.sleep(sleep_s)
    return resultado
