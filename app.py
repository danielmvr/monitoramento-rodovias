"""
Monitoramento de Rodovias - Linhas Guanabara
Painel Streamlit (visual padrao pixel Guanabara).
Execute com:  streamlit run app.py
"""
import os
import sys
import base64
import html
import subprocess
import datetime as dt

import streamlit as st
try:
    from streamlit_folium import st_folium
except ImportError:
    st_folium = None

from monitor import config as cfgmod
from monitor import pipeline, mapa
from monitor import frota
from monitor.processa import CATEGORIAS
from monitor import __version__ as VERSAO

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

BASE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(BASE, "logoGB.png")

st.set_page_config(page_title="Monitoramento de Rodovias - Guanabara",
                   page_icon=None, layout="wide")

CAT_NOMES = [c[0] for c in CATEGORIAS] + ["Outros"]
SEV_COR = {"Alta": "#d23a2e", "Media": "#cf9500", "Baixa": "#2e8b57"}
CHIP_CLARO = {"#f7c01a"}  # fundos claros usam texto escuro


def _txt_chip(cor):
    return "#161a2e" if str(cor).lower() in CHIP_CLARO else "#fff"


MAP_ICON = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" '
            'stroke="#ffffff" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round">'
            '<path d="M12 21s-6-5.686-6-10a6 6 0 1 1 12 0c0 4.314-6 10-6 10z"/>'
            '<circle cx="12" cy="11" r="2.5"/></svg>')

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');
:root{
  --ink:#161a2e; --ink2:#222743; --paper:#f6f3ea; --paperline:#ddd6c2;
  --primary:#46467f; --primaryd:#33335a; --blue:#5e86d6; --yellow:#f7c01a;
  --wine:#9c2742; --green:#2e8b57; --muted:#6b6f86; --line:#0d1024;
  --pix:"Press Start 2P","Courier New",monospace;
  --sans:"Segoe UI",system-ui,Arial,sans-serif;
  --shadow:5px 5px 0 0 var(--line); --shadowsm:3px 3px 0 0 var(--line);
}
.stApp{
  background:
    repeating-linear-gradient(0deg, rgba(255,255,255,.025) 0 2px, transparent 2px 4px),
    radial-gradient(circle at 25% -10%, #2b3160 0%, #161a2e 62%);
  background-attachment:fixed;
}
.block-container{ padding-top:4.5rem; max-width:1800px; }
header[data-testid="stHeader"]{ background:transparent; }
div[data-testid="stToolbar"]{ right:8px; }
img{ image-rendering:auto; }

/* cabecalho */
.gb-header{ display:flex; align-items:center; gap:18px; flex-wrap:wrap;
  background:var(--ink2); border:4px solid var(--line); box-shadow:var(--shadow);
  padding:14px 20px; margin:0 0 18px; }
.gb-logo{ height:48px; image-rendering:pixelated; }
.gb-brand{ font-family:var(--pix); color:var(--yellow); font-size:17px; line-height:1.55;
  text-shadow:3px 3px 0 var(--wine); letter-spacing:1px; padding-left:16px;
  border-left:3px solid var(--line); margin:0; }
.gb-brand small{ display:block; font-family:var(--sans); font-size:10px;
  color:var(--blue); margin-top:8px; letter-spacing:0; }

/* titulos de secao */
.gb-h2{ font-family:var(--pix); font-size:14px; color:var(--paper);
  margin:20px 0 14px; text-shadow:2px 2px 0 var(--line); }
.gb-upd{ font-size:13px; color:#aab0cc; margin:8px 0 14px; }

/* metricas */
div[data-testid="stMetric"]{ background:var(--paper); border:4px solid var(--line);
  box-shadow:var(--shadowsm); padding:10px 14px; }
div[data-testid="stMetric"] label, div[data-testid="stMetricLabel"]{
  color:var(--primaryd) !important; font-weight:700; }
div[data-testid="stMetricValue"]{ font-family:var(--pix); font-size:20px; color:var(--primary); }

/* botoes */
.stButton>button{ font-family:var(--pix); font-size:11px; color:#fff; background:var(--primary);
  border:3px solid var(--line); border-radius:0; box-shadow:var(--shadowsm); padding:11px 12px; }
.stButton>button:hover{ background:var(--primaryd); color:#fff; border-color:var(--line); }
.stButton>button:active{ transform:translate(2px,2px); box-shadow:1px 1px 0 0 var(--line); }
.stButton>button[kind="primary"]{ background:var(--yellow); color:var(--ink); }

/* sidebar */
section[data-testid="stSidebar"]{ border-right:4px solid var(--line); }
.gb-side-title{ font-family:var(--pix); font-size:14px; color:var(--yellow);
  text-shadow:2px 2px 0 var(--wine); margin:2px 0 8px; }
.gb-side-sub{ font-family:var(--pix); font-size:10px; color:var(--blue); margin:8px 0 4px; }

/* grade de cards */
.gb-grid{ display:grid; grid-template-columns:repeat(auto-fill, minmax(360px,1fr)); gap:18px; }
.gb-card{ background:var(--paper); border:4px solid var(--line); box-shadow:var(--shadow);
  display:flex; flex-direction:column; }
.gb-top{ height:10px; border-bottom:2px solid var(--line); }
.gb-cbody{ padding:14px 16px 16px; }
.gb-chip{ display:inline-block; font-family:var(--pix); font-size:9px; color:#fff;
  padding:5px 8px; border:2px solid var(--line); margin:0 6px 9px 0; }
.gb-title{ font-size:16px; font-weight:800; color:var(--primaryd); line-height:1.3; margin:6px 0 8px; }
.gb-title a{ color:var(--primaryd); text-decoration:none; }
.gb-title a:hover{ color:var(--primary); text-decoration:underline; }
.gb-resumo{ font-size:14px; color:#2c3147; line-height:1.5; margin:6px 0; }
.gb-meta{ font-size:13px; color:var(--muted); margin-top:10px;
  border-top:2px dotted var(--paperline); padding-top:8px; line-height:1.55; }
.gb-meta b{ color:var(--primaryd); }
.gb-links{ margin-top:11px; }
.gb-links a{ font-family:var(--pix); font-size:9px; color:#fff; background:var(--blue);
  border:2px solid var(--line); padding:6px 8px; margin-right:8px; text-decoration:none;
  display:inline-block; }
.gb-links a:hover{ filter:brightness(1.12); }
.gb-stack{ display:flex; flex-direction:column; gap:14px; }
.gb-scroll{ max-height:700px; overflow-y:auto; padding-right:8px; }
.gb-scroll::-webkit-scrollbar{ width:10px; }
.gb-scroll::-webkit-scrollbar-thumb{ background:var(--primary); border:2px solid var(--line); }
.gb-scroll::-webkit-scrollbar-track{ background:var(--ink2); }
.gb-footer{ margin:26px 0 8px; padding:12px 16px; background:var(--ink2);
  border:3px solid var(--line); box-shadow:var(--shadowsm); color:#aab0cc;
  font-size:12px; display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
.gb-ver{ font-family:var(--pix); font-size:9px; color:#fff; background:var(--blue);
  border:2px solid var(--line); padding:5px 8px; }
.gb-foot-name{ font-family:var(--pix); font-size:9px; color:var(--yellow); }
.gb-row1{ display:flex; align-items:center; gap:6px; flex-wrap:wrap; margin-bottom:9px; }
.gb-row1 .gb-chip{ margin:0; }
.gb-actions{ margin-left:auto; display:inline-flex; gap:6px; align-items:center; }
.gb-btn{ font-family:var(--pix); font-size:9px; color:#fff; background:var(--blue);
  border:2px solid var(--line); padding:6px 8px; text-decoration:none; display:inline-block; }
.gb-btn:hover{ filter:brightness(1.12); }
.gb-iconbtn{ display:inline-flex; align-items:center; justify-content:center;
  width:28px; height:26px; background:var(--blue); border:2px solid var(--line); }
.gb-iconbtn:hover{ filter:brightness(1.12); }
.gb-linhas{ font-size:11px; color:var(--muted); margin-top:9px; line-height:1.55;
  border-top:2px dotted var(--paperline); padding-top:7px; cursor:help; }
.gb-linhas b{ color:var(--primaryd); }
.gb-side-upd{ font-size:11px; color:#aab0cc; margin:8px 0 2px; }
.gb-side-link{ display:inline-block; font-family:var(--pix); font-size:9px; color:#fff !important;
  background:var(--primary); border:2px solid var(--line); padding:7px 9px; margin-top:8px;
  text-decoration:none !important; }
.gb-side-link:hover{ background:var(--primaryd); }
.gb-btn, .gb-iconbtn{ color:#fff !important; text-decoration:none !important; }
.gb-btn:hover, .gb-iconbtn:hover{ text-decoration:none !important; filter:brightness(1.12); }
"""

st.markdown("<style>" + CSS + "</style>", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def _carregar_config():
    return cfgmod.load_config()


CFG = _carregar_config()
APP = CFG["app"]


def _agora():
    return dt.datetime.now()


TZ_BR = dt.timezone(dt.timedelta(hours=-3))


def _fmt_brt(t):
    """Formata um datetime no horario de Brasilia (UTC-3), independente do
    fuso do servidor (Streamlit Cloud roda em UTC)."""
    if not isinstance(t, dt.datetime):
        return "-"
    if t.tzinfo is None:
        t = t.astimezone()   # interpreta como horario local do servidor
    return t.astimezone(TZ_BR).strftime("%d/%m/%Y %H:%M")


def _logo_uri():
    try:
        with open(LOGO, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except Exception:
        return ""


def rodar_coleta(usar_nominatim=True):
    barra = st.progress(0.0)
    txt = st.empty()

    def cb(i, total, label):
        barra.progress(min(i / max(total, 1), 1.0))
        txt.write(f"Buscando {i}/{total}: {label}")

    itens, meta = pipeline.executar(
        cfg=CFG, usar_nominatim=usar_nominatim, sleep_s=0.7, status_cb=cb)
    barra.empty()
    txt.empty()
    st.session_state["itens"] = itens
    st.session_state["meta"] = meta
    st.session_state["last_run"] = _agora()
    return itens, meta


# ---------- estado inicial ----------
if "itens" not in st.session_state:
    cache = pipeline.carregar_resultados()
    if cache:
        st.session_state["itens"] = cache["itens"]
        st.session_state["meta"] = cache["meta"]
        la = cache["meta"].get("atualizado_em")
        st.session_state["last_run"] = pipeline._parse_dt(la)
    else:
        st.session_state["itens"] = []
        st.session_state["meta"] = {}
        st.session_state["last_run"] = None

# ---------- cabecalho ----------
st.markdown(
    f'<div class="gb-header">'
    f'<img class="gb-logo" src="{_logo_uri()}" alt="Guanabara">'
    f'<div class="gb-brand">MONITORAMENTO RODOVIAS'
    f'<small>Linhas Guanabara - interdicoes, transito e ocorrencias</small>'
    f'</div></div>', unsafe_allow_html=True)

# ---------- sidebar ----------
st.sidebar.markdown('<div class="gb-side-title">CONTROLES</div>',
                    unsafe_allow_html=True)
if st.sidebar.button("Atualizar Noticias", type="primary",
                     use_container_width=True):
    with st.spinner("Coletando noticias..."):
        rodar_coleta()
    st.rerun()

_ult = st.session_state.get("last_run")
_ult_txt = _fmt_brt(_ult) if isinstance(_ult, dt.datetime) else "nunca"
st.sidebar.markdown(
    f'<div class="gb-side-upd">Ultimo rastreio: {_ult_txt}</div>',
    unsafe_allow_html=True)

# ---- GPS: fonte do arquivo (local na sua maquina OU link do OneDrive) ----
_fcfg = CFG.get("frota", {})
_gps_local = _fcfg.get("arquivo", "")
_gps_url = (_fcfg.get("url", "") or "").strip()
_gps_fetched = os.path.join(BASE, "data", "ultima_gps.csv")
_na_maquina = bool(_gps_local) and os.path.isdir(os.path.dirname(_gps_local) or "")


def _baixar_gps():
    """Baixa o ultima.CSV de um link publico do OneDrive (uso na nuvem)."""
    if not _gps_url:
        return False
    try:
        import requests as _rq
        u = _gps_url
        r = _rq.get(u, timeout=60, allow_redirects=True)
        c = r.content or b""
        if c[:64].lstrip().lower().startswith((b"<!doctype", b"<html")):
            sep = "&" if "?" in u else "?"
            r = _rq.get(u + sep + "download=1", timeout=60, allow_redirects=True)
            c = r.content or b""
        if r.status_code == 200 and c and not c[:64].lstrip().lower().startswith(b"<"):
            os.makedirs(os.path.dirname(_gps_fetched), exist_ok=True)
            with open(_gps_fetched, "wb") as _f:
                _f.write(c)
            return True
    except Exception:
        pass
    return False


if (not _na_maquina) and _gps_url and "gps_fetch_ok" not in st.session_state:
    st.session_state["gps_fetch_ok"] = _baixar_gps()

if _na_maquina:
    _gps_path = _gps_local
elif os.path.exists(_gps_fetched):
    _gps_path = _gps_fetched
else:
    _gps_path = ""
_gps_ok = bool(_gps_path) and os.path.exists(_gps_path)

if st.sidebar.button("Atualizar GPS", use_container_width=True):
    if _na_maquina:
        with st.spinner("Gerando relatorio GPS no SIGLA (nao use o mouse)..."):
            try:
                _r = subprocess.run(
                    [sys.executable, os.path.join(BASE, "sigla_gps.py")],
                    capture_output=True, text=True, timeout=900)
                _gok = (_r.returncode == 0)
            except Exception:
                _gok = False
    elif _gps_url:
        with st.spinner("Buscando ultimas posicoes..."):
            _gok = _baixar_gps()
    else:
        _gok = False
        st.sidebar.info("Configure frota.url (link do OneDrive) ou rode o app "
                        "na maquina do SIGLA.")
    if _gok:
        st.sidebar.success("GPS atualizado.")
        st.rerun()
    elif _na_maquina or _gps_url:
        st.sidebar.error("Nao foi possivel atualizar o GPS.")
if _gps_ok:
    _gtxt = _fmt_brt(dt.datetime.fromtimestamp(os.path.getmtime(_gps_path)))
else:
    _gtxt = "-"
st.sidebar.markdown(
    f'<div class="gb-side-upd">Ultima atualizacao GPS: {_gtxt}</div>',
    unsafe_allow_html=True)

st.sidebar.divider()
auto = st.sidebar.checkbox("Atualizacao automatica", value=True)
intervalo = st.sidebar.number_input(
    "Intervalo (min)", min_value=5, max_value=240,
    value=int(APP.get("intervalo_auto_min", 5)), step=5)

if auto and st_autorefresh is not None:
    st_autorefresh(interval=int(intervalo) * 60 * 1000, key="auto_tick")
elif auto and st_autorefresh is None:
    st.sidebar.warning("Instale streamlit-autorefresh para auto-refresh.")

if auto and st.session_state.get("last_run"):
    if _agora() - st.session_state["last_run"] >= dt.timedelta(
            minutes=int(intervalo)):
        with st.spinner("Atualizacao automatica..."):
            rodar_coleta()

st.sidebar.divider()
st.sidebar.markdown('<div class="gb-side-sub">FILTROS</div>',
                    unsafe_allow_html=True)
itens_all = st.session_state.get("itens", [])
rodovias_disp = sorted({i.get("rodovia", "")
                        for i in itens_all if i.get("rodovia")})
cat_default = [c for c in ["Interdicao", "Congestionamento"] if c in CAT_NOMES]

f_rod = st.sidebar.multiselect("Rodovia/Corredor", rodovias_disp)
f_cat = st.sidebar.multiselect("Categoria", CAT_NOMES, default=cat_default)
f_sev = st.sidebar.multiselect("Severidade", ["Alta", "Media", "Baixa"],
                               default=["Alta", "Media"])
f_dias = st.sidebar.slider("Periodo (dias)", 1, 30,
                           int(APP.get("periodo_default", 1)))

st.sidebar.divider()
st.sidebar.caption(
    f"Rodovias monitoradas: {len(CFG.get('rodovias', []))}  |  "
    f"Hubs: {len(CFG.get('hubs', []))}")

# ---- controles GPS (carros) ----
st.sidebar.divider()
st.sidebar.markdown('<div class="gb-side-sub">CARROS (GPS)</div>',
                    unsafe_allow_html=True)
if _gps_ok:
    _mostrar_carros = st.sidebar.checkbox(
        "Mostrar carros", value=bool(_fcfg.get("mostrar", True)))
    _so_prox = st.sidebar.checkbox("Apenas proximos a ocorrencias", value=True)
    _raio = st.sidebar.number_input(
        "Raio proximidade (km)", min_value=1, max_value=200,
        value=int(_fcfg.get("raio_km", 15)), step=1)
else:
    _mostrar_carros = False
    _so_prox = False
    _raio = int(_fcfg.get("raio_km", 15))
    st.sidebar.caption("GPS indisponivel (arquivo nao encontrado).")

st.sidebar.markdown(
    '<a class="gb-side-link" href="Carros_GPS" target="_blank">'
    'Abrir tabela de carros (nova aba)</a>', unsafe_allow_html=True)

# ---------- filtragem ----------
limite = _agora() - dt.timedelta(days=int(f_dias))


def no_periodo(it):
    p = it.get("publicado")
    return not (isinstance(p, dt.datetime) and p < limite)


itens_periodo = [i for i in itens_all if no_periodo(i)]


def passa(it):
    if f_rod and it.get("rodovia") not in f_rod:
        return False
    if f_cat and it.get("categoria") not in f_cat:
        return False
    if f_sev and it.get("severidade") not in f_sev:
        return False
    return True


itens = [i for i in itens_periodo if passa(i)]

# ---------- frota (GPS) ----------
_carros = []
_ref_gps = None
_nprox = 0
if _gps_ok and _mostrar_carros:
    _carros, _ref_gps = frota.carregar_frota(
        _gps_path, janela_min=int(_fcfg.get("janela_min", 60)))
    _nprox = frota.marcar_proximos(_carros, itens, raio_km=float(_raio))

# ---------- layout: cards (esq.) | contadores + mapa (dir., maior) ----------
if not itens_all:
    st.info("Sem dados ainda. Clique em Atualizar agora na barra lateral "
            "para fazer a primeira varredura.")
    st.stop()


def _card_html(it):
    cor = it.get("cor", "#6b6f86")
    cat = html.escape(it.get("categoria", ""))
    sev = html.escape(it.get("severidade", ""))
    sevcor = SEV_COR.get(it.get("severidade"), "#6b6f86")
    titulo = html.escape(it.get("titulo", "(sem titulo)"))
    local = html.escape(it.get("local", "-"))
    rod = html.escape(it.get("rodovia", "-"))
    fonte = html.escape(it.get("fonte", "-"))
    d = it.get("publicado")
    dtxt = d.strftime("%d/%m %H:%M") if isinstance(d, dt.datetime) else ""
    link = it.get("link", "")
    titulo_html = (f'<a href="{html.escape(link)}" target="_blank">{titulo}</a>'
                   if link else titulo)
    acoes = ""
    if link:
        acoes += (f'<a class="gb-btn" href="{html.escape(link)}" '
                  f'target="_blank">Noticia</a>')
    if it.get("lat") is not None and it.get("lon") is not None:
        acoes += (f'<a class="gb-iconbtn" title="Ver no mapa" '
                  f'aria-label="Ver no mapa" target="_blank" '
                  f'href="https://www.google.com/maps?q={it["lat"]},{it["lon"]}">'
                  f'{MAP_ICON}</a>')
    linhas = it.get("linhas") or []
    ltot = it.get("linhas_total", len(linhas))
    linhas_html = ""
    if ltot:
        tip = "\n".join(linhas)
        if ltot > len(linhas):
            tip += f"\n(+{ltot - len(linhas)} outras)"
        linhas_html = (f'<div class="gb-linhas" title="{html.escape(tip)}">'
                       f'<b>Possiveis Linhas Afetadas</b> ({ltot})</div>')
    return (
        f'<div class="gb-card"><div class="gb-top" style="background:{cor}"></div>'
        f'<div class="gb-cbody"><div class="gb-row1">'
        f'<span class="gb-chip" style="background:{cor};color:{_txt_chip(cor)}">{cat}</span>'
        f'<span class="gb-chip" style="background:{sevcor};color:{_txt_chip(sevcor)}">{sev}</span>'
        f'<span class="gb-actions">{acoes}</span></div>'
        f'<div class="gb-title">{titulo_html}</div>'
        f'<div class="gb-meta"><b>Local:</b> {local} &nbsp;|&nbsp; '
        f'<b>Rodovia:</b> {rod}<br><b>Fonte:</b> {fonte} - {dtxt}</div>'
        f'{linhas_html}</div></div>')


col_cards, col_main = st.columns([1, 2], gap="large")

with col_cards:
    st.markdown(f'<div class="gb-h2">OCORRENCIAS ({len(itens)})</div>',
                unsafe_allow_html=True)
    if not itens:
        st.warning("Nenhuma ocorrencia para os filtros selecionados.")
    else:
        MAX = 120
        cards = "".join(_card_html(it) for it in itens[:MAX])
        st.markdown('<div class="gb-scroll"><div class="gb-stack">' + cards
                    + '</div></div>', unsafe_allow_html=True)
        if len(itens) > MAX:
            st.markdown(
                f'<div class="gb-upd">Exibindo {MAX} de {len(itens)} '
                f'ocorrencias. Use os filtros para refinar.</div>',
                unsafe_allow_html=True)

with col_main:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Ocorrencias (periodo)", len(itens_periodo))
    m2.metric("Interdicoes",
              sum(1 for i in itens_periodo if i.get("categoria") == "Interdicao"))
    m3.metric("Acidentes",
              sum(1 for i in itens_periodo if i.get("categoria") == "Acidente"))
    m4.metric("Severidade alta",
              sum(1 for i in itens_periodo if i.get("severidade") == "Alta"))
    st.markdown(
        f'<div class="gb-upd">Exibindo {len(itens)} de '
        f'{len(itens_periodo)} no periodo</div>', unsafe_allow_html=True)
    if _gps_ok and _mostrar_carros:
        _rtxt = _ref_gps.strftime("%d/%m %H:%M") if _ref_gps else "-"
        st.markdown(
            f'<div class="gb-upd">GPS: {len(_carros)} carros (ref {_rtxt}) '
            f'&nbsp;|&nbsp; {_nprox} proximos (ate {int(_raio)} km)</div>',
            unsafe_allow_html=True)
    st.markdown('<div class="gb-h2">MAPA DAS OCORRENCIAS</div>',
                unsafe_allow_html=True)
    if st_folium is not None:
        st_folium(
            mapa.construir_mapa(itens, usar_cluster=True,
                                carros=(_carros or None), so_proximos=_so_prox),
            use_container_width=True, height=600, returned_objects=[])
    else:
        st.warning("Pacote streamlit-folium nao instalado. Mapa simplificado. "
                   "Rode: pip install streamlit-folium")
        _pts = [(i["lat"], i["lon"]) for i in itens
                if i.get("lat") is not None and i.get("lon") is not None]
        if _pts:
            st.map({"lat": [p[0] for p in _pts], "lon": [p[1] for p in _pts]})

# ---------- rodape / controle de versao ----------
st.markdown(
    f'<div class="gb-footer"><span class="gb-ver">v{html.escape(VERSAO)}</span>'
    f'<span class="gb-foot-name">MONITORAMENTO RODOVIAS</span>'
    f'<span>Linhas Guanabara</span></div>', unsafe_allow_html=True)
