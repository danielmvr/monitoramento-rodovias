"""
Pagina "Acompanhamento de Atrasos" do painel de Monitoramento de Rodovias.

Consome o motor core.py (logica pura, sem UI) a partir do relatorio atrasos.TXT.
A fonte segue o mesmo esquema do GPS: arquivo local (pasta OneDrive) na maquina do
SIGLA, ou download de um link publico do OneDrive quando rodando na nuvem.

Exibe metricas, duas abas (Atrasos / Anomalias) com filtro, horarios e atraso/silencio
em HH:MM, onda de calor no atraso e botao de download.

Cruza cada carro atrasado com a ULTIMA POSICAO do GPS (mesmo identificador de carro):
uma coluna "Mapa" com icone que abre a posicao no Google Maps, e um mapa in-screen
com os carros atrasados localizados.
"""
import os
import datetime as dt

import pandas as pd
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

import core
from monitor import frota


def _baixar(url, destino):
    """Baixa um arquivo de um link publico do OneDrive (uso na nuvem)."""
    if not url:
        return False
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


def _fmt_dt(t):
    """Horario do relatorio (ja em horario local), como dd/mm HH:MM."""
    if t is None or pd.isna(t):
        return "-"
    return pd.Timestamp(t).strftime("%d/%m %H:%M")


def _fmt_hhmm(m):
    """Minutos inteiros -> HH:MM (mantem sinal para adiantado)."""
    if m is None or (isinstance(m, float) and pd.isna(m)):
        return "-"
    try:
        m = int(round(float(m)))
    except (TypeError, ValueError):
        return "-"
    sinal = "-" if m < 0 else ""
    m = abs(m)
    return f"{sinal}{m // 60:02d}:{m % 60:02d}"


def _gps_path(cfg, base_dir, baixar=False):
    """Resolve o caminho do relatorio de ultimas posicoes (GPS). Se baixar=True
    e estiver na nuvem, rebaixa o arquivo do OneDrive antes de resolver."""
    fcfg = (cfg or {}).get("frota", {})
    local = fcfg.get("arquivo", "")
    url = (fcfg.get("url", "") or "").strip()
    fetched = os.path.join(base_dir, "data", "ultima_gps.csv")
    na_maquina = bool(local) and os.path.isdir(os.path.dirname(local) or "")
    if na_maquina:
        return local
    if baixar and url:
        _baixar(url, fetched)
    if os.path.exists(fetched):
        return fetched
    if url and _baixar(url, fetched):
        return fetched
    return ""


def _posicoes_gps(cfg, base_dir):
    """Ultima posicao GPS por carro: dict veiculo(maiusculo) -> registro do frota.
    Janela ampla (dia) para localizar tambem carros que transmitiram ha mais tempo."""
    path = _gps_path(cfg, base_dir, baixar=False)
    if not path or not os.path.exists(path):
        return {}
    try:
        carros, _ref = frota.carregar_frota(path, janela_min=1440)
    except Exception:
        return {}
    pos = {}
    for c in carros:
        v = str(c.get("veiculo", "")).strip().upper()
        if v and c.get("lat") is not None and c.get("lon") is not None:
            pos[v] = c
    return pos


def _map_url(veiculo, pos):
    c = pos.get(str(veiculo).strip().upper())
    if c and c.get("lat") is not None and c.get("lon") is not None:
        return f"https://www.google.com/maps?q={c['lat']},{c['lon']}"
    return ""


def _disp(dfin, anomalia, pos):
    """Monta o DataFrame de exibicao a partir da saida do core."""
    if dfin is None or dfin.empty:
        return pd.DataFrame()
    out = pd.DataFrame()
    out["Carro"] = dfin["prefixo_veiculo"].fillna("").astype(str).str.strip()
    out["Mapa"] = out["Carro"].map(lambda v: _map_url(v, pos))
    out["Linha"] = dfin["linha"].fillna("").astype(str)
    if anomalia:
        out["Categoria"] = dfin["categoria"].fillna("").astype(str)
    out["Servico"] = dfin["servico"].fillna("").astype(str)
    out["Ponto"] = dfin["ponto"].fillna("").astype(str)
    out["Previsto"] = dfin["previsto"].map(_fmt_dt)
    out["Ultima transm."] = dfin["real"].map(_fmt_dt)
    out["Atraso"] = pd.to_numeric(dfin["atraso_min"], errors="coerce")
    out["Silencio"] = pd.to_numeric(dfin["silencio_min"], errors="coerce")
    out["Prox. ponto"] = dfin["proximo_ponto"].fillna("").astype(str)
    if not anomalia:
        out["Fim projetado"] = dfin["fim_projetado"].map(_fmt_dt)
    out["Base"] = dfin["base"].fillna("").astype(str)
    out["Motorista"] = dfin["motorista"].fillna("").astype(str)
    return out


def _heat_rgb(t):
    """Interpola uma 'onda de calor': amarelo claro -> laranja -> vermelho."""
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    stops = [(0.0, (255, 247, 188)), (0.5, (253, 141, 60)), (1.0, (189, 0, 38))]
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t <= t1:
            f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return tuple(int(round(c0[k] + (c1[k] - c0[k]) * f)) for k in range(3))
    return stops[-1][1]


def _grad_atraso(col):
    """Fundo de cada celula em onda de calor conforme o atraso (valor numerico)."""
    vals = pd.to_numeric(col, errors="coerce")
    vmin, vmax = vals.min(), vals.max()
    estilos = []
    for v in vals:
        if pd.isna(v):
            estilos.append("")
            continue
        if pd.isna(vmin) or pd.isna(vmax) or vmax == vmin:
            t = 0.5
        else:
            t = (v - vmin) / (vmax - vmin)
        r, g, b = _heat_rgb(t)
        estilos.append(f"background-color: rgb({r},{g},{b}); color: #1a1a1a;")
    return estilos


def _tabela(dfin, busca, anomalia, pos):
    disp = _disp(dfin, anomalia, pos)
    if busca and not disp.empty:
        mask = (disp["Carro"].str.upper().str.contains(busca, na=False, regex=False)
                | disp["Linha"].str.upper().str.contains(busca, na=False, regex=False)
                | disp["Base"].str.upper().str.contains(busca, na=False, regex=False))
        disp = disp[mask]
    if disp.empty:
        st.info("Nada para exibir com os filtros atuais.")
        return
    disp = disp.reset_index(drop=True)
    colcfg = {"Mapa": st.column_config.LinkColumn(
        "Mapa", display_text="🗺️", width="small",
        help="Abre a posicao atual do carro no Google Maps (nova aba)")}
    try:
        sty = (disp.style
               .format({"Atraso": _fmt_hhmm, "Silencio": _fmt_hhmm}, na_rep="-")
               .apply(_grad_atraso, subset=["Atraso"]))
        st.dataframe(sty, use_container_width=True, hide_index=True, height=520,
                     column_config=colcfg)
    except Exception:  # fallback sem onda de calor (ex.: jinja2 ausente)
        plano = disp.copy()
        plano["Atraso"] = plano["Atraso"].map(_fmt_hhmm)
        plano["Silencio"] = plano["Silencio"].map(_fmt_hhmm)
        st.dataframe(plano, use_container_width=True, hide_index=True, height=520,
                     column_config=colcfg)
    csv = disp.copy()
    csv["Atraso"] = csv["Atraso"].map(_fmt_hhmm)
    csv["Silencio"] = csv["Silencio"].map(_fmt_hhmm)
    st.download_button(
        "Baixar CSV", csv.to_csv(index=False).encode("utf-8-sig"),
        file_name=("anomalias.csv" if anomalia else "atrasos.csv"),
        mime="text/csv", key=("dl_anom" if anomalia else "dl_atr"))


def _mapa_atrasos(A, pos):
    """Mapa in-screen com os carros atrasados que tem ultima posicao GPS."""
    linhas = []
    for _, r in A.iterrows():
        c = pos.get(str(r.get("prefixo_veiculo", "")).strip().upper())
        if c and c.get("lat") is not None and c.get("lon") is not None:
            linhas.append((str(r.get("prefixo_veiculo", "")).strip(),
                           float(c["lat"]), float(c["lon"]), c.get("local", ""),
                           str(r.get("linha", "")), r.get("atraso_min"), c.get("dh")))
    st.markdown('<div class="gb-h2">LOCALIZACAO DOS CARROS ATRASADOS (GPS)</div>',
                unsafe_allow_html=True)
    if not linhas:
        st.caption("Sem posicao GPS para os carros atrasados no momento "
                   "(o relatorio de ultimas posicoes pode nao cobri-los).")
        return
    try:
        import folium
        from streamlit_folium import st_folium
    except Exception:
        st.map(pd.DataFrame([(x[1], x[2]) for x in linhas], columns=["lat", "lon"]))
        return
    lats = [x[1] for x in linhas]
    lons = [x[2] for x in linhas]
    m = folium.Map(location=[sum(lats) / len(lats), sum(lons) / len(lons)],
                   zoom_start=6, tiles="CartoDB dark_matter")
    for v, lat, lon, local, linha, atr, dh in linhas:
        pop = (f"<b>{v}</b><br>{linha}<br>Atraso: {_fmt_hhmm(atr)}"
               f"<br>Local: {local}<br>GPS: {_fmt_dt(dh)}")
        folium.Marker([lat, lon], tooltip=f"{v} ({_fmt_hhmm(atr)})",
                      popup=folium.Popup(pop, max_width=260),
                      icon=folium.Icon(color="red")).add_to(m)
    if len(linhas) > 1:
        m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])
    st_folium(m, use_container_width=True, height=420, returned_objects=[],
              key=f"mapa_atrasos_{len(linhas)}_{lats[0]:.3f}_{lons[0]:.3f}")


def render(cfg, base_dir, agora_dt):
    """Renderiza a pagina de atrasos. Chamada quando a visao do app == 'atrasos'."""
    cfg_a = (cfg or {}).get("atrasos", {})
    local = cfg_a.get("arquivo", "")
    url = (cfg_a.get("url", "") or "").strip()
    fetched = os.path.join(base_dir, "data", "atrasos.txt")
    na_maquina = bool(local) and os.path.isdir(os.path.dirname(local) or "")

    # primeira busca na nuvem (uma vez por sessao): atrasos + GPS juntos
    if (not na_maquina) and url and "atr_fetch_ok" not in st.session_state:
        st.session_state["atr_fetch_ok"] = _baixar(url, fetched)
        _gps_path(cfg, base_dir, baixar=True)
        st.session_state["last_atr_auto"] = agora_dt

    if na_maquina:
        path = local
    elif os.path.exists(fetched):
        path = fetched
    else:
        path = ""
    ok = bool(path) and os.path.exists(path)

    # ---------- topo: voltar ----------
    if st.button("Voltar ao mapa e noticias", key="voltar_atrasos_top",
                 type="primary"):
        st.session_state["view"] = "mapa"
        st.rerun()
    st.markdown('<div class="gb-h2">ACOMPANHAMENTO DE ATRASOS</div>',
                unsafe_allow_html=True)

    # ---------- sidebar: parametros + atualizacao ----------
    st.sidebar.divider()
    st.sidebar.markdown('<div class="gb-side-sub">ATRASOS</div>',
                        unsafe_allow_html=True)
    limite = st.sidebar.number_input(
        "Atraso minimo (min)", min_value=5, max_value=240,
        value=int(cfg_a.get("limite_min", 60)), step=5, key="atr_limite")
    frescor = st.sidebar.number_input(
        "Silencio max (min)", min_value=30, max_value=600,
        value=int(cfg_a.get("frescor_min", 180)), step=10, key="atr_frescor")

    if st.sidebar.button("Atualizar atrasos", use_container_width=True,
                         key="atr_btn"):
        if (not na_maquina) and url:
            with st.spinner("Buscando relatorios (atrasos + GPS)..."):
                _baixar(url, fetched)
                _gps_path(cfg, base_dir, baixar=True)
            st.session_state["last_atr_auto"] = agora_dt
            st.rerun()
        elif na_maquina:
            st.sidebar.info("Na maquina do SIGLA a extracao roda junto do GPS.")
        else:
            st.sidebar.info("Configure atrasos.url (link do OneDrive).")

    _atxt = (pd.Timestamp(os.path.getmtime(path), unit="s").strftime("%d/%m %H:%M")
             if ok else "-")
    st.sidebar.markdown(
        f'<div class="gb-side-upd">Arquivo atualizado: {_atxt}</div>',
        unsafe_allow_html=True)

    auto_a = st.sidebar.checkbox("Atualizacao automatica",
                                 value=bool(cfg_a.get("auto", True)),
                                 key="atr_auto")
    intervalo_a = st.sidebar.number_input(
        "Intervalo (min)", min_value=5, max_value=240,
        value=int(cfg_a.get("auto_min", 30)), step=5, key="atr_intervalo")
    if auto_a and st_autorefresh is not None:
        st_autorefresh(interval=int(intervalo_a) * 60 * 1000, key="atr_tick")
    if auto_a and (not na_maquina) and url:
        la = st.session_state.get("last_atr_auto")
        if (la is None) or (agora_dt - la >= dt.timedelta(minutes=int(intervalo_a))):
            with st.spinner("Atualizando..."):
                _baixar(url, fetched)
                _gps_path(cfg, base_dir, baixar=True)
            st.session_state["last_atr_auto"] = agora_dt

    if not ok:
        st.warning("Sem relatorio de atrasos disponivel (verifique o arquivo/link "
                   "do OneDrive ou gere o relatorio no SIGLA).")
        return

    try:
        df = core.carregar(path)
        A, N = core.classificar(df, limite_min=int(limite),
                                frescor_min=int(frescor))
        ref = core.agora_padrao(df)
    except Exception as e:  # noqa: BLE001
        st.error(f"Falha ao processar o relatorio de atrasos: {e}")
        return

    pos = _posicoes_gps(cfg, base_dir)

    n_parou = int((N["categoria"] == "Parou de transmitir").sum()) if not N.empty else 0
    n_sem = int((N["categoria"] == "Sem transmissão").sum()) if not N.empty else 0
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Atrasos", len(A))
    m2.metric("Parou de transmitir", n_parou)
    m3.metric("Sem transmissao", n_sem)
    m4.metric("Localizados", sum(1 for _, r in A.iterrows()
              if str(r.get("prefixo_veiculo", "")).strip().upper() in pos))
    m5.metric("Snapshot", _fmt_dt(ref))

    busca = st.text_input("Buscar carro, linha ou base",
                          placeholder="ex.: 9708 / RIO X / UTIL",
                          key="atr_busca").strip().upper()

    aba_a, aba_n = st.tabs([f"Atrasos ({len(A)})", f"Anomalias ({len(N)})"])
    with aba_a:
        _tabela(A, busca, anomalia=False, pos=pos)
        _mapa_atrasos(A, pos)
    with aba_n:
        _tabela(N, busca, anomalia=True, pos=pos)
