"""
Monitoramento de Rodovias - Linhas Guanabara
Painel Streamlit (visual padrao pixel Guanabara).
Execute com:  streamlit run app.py
"""
import os
import base64
import html
import datetime as dt

import streamlit as st
try:
    from streamlit_folium import st_folium
except ImportError:
    st_folium = None

from monitor import config as cfgmod
from monitor import pipeline, mapa
from monitor.processa import CATEGORIAS

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
"""

st.markdown("<style>" + CSS + "</style>", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def _carregar_config():
    return cfgmod.load_config()


CFG = _carregar_config()
APP = CFG["app"]


def _agora():
    return dt.datetime.now()


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
if st.sidebar.button("Atualizar agora", type="primary",
                     use_container_width=True):
    with st.spinner("Coletando noticias..."):
        rodar_coleta()
    st.rerun()

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

# ---------- metricas ----------
lr = st.session_state.get("last_run")
lr_txt = lr.strftime("%d/%m/%Y %H:%M") if isinstance(lr, dt.datetime) else "nunca"

c1, c2, c3, c4 = st.columns(4)
c1.metric("Ocorrencias (periodo)", len(itens_periodo))
c2.metric("Interdicoes",
          sum(1 for i in itens_periodo if i.get("categoria") == "Interdicao"))
c3.metric("Acidentes",
          sum(1 for i in itens_periodo if i.get("categoria") == "Acidente"))
c4.metric("Severidade alta",
          sum(1 for i in itens_periodo if i.get("severidade") == "Alta"))
st.markdown(
    f'<div class="gb-upd">Ultima atualizacao: {html.escape(lr_txt)} '
    f'&nbsp;|&nbsp; Exibindo {len(itens)} de {len(itens_periodo)} no periodo'
    f'</div>', unsafe_allow_html=True)

if not itens_all:
    st.info("Sem dados ainda. Clique em Atualizar agora na barra lateral "
            "para fazer a primeira varredura.")
    st.stop()

# ---------- mapa ----------
st.markdown('<div class="gb-h2">MAPA DAS OCORRENCIAS</div>',
            unsafe_allow_html=True)
if st_folium is not None:
    st_folium(mapa.construir_mapa(itens, usar_cluster=True),
              use_container_width=True, height=520, returned_objects=[])
else:
    st.warning("Pacote streamlit-folium nao instalado. Mapa simplificado. "
               "Rode: pip install streamlit-folium")
    _pts = [(i["lat"], i["lon"]) for i in itens
            if i.get("lat") is not None and i.get("lon") is not None]
    if _pts:
        st.map({"lat": [p[0] for p in _pts], "lon": [p[1] for p in _pts]})

# ---------- cards ----------
st.markdown(f'<div class="gb-h2">OCORRENCIAS ({len(itens)})</div>',
            unsafe_allow_html=True)

if not itens:
    st.warning("Nenhuma ocorrencia para os filtros selecionados.")
else:
    MAX = 80
    blocos = ['<div class="gb-grid">']
    for it in itens[:MAX]:
        cor = it.get("cor", "#6b6f86")
        cat = html.escape(it.get("categoria", ""))
        sev = html.escape(it.get("severidade", ""))
        sevcor = SEV_COR.get(it.get("severidade"), "#6b6f86")
        titulo = html.escape(it.get("titulo", "(sem titulo)"))
        resumo = html.escape(it.get("resumo", ""))
        local = html.escape(it.get("local", "-"))
        rod = html.escape(it.get("rodovia", "-"))
        fonte = html.escape(it.get("fonte", "-"))
        d = it.get("publicado")
        dtxt = d.strftime("%d/%m %H:%M") if isinstance(d, dt.datetime) else ""
        link = it.get("link", "")
        titulo_html = (f'<a href="{html.escape(link)}" target="_blank">{titulo}</a>'
                       if link else titulo)
        links = ""
        if link:
            links += f'<a href="{html.escape(link)}" target="_blank">Abrir noticia</a>'
        if it.get("lat") is not None and it.get("lon") is not None:
            links += (f'<a href="https://www.google.com/maps?q='
                      f'{it["lat"]},{it["lon"]}" target="_blank">Ver no mapa</a>')
        blocos.append(
            f'<div class="gb-card"><div class="gb-top" style="background:{cor}">'
            f'</div><div class="gb-cbody">'
            f'<span class="gb-chip" style="background:{cor};color:{_txt_chip(cor)}">{cat}</span>'
            f'<span class="gb-chip" style="background:{sevcor};color:{_txt_chip(sevcor)}">{sev}</span>'
            f'<div class="gb-title">{titulo_html}</div>'
            f'<div class="gb-resumo">{resumo}</div>'
            f'<div class="gb-meta"><b>Local:</b> {local} &nbsp;|&nbsp; '
            f'<b>Rodovia:</b> {rod}<br><b>Fonte:</b> {fonte} - {dtxt}</div>'
            f'<div class="gb-links">{links}</div>'
            f'</div></div>')
    blocos.append('</div>')
    st.markdown("\n".join(blocos), unsafe_allow_html=True)
    if len(itens) > MAX:
        st.markdown(
            f'<div class="gb-upd">Exibindo {MAX} de {len(itens)} ocorrencias. '
            f'Use os filtros para refinar.</div>', unsafe_allow_html=True)
