"""
Pagina "Carros GPS" - tabela dos carros com posicao capturada.
Abre como sub-pagina do painel (e pode ser aberta em nova aba pelo link da
barra lateral). Colunas: Carro, Empresa, Ultima transmissao, Local mais
proximo (sigla), Distancia do local. Filtros por numero do carro e empresa.
"""
import os
import base64
import datetime as dt

import streamlit as st

from monitor import config as cfgmod
from monitor import frota

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO = os.path.join(BASE, "logoGB.png")

st.set_page_config(page_title="Carros GPS - Guanabara", page_icon=None,
                   layout="wide")

TZ_BR = dt.timezone(dt.timedelta(hours=-3))


def _fmt_brt(t, fmt="%d/%m/%Y %H:%M"):
    if not isinstance(t, dt.datetime):
        return "-"
    if t.tzinfo is None:
        t = t.astimezone()
    return t.astimezone(TZ_BR).strftime(fmt)


def _logo_uri():
    try:
        with open(LOGO, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except Exception:
        return ""


CSS = """
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');
:root{ --ink2:#222743; --yellow:#f7c01a; --blue:#5e86d6; --wine:#9c2742;
  --line:#0d1024; --pix:"Press Start 2P","Courier New",monospace; }
.stApp{ background:
  repeating-linear-gradient(0deg, rgba(255,255,255,.025) 0 2px, transparent 2px 4px),
  radial-gradient(circle at 25% -10%, #2b3160 0%, #161a2e 62%); background-attachment:fixed; }
.block-container{ padding-top:3.2rem; max-width:1400px; }
header[data-testid="stHeader"]{ background:transparent; }
.gb-header{ display:flex; align-items:center; gap:18px; flex-wrap:wrap;
  background:var(--ink2); border:4px solid var(--line);
  box-shadow:5px 5px 0 0 var(--line); padding:12px 18px; margin:0 0 16px; }
.gb-logo{ height:42px; image-rendering:pixelated; }
.gb-brand{ font-family:var(--pix); color:var(--yellow); font-size:15px; line-height:1.5;
  text-shadow:3px 3px 0 var(--wine); padding-left:14px; border-left:3px solid var(--line); margin:0; }
.gb-brand small{ display:block; font-size:9px; color:var(--blue); margin-top:7px; }
.gb-cap{ font-size:13px; color:#aab0cc; margin:0 0 12px; }
"""
st.markdown("<style>" + CSS + "</style>", unsafe_allow_html=True)

st.markdown(
    f'<div class="gb-header"><img class="gb-logo" src="{_logo_uri()}" alt="GB">'
    f'<div class="gb-brand">CARROS - GPS'
    f'<small>Linhas Guanabara - ultimas posicoes</small></div></div>',
    unsafe_allow_html=True)

CFG = cfgmod.load_config()
_fcfg = CFG.get("frota", {})
_local = _fcfg.get("arquivo", "")
_url = (_fcfg.get("url", "") or "").strip()
_fetched = os.path.join(BASE, "data", "ultima_gps.csv")


def _baixar(url, destino):
    try:
        import requests
        r = requests.get(url, timeout=60, allow_redirects=True)
        c = r.content or b""
        if c[:64].lstrip().lower().startswith((b"<!doctype", b"<html")):
            sep = "&" if "?" in url else "?"
            r = requests.get(url + sep + "download=1", timeout=60,
                             allow_redirects=True)
            c = r.content or b""
        if r.status_code == 200 and c and not c[:64].lstrip().lower().startswith(b"<"):
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            with open(destino, "wb") as f:
                f.write(c)
            return True
    except Exception:
        pass
    return False


if _local and os.path.isdir(os.path.dirname(_local) or "") and os.path.exists(_local):
    _path = _local
elif os.path.exists(_fetched):
    _path = _fetched
elif _url:
    _baixar(_url, _fetched)
    _path = _fetched if os.path.exists(_fetched) else ""
else:
    _path = ""

carros, ref = frota.carregar_frota(_path, janela_min=int(_fcfg.get("janela_min", 60)))

if not carros:
    st.warning("Sem posicoes de GPS disponiveis (verifique o arquivo/ link do "
               "OneDrive ou gere o relatorio).")
    st.stop()

# ---------- filtros ----------
c1, c2 = st.columns([2, 1])
busca = c1.text_input("Buscar carro", placeholder="ex.: 11216").strip().upper()
empresas = ["Todas"] + sorted({c.get("empresa", "") for c in carros if c.get("empresa")})
emp = c2.selectbox("Empresa", empresas)

linhas = []
for c in carros:
    if busca and busca not in c.get("veiculo", "").upper():
        continue
    if emp != "Todas" and c.get("empresa") != emp:
        continue
    d = c.get("dist_local")
    linhas.append({
        "Carro": c.get("veiculo", ""),
        "Empresa": c.get("empresa", ""),
        "Ultima transmissao": _fmt_brt(c.get("dh"), "%d/%m %H:%M"),
        "Local mais proximo": c.get("local", ""),
        "Dist. do local (km)": round(d, 1) if isinstance(d, (int, float)) else None,
    })

st.markdown(
    f'<div class="gb-cap">{len(linhas)} de {len(carros)} carros '
    f'(janela {int(_fcfg.get("janela_min", 60))} min, '
    f'ref {_fmt_brt(ref, "%d/%m %H:%M")})</div>', unsafe_allow_html=True)

try:
    import pandas as pd
    st.dataframe(pd.DataFrame(linhas), use_container_width=True,
                 hide_index=True, height=620)
except Exception:
    st.table(linhas)
