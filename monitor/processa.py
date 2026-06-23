"""Resumo extrativo (sem API), classificacao e extracao de local."""
import re
import html

from .config import normalizar, load_cidades

try:
    import requests
except ImportError:
    requests = None

try:
    import trafilatura
except ImportError:
    trafilatura = None

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")

STOPWORDS = set("""
a o e de da do das dos em no na nos nas um uma uns umas para por com sem sob
sobre que se ao aos as os e ou mas como apos ate entre desde contra ja nao sim
foi sao era e eh esta estao tem tinha havia ha sera seu sua seus suas este esta
isso isto aquele aquela la aqui ali muito mais menos tambem entao depois antes
quando onde quem qual quais cujo cuja apenas cerca toda todo todos todas pela
pelo pelos pelas num numa dele dela deles delas nesta neste nessa nesse
""".split())

# Categorias por prioridade (a primeira que casar vira a principal).
CATEGORIAS = [
    ("Interdicao", "#9c2742", [
        "interdit", "bloque", "pista interditada", "fechada", "fechado",
        "interdicao", "queda de barreira", "deslizamento", "desabamento",
        "cratera", "interrompid"]),
    ("Acidente", "#d23a2e", [
        "acidente", "colisao", "capotamento", "capotou", "tombamento",
        "tombou", "engavetamento", "atropel", "feridos", "morre", "morto",
        "vitima", "batida"]),
    ("Clima/Natureza", "#5e86d6", [
        "alagamento", "alagada", "alagado", "neblina", "chuva", "temporal",
        "enchente", "queda de arvore", "vendaval"]),
    ("Manifestacao", "#46467f", [
        "protesto", "manifestacao", "manifestantes", "bloqueio de"]),
    ("Obras", "#cf9500", [
        "obras", "manutencao", "recuperacao", "recapeamento", "obra"]),
    ("Congestionamento", "#f7c01a", [
        "congestionamento", "transito", "lentidao", "fila", "parado",
        "morosidade"]),
]

SEV_ALTA = ["morre", "morto", "morte", "vitima", "feridos", "interdit",
            "bloque", "fechada", "deslizamento", "capotamento", "desabamento",
            "totalmente", "interrompid", "grave"]
SEV_MEDIA = ["acidente", "congestionamento", "tombamento", "alagamento",
             "parcial", "lentidao", "obras"]

_CIDADES = None
_CIDADES_ORD = None


def _cidades():
    global _CIDADES, _CIDADES_ORD
    if _CIDADES is None:
        lst = load_cidades()
        _CIDADES = {normalizar(c): c for c in lst}
        _CIDADES_ORD = sorted(_CIDADES.keys(), key=len, reverse=True)
    return _CIDADES, _CIDADES_ORD


def limpar_html(txt):
    if not txt:
        return ""
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = html.unescape(txt)
    return re.sub(r"\s+", " ", txt).strip()


def baixar_artigo(url, timeout=20):
    """Texto principal do artigo. Resolve redirect do Google News e usa
    trafilatura quando disponivel. Retorna '' em falha."""
    if not url or requests is None:
        return ""
    try:
        r = requests.get(url, headers={"User-Agent": UA},
                         timeout=timeout, allow_redirects=True)
        final = r.url
        if "news.google" in final:
            return ""
        if trafilatura is not None:
            txt = trafilatura.extract(r.text, include_comments=False,
                                      include_tables=False) or ""
            return txt.strip()
        paras = re.findall(r"<p[^>]*>(.*?)</p>", r.text, flags=re.S | re.I)
        return limpar_html(" ".join(paras))[:4000]
    except Exception:
        return ""


def _sentencas(texto):
    texto = re.sub(r"\s+", " ", texto.strip())
    partes = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", texto)
    return [p.strip() for p in partes if len(p.strip()) > 25]


def resumir(texto, titulo="", max_sentencas=3, max_chars=420,
            termos_relevantes=None):
    """Resumo extrativo por frequencia de palavras + realce de termos."""
    texto = limpar_html(texto)
    if not texto:
        return limpar_html(titulo)
    sents = _sentencas(texto)
    if len(sents) <= max_sentencas:
        return (" ".join(sents) or limpar_html(titulo))[:max_chars]

    freq = {}
    for w in re.findall(r"[a-z0-9]+", normalizar(texto)):
        if w in STOPWORDS or len(w) < 3:
            continue
        freq[w] = freq.get(w, 0) + 1
    if not freq:
        return " ".join(sents[:max_sentencas])[:max_chars]
    fmax = max(freq.values())
    termos = [normalizar(t) for t in (termos_relevantes or [])]

    pont = []
    for i, s in enumerate(sents):
        ns = normalizar(s)
        score = sum(freq.get(w, 0) / fmax
                    for w in re.findall(r"[a-z0-9]+", ns))
        score = score / (len(ns.split()) + 1)
        if i < 3:
            score += 0.12 - i * 0.03
        if any(t and t in ns for t in termos):
            score += 0.25
        pont.append((score, i, s))

    melhores = sorted(pont, key=lambda x: x[0], reverse=True)[:max_sentencas]
    melhores = [s for _, _, s in sorted(melhores, key=lambda x: x[1])]
    resumo = " ".join(melhores).strip()
    if len(resumo) > max_chars:
        resumo = resumo[:max_chars].rsplit(" ", 1)[0] + "..."
    return resumo


def classificar(texto):
    n = normalizar(texto)
    categoria, cor = "Outros", "#6b6f86"
    for nome, c, termos in CATEGORIAS:
        if any(t in n for t in termos):
            categoria, cor = nome, c
            break
    if any(t in n for t in SEV_ALTA):
        sev = "Alta"
    elif any(t in n for t in SEV_MEDIA):
        sev = "Media"
    else:
        sev = "Baixa"
    return categoria, cor, sev


def extrair_local(texto, origem_meta=None, origem_tipo=None):
    """Retorna (cidade, km). cidade pode ser None."""
    cid_map, cid_ord = _cidades()
    n = normalizar(texto)
    cidade = None
    if origem_tipo == "hub" and origem_meta:
        cidade = origem_meta.get("nome")
    if not cidade:
        achados = []
        for cn in cid_ord:
            if len(cn) < 4:
                continue
            m = re.search(r"\b" + re.escape(cn) + r"\b", n)
            if m:
                achados.append((m.start(), -len(cn), cid_map[cn]))
        if achados:
            achados.sort()
            cidade = achados[0][2]
    km = None
    m = re.search(r"\bkm\s*\.?\s*(\d{1,4})", n)
    if m:
        km = m.group(1)
    return cidade, km


def processar_item(item, cfg):
    """Enriquece um item cru: resumo, categoria, severidade, local."""
    titulo = item.get("titulo", "")
    desc = item.get("descricao", "")
    base_texto = limpar_html(titulo + ". " + desc)

    texto_resumo = ""
    if cfg["app"].get("fetch_artigo", True):
        texto_resumo = baixar_artigo(item.get("link", ""))
    if not texto_resumo:
        texto_resumo = limpar_html(desc) or titulo

    meta = item.get("origem_meta") or {}
    termos = [item.get("origem_nome", "")] + (meta.get("aliases") or [])
    resumo = resumir(texto_resumo, titulo=titulo, termos_relevantes=termos)

    categoria, cor, sev = classificar(base_texto)
    cidade, km = extrair_local(
        base_texto, origem_meta=meta, origem_tipo=item.get("origem_tipo"))

    return {
        "titulo": titulo,
        "resumo": resumo,
        "link": item.get("link", ""),
        "fonte": item.get("fonte", ""),
        "publicado": item.get("publicado"),
        "rodovia": item.get("origem_nome", ""),
        "origem_tipo": item.get("origem_tipo", ""),
        "categoria": categoria,
        "cor": cor,
        "severidade": sev,
        "cidade": cidade,
        "km": km,
    }
