"""Orquestracao: coleta -> processamento -> geocodificacao -> cache."""
import json
import datetime as dt

from .config import load_config, data_path
from .coleta import coletar
from .processa import processar_item
from .geocode import GeoCoder, rep_rodovias

RESULT_FILE = data_path("resultados_cache.json")


def _serial(item):
    it = dict(item)
    p = it.get("publicado")
    it["publicado"] = p.isoformat() if hasattr(p, "isoformat") else None
    it.pop("origem_meta", None)
    return it


def _parse_dt(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s)
    except Exception:
        return None


def salvar_resultados(itens, meta):
    payload = {"meta": meta, "itens": [_serial(i) for i in itens]}
    try:
        with open(RESULT_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1, default=str)
    except Exception:
        pass


def carregar_resultados():
    try:
        with open(RESULT_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    for it in payload.get("itens", []):
        it["publicado"] = _parse_dt(it.get("publicado"))
    return payload


def executar(cfg=None, fetch_fn=None, usar_nominatim=True, sleep_s=1.0,
             status_cb=None):
    """Roda a coleta completa e devolve (itens, meta). Tambem grava o cache."""
    cfg = cfg or load_config()
    crus = coletar(cfg, fetch_fn=fetch_fn, sleep_s=sleep_s,
                   status_cb=status_cb)
    geo = GeoCoder(cfg, usar_nominatim=usar_nominatim)
    rod_rep = rep_rodovias(cfg)
    itens = []
    for c in crus:
        proc = processar_item(c, cfg)
        proc.update(geo.localizar(proc, rod_rep))
        itens.append(proc)
    geo.salvar()
    itens.sort(key=lambda x: x.get("publicado") or dt.datetime.min,
               reverse=True)
    meta = {"atualizado_em": dt.datetime.now().isoformat(),
            "total": len(itens)}
    salvar_resultados(itens, meta)
    return itens, meta
