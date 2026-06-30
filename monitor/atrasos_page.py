"""
Pagina "Acompanhamento de Atrasos" do painel de Monitoramento de Rodovias.

Consome o motor core.py (logica pura, sem UI) a partir do relatorio atrasos.TXT.
A fonte segue o mesmo esquema do GPS: arquivo local (pasta OneDrive) na maquina do
SIGLA, ou download de um link publico do OneDrive quando rodando na nuvem.

Exibe metricas, duas abas (Atrasos / Anomalias) com filtro, horarios e atraso/silencio
em HH:MM, e botao de download. Refresh manual e automatico por intervalo.
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


def _baixar(url, destino):
    """Baixa o atrasos.TXT de um link publico do OneDrive (uso na nuvem)."""
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


def _disp(dfin, anomalia):
    """Monta o DataFrame de exibicao a partir da saida do core."""
    if dfin is None or dfin.empty:
        return pd.DataFrame()
    out = pd.DataFrame()
    out["Carro"] = dfin["prefixo_veiculo"].fillna("").astype(str).str.strip()
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


def _tabela(dfin, busca, anomalia):
    disp = _disp(dfin, anomalia)
    if busca and not disp.empty:
        mask = (disp["Carro"].str.upper().str.contains(busca, na=False, regex=False)
                | disp["Linha"].str.upper().str.contains(busca, na=False, regex=False)
                | disp["Base"].str.upper().str.contains(busca, na=False, regex=False))
        disp = disp[mask]
    if disp.empty:
        st.info("Nada para exibir com os filtros atuais.")
        return
    disp = disp.reset_index(drop=True)
    try:
        sty = (disp.style
               .format({"Atraso": _fmt_hhmm, "Silencio": _fmt_hhmm}, na_rep="-")
               .apply(_grad_atraso, subset=["Atraso"]))
        st.dataframe(sty, use_container_width=True, hide_index=True, height=520)
    except Exception:  # fallback sem onda de calor (ex.: jinja2 ausente)
        plano = disp.copy()
        plano["Atraso"] = plano["Atraso"].map(_fmt_hhmm)
        plano["Silencio"] = plano["Silencio"].map(_fmt_hhmm)
        st.dataframe(plano, use_container_width=True, hide_index=True, height=520)
    csv = disp.copy()
    csv["Atraso"] = csv["Atraso"].map(_fmt_hhmm)
    csv["Silencio"] = csv["Silencio"].map(_fmt_hhmm)
    st.download_button(
        "Baixar CSV", csv.to_csv(index=False).encode("utf-8-sig"),
        file_name=("anomalias.csv" if anomalia else "atrasos.csv"),
        mime="text/csv", key=("dl_anom" if anomalia else "dl_atr"))


def render(cfg, base_dir, agora_dt):
    """Renderiza a pagina de atrasos. Chamada quando a visao do app == 'atrasos'."""
    cfg_a = (cfg or {}).get("atrasos", {})
    local = cfg_a.get("arquivo", "")
    url = (cfg_a.get("url", "") or "").strip()
    fetched = os.path.join(base_dir, "data", "atrasos.txt")
    na_maquina = bool(local) and os.path.isdir(os.path.dirname(local) or "")

    # primeira busca na nuvem (uma vez por sessao)
    if (not na_maquina) and url and "atr_fetch_ok" not in st.session_state:
        st.session_state["atr_fetch_ok"] = _baixar(url, fetched)
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
            with st.spinner("Buscando relatorio de atrasos..."):
                _baixar(url, fetched)
            st.session_state["last_atr_auto"] = agora_dt
            st.rerun()
        elif na_maquina:
            st.sidebar.info("Na maquina do SIGLA a extracao roda junto do GPS.")
        else:
            st.sidebar.info("Configure atrasos.url (link do OneDrive).")

    if na_maquina and os.path.exists(path):
        _atxt = pd.Timestamp(os.path.getmtime(path), unit="s").strftime("%d/%m %H:%M")
    elif ok:
        _atxt = pd.Timestamp(os.path.getmtime(path), unit="s").strftime("%d/%m %H:%M")
    else:
        _atxt = "-"
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
            with st.spinner("Atualizando atrasos..."):
                _baixar(url, fetched)
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

    n_parou = int((N["categoria"] == "Parou de transmitir").sum()) if not N.empty else 0
    n_sem = int((N["categoria"] == "Sem transmissão").sum()) if not N.empty else 0
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Atrasos", len(A))
    m2.metric("Parou de transmitir", n_parou)
    m3.metric("Sem transmissao", n_sem)
    m4.metric("Snapshot", _fmt_dt(ref))

    busca = st.text_input("Buscar carro, linha ou base",
                          placeholder="ex.: 9708 / RIO X / UTIL",
                          key="atr_busca").strip().upper()

    aba_a, aba_n = st.tabs([f"Atrasos ({len(A)})", f"Anomalias ({len(N)})"])
    with aba_a:
        _tabela(A, busca, anomalia=False)
    with aba_n:
        _tabela(N, busca, anomalia=True)
