"""
Lógica de detecção de atrasos a partir do relatório atrasos.TXT.

Dois princípios centrais:

1) O atraso é sempre ancorado na ÚLTIMA TRANSMISSÃO REAL do carro. Não se infla o
   atraso pelo tempo de silêncio. Quem estava quase no horário e parou de transmitir
   vira anomalia, não "atraso gigante".

2) UM status por carro, sempre da VIAGEM ATUAL. Se o carro já tem uma viagem mais
   à frente (transmitindo numa viagem posterior), a viagem anterior morre: o carro
   já terminou e está em outro serviço. Não existem duplicatas do mesmo carro.

Seleção da viagem atual (por carro), entre as viagens não concluídas:
- Se há transmissão, a viagem da transmissão mais recente. Quando a mesma transmissão
  cai em duas pernas (ida e volta com horários "vazados"), vence a perna que casa
  melhor com o horário (menor atraso absoluto).
- Se nenhuma transmitiu, a viagem de início mais recente que já começou.

Saída em duas listas:

ATRASOS (atraso real, evidenciado)
- A última transmissão tem atraso >= limite (padrão 60 min), a viagem não chegou ao
  destino, o sinal é recente (silêncio <= frescor) e a chegada projetada
  (última parada prevista + atraso) ainda está no futuro.

ANOMALIAS
- "Parou de transmitir": transmitiu, estava abaixo do limite e parou de transmitir em
  paradas já vencidas. Provável encerramento sem transmissão.
- "Sem transmissão": nenhuma transmissão na viagem, com a janela ainda ativa.

"Agora": por padrão, o maior horário real do arquivo. Linhas DUPLICADO são removidas.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

DT_FMT = "%d/%m/%Y %H:%M:%S"
COLS_DT = [
    "horario_comercial",
    "horario_entrada_comercial_real",
    "horario_partida_comercial_real",
]
COLS_NUM = ["tempo_atraso", "tempo_tolerancia", "tempo_espera_real"]
CHAVE_VIAGEM = ["prefixo_veiculo", "servico", "codigo_linha", "dtoper"]

COLS_ALERTA = [
    "prefixo_veiculo", "placa_veiculo", "frota_veiculo", "motorista", "matricula",
    "base", "codigo_linha", "linha", "servico", "ponto", "previsto", "real",
    "atraso_min", "silencio_min", "proximo_ponto", "proximo_previsto",
    "destino_previsto", "fim_projetado", "categoria",
]
COLS_ANOMALIA = [c for c in COLS_ALERTA if c != "fim_projetado"]


def carregar(fonte) -> pd.DataFrame:
    """Lê o atrasos.TXT (TAB) de um caminho ou objeto file-like e normaliza tipos."""
    df = None
    for enc in ("utf-8", "latin-1"):
        try:
            if hasattr(fonte, "seek"):
                fonte.seek(0)
            df = pd.read_csv(fonte, sep="\t", dtype=str, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    if df is None:
        raise ValueError("Não foi possível ler o arquivo (codificação não suportada).")

    df.columns = [c.strip() for c in df.columns]
    for c in df.columns:
        df[c] = df[c].astype(str).str.strip().replace({"": np.nan, "nan": np.nan, "NaT": np.nan})

    for c in COLS_DT:
        df[c + "_dt"] = pd.to_datetime(df.get(c), format=DT_FMT, errors="coerce")
    for c in COLS_NUM:
        df[c + "_num"] = pd.to_numeric(df.get(c), errors="coerce")

    # Posição real do carro no ponto: usa a partida; se faltar, a entrada.
    df["real_dt"] = df["horario_partida_comercial_real_dt"].fillna(
        df["horario_entrada_comercial_real_dt"]
    )
    return df


def agora_padrao(df: pd.DataFrame) -> pd.Timestamp:
    """Maior horário real do arquivo, usado como proxy do momento da extração."""
    return df["real_dt"].max()


def _minutos(td) -> float:
    return td.total_seconds() / 60.0


def _resumir_viagem(g: pd.DataFrame, agora: pd.Timestamp):
    """Resume uma viagem (carro + serviço + linha) com tudo que a classificação precisa."""
    g = g.sort_values("horario_comercial_dt")
    if g["horario_comercial_dt"].isna().all():
        return None

    destino = g.loc[g["horario_comercial_dt"].idxmax()]
    concluida = pd.notna(destino["real_dt"])
    inicio = g["horario_comercial_dt"].min()
    fim_prev = g["horario_comercial_dt"].max()
    com_real = g[g["real_dt"].notna()]

    tol = g["tempo_tolerancia_num"].fillna(0)
    vencimento = g["horario_comercial_dt"] + pd.to_timedelta(tol, unit="m")
    perdidas_mask = g["real_dt"].isna() & (vencimento < agora)

    if not com_real.empty:
        lr = com_real.loc[com_real["real_dt"].idxmax()]
        medido = lr["tempo_atraso_num"]
        if pd.isna(medido):
            medido = _minutos(lr["real_dt"] - lr["horario_comercial_dt"])
        t_real = lr["real_dt"]
        sched_lr = lr["horario_comercial_dt"]
        ponto = lr["local_comercial"]
        ident = lr
        perdidas = g[perdidas_mask & (g["horario_comercial_dt"] > sched_lr)]
    else:
        medido = np.nan
        t_real = pd.NaT
        sched_lr = pd.NaT
        ponto = None
        ident = g.iloc[0]
        perdidas = g[perdidas_mask]

    silencio = _minutos(agora - t_real) if pd.notna(t_real) else np.nan
    prox_ponto, prox_sched = None, pd.NaT
    if not perdidas.empty:
        nx = perdidas.loc[perdidas["horario_comercial_dt"].idxmin()]
        prox_ponto = nx["local_comercial"]
        prox_sched = nx["horario_comercial_dt"]

    return {
        "prefixo_veiculo": ident["prefixo_veiculo"],
        "placa_veiculo": ident["placa_veiculo"],
        "frota_veiculo": ident["frota_veiculo"],
        "motorista": ident["nome"],
        "matricula": ident["matricula"],
        "base": ident["nomebase"],
        "codigo_linha": ident["codigo_linha"],
        "linha": ident["descricao_linha"],
        "servico": ident["servico"],
        "ponto": ponto,
        "previsto": sched_lr,
        "real": t_real,
        "proximo_ponto": prox_ponto,
        "proximo_previsto": prox_sched,
        "destino_previsto": fim_prev,
        "_medido": medido,
        "_silencio": silencio,
        "_inicio": inicio,
        "_fim": fim_prev,
        "_concluida": concluida,
        "_tem_real": not com_real.empty,
        "_sem_perdidas": perdidas.empty,
    }


def _escolher_viagem_atual(viagens: list, agora: pd.Timestamp):
    """Escolhe a viagem atual do carro. Viagens concluídas nunca são a atual."""
    candidatas = [v for v in viagens if not v["_concluida"]]
    if not candidatas:
        return None

    com_tx = [v for v in candidatas if v["_tem_real"]]
    if com_tx:
        ultima = max(v["real"] for v in com_tx)
        # Mesma transmissão pode cair em ida e volta; vence a perna de menor atraso.
        empate = [v for v in com_tx if v["real"] == ultima]
        return min(empate, key=lambda v: abs(v["_medido"]))

    iniciadas = [v for v in candidatas if pd.notna(v["_inicio"]) and v["_inicio"] <= agora]
    if not iniciadas:
        return None
    return max(iniciadas, key=lambda v: v["_inicio"])


def classificar(
    df: pd.DataFrame,
    agora: pd.Timestamp | None = None,
    limite_min: int = 60,
    frescor_min: int = 180,
):
    """Retorna (atrasos, anomalias) como dois DataFrames, um registro por carro."""
    if agora is None:
        agora = agora_padrao(df)
    agora = pd.Timestamp(agora)

    eh_dup = df["frota_veiculo"].fillna("").str.upper().eq("DUPLICADO") | df[
        "prefixo_veiculo"
    ].fillna("").str.upper().str.startswith("DUPLICAD")
    df = df[~eh_dup]

    por_carro = defaultdict(list)
    for _, g in df.groupby(CHAVE_VIAGEM, dropna=False):
        v = _resumir_viagem(g, agora)
        if v is not None:
            por_carro[v["prefixo_veiculo"]].append(v)

    atrasos, anomalias = [], []
    for _, viagens in por_carro.items():
        v = _escolher_viagem_atual(viagens, agora)
        if v is None:
            continue

        medido, silencio = v["_medido"], v["_silencio"]
        inicio, fim = v["_inicio"], v["_fim"]
        rec = {k: v[k] for k in COLS_ANOMALIA if k in v}
        rec["atraso_min"] = int(round(medido)) if pd.notna(medido) else None
        rec["silencio_min"] = int(round(silencio)) if pd.notna(silencio) else None

        if pd.notna(medido) and medido >= limite_min:
            fim_proj = fim + pd.to_timedelta(medido, unit="m")
            if (silencio <= frescor_min) and (fim_proj >= agora):
                rec["categoria"] = "Atraso"
                rec["fim_projetado"] = fim_proj
                atrasos.append(rec)
        else:
            janela_atual = (
                pd.notna(inicio)
                and inicio <= agora <= fim + pd.to_timedelta(frescor_min, unit="m")
            )
            if janela_atual and not v["_sem_perdidas"]:
                rec["categoria"] = (
                    "Parou de transmitir" if v["_tem_real"] else "Sem transmissão"
                )
                anomalias.append(rec)

    A = pd.DataFrame(atrasos).reindex(columns=COLS_ALERTA)
    N = pd.DataFrame(anomalias).reindex(columns=COLS_ANOMALIA)
    if not A.empty:
        A = A.sort_values("atraso_min", ascending=False).reset_index(drop=True)
    if not N.empty:
        N = N.sort_values("silencio_min", ascending=False, na_position="last").reset_index(drop=True)
    return A, N


def detectar_alertas(df, agora=None, limite_min=60, frescor_min=180) -> pd.DataFrame:
    """Atalho que retorna apenas a lista de atrasos reais."""
    return classificar(df, agora, limite_min, frescor_min)[0]


if __name__ == "__main__":
    import sys

    base = carregar(sys.argv[1] if len(sys.argv) > 1 else "atrasos.TXT")
    ref = agora_padrao(base)
    A, N = classificar(base, agora=ref)
    print(f"Agora (proxy): {ref}")
    print(f"\nATRASOS REAIS: {len(A)}")
    with pd.option_context("display.width", 240, "display.max_columns", 20):
        print(A[["prefixo_veiculo", "linha", "ponto", "real", "atraso_min", "fim_projetado"]].to_string(index=False))
    print(f"\nANOMALIAS: {len(N)}  {N['categoria'].value_counts().to_dict() if not N.empty else ''}")
    with pd.option_context("display.width", 240, "display.max_columns", 20):
        print(N[["prefixo_veiculo", "linha", "categoria", "ponto", "atraso_min", "silencio_min", "proximo_ponto"]].head(40).to_string(index=False))
