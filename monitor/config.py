"""Carregamento de configuracao, dados auxiliares e utilitarios de texto."""
import os
import json
import unicodedata

try:
    import yaml
except ImportError:  # mensagem amigavel se faltar dependencia
    yaml = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

DEFAULT_APP = {
    "titulo": "Monitoramento de Rodovias",
    "janela_dias": 7,
    "intervalo_auto_min": 5,
    "max_por_consulta": 8,
    "periodo_default": 1,
    "linhas_raio_km": 40,
    "buscar_hubs": True,
    "fetch_artigo": True,
    "idioma_news": "pt-BR",
    "pais_news": "BR",
}

# Termos usados para montar a busca no Google News (grupo OR).
# A filtragem de relevancia usa a lista completa em config.yaml -> palavras_problema.
PALAVRAS_BUSCA = [
    "interdicao", "interditada", "acidente", "bloqueio",
    "transito", "congestionamento", "tombamento", "deslizamento",
    "alagamento", "obras",
]


def data_path(*parts):
    return os.path.join(DATA_DIR, *parts)


def normalizar(txt):
    """Minusculas, sem acentos, sem espacos nas pontas."""
    if not txt:
        return ""
    txt = unicodedata.normalize("NFKD", str(txt))
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return txt.lower().strip()


def load_config(path=None):
    if yaml is None:
        raise RuntimeError(
            "PyYAML nao instalado. Rode: pip install -r requirements.txt"
        )
    path = path or os.path.join(BASE_DIR, "config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    app = dict(DEFAULT_APP)
    app.update(cfg.get("app") or {})
    cfg["app"] = app
    cfg.setdefault("palavras_problema", [])
    cfg.setdefault("rodovias", [])
    cfg.setdefault("hubs", [])
    fr = {"arquivo": "", "janela_min": 60, "raio_km": 15, "mostrar": True}
    fr.update(cfg.get("frota") or {})
    cfg["frota"] = fr
    return cfg


def load_builtin_coords():
    """{ 'CIDADE': [lat, lon, 'UF'] }"""
    try:
        with open(data_path("coords_builtin.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_cidades():
    """Lista de cidades da malha (planilha)."""
    try:
        with open(data_path("cidades.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def load_linhas():
    """Lista de linhas (pares origem-destino) da malha."""
    try:
        with open(data_path("linhas.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def load_rotas():
    """Rotas das linhas (paradas com cidade/coordenada)."""
    try:
        with open(data_path("linhas_rotas.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def uf_por_cidade(cfg):
    """Mapa CIDADE_NORMALIZADA -> UF a partir das coords builtin e dos hubs."""
    m = {}
    for nome, val in load_builtin_coords().items():
        if isinstance(val, list) and len(val) >= 3 and val[2]:
            m[normalizar(nome)] = val[2]
    for h in cfg.get("hubs", []):
        if h.get("uf"):
            m[normalizar(h["nome"])] = h["uf"]
    return m
