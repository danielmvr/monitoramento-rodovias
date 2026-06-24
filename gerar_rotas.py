"""
Regera data/linhas_rotas.json a partir de anatomiaLinhas.CSV + siglas.XLS.

Rode sempre que atualizar os arquivos brutos:
    python gerar_rotas.py

Requer pandas e xlrd (uso offline, fora do app):
    pip install pandas xlrd

Logica:
- 1 rota por codigo_linha (dedup das duplicatas por horario): usa o servico
  com mais paradas e ordena as paradas (local_comercial) por horario.
- Cruza cada sigla de parada com siglas.XLS para obter cidade + coordenada
  (cai para coords_builtin.json quando a sigla nao tem coordenada).
"""
import os
import json
import unicodedata

import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))


def p(*x):
    return os.path.join(BASE, *x)


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def main():
    builtin = {}
    try:
        with open(p("data", "coords_builtin.json"), encoding="utf-8") as f:
            for k, v in json.load(f).items():
                if isinstance(v, list) and len(v) >= 2:
                    builtin[norm(k)] = (v[0], v[1])
    except FileNotFoundError:
        pass

    sg = pd.read_excel(p("siglas.XLS"), engine="xlrd")
    sg.columns = [str(c).strip() for c in sg.columns]
    sig = {}
    for _, r in sg.iterrows():
        s = str(r["Sigla"]).strip()
        cidade = str(r["Cidade"]).strip()
        try:
            la = float(r["Latitude"])
            lo = float(r["Longitude"])
            if la != la or lo != lo:
                la = lo = None
        except Exception:
            la = lo = None
        if la is None:
            c = builtin.get(norm(cidade))
            if c:
                la, lo = c
        sig[s] = (cidade, la, lo)

    cols = ["dtoper", "servico", "codigo_linha", "descricao_linha",
            "local_comercial", "horario_comercial"]
    df = pd.read_csv(p("anatomiaLinhas.CSV"), usecols=cols, dtype=str,
                     low_memory=False)
    df["local_comercial"] = df["local_comercial"].astype(str).str.strip()
    df["h"] = pd.to_datetime(df["horario_comercial"], dayfirst=True,
                             errors="coerce")
    sizes = df.groupby(["codigo_linha", "dtoper", "servico"]).size()
    sizes = sizes.reset_index(name="n")
    best = sizes.sort_values("n", ascending=False).drop_duplicates("codigo_linha")
    bestset = set(map(tuple, best[["codigo_linha", "dtoper", "servico"]].values))
    df["key"] = list(zip(df["codigo_linha"], df["dtoper"], df["servico"]))
    sub = df[df["key"].isin(bestset)].sort_values(["codigo_linha", "h"])

    linhas = []
    for cod, g in sub.groupby("codigo_linha"):
        seq = []
        for s in g["local_comercial"].tolist():
            if not s or s == "nan":
                continue
            if not seq or seq[-1] != s:
                seq.append(s)
        if len(seq) < 2:
            continue
        stops = []
        for s in seq:
            cidade, la, lo = sig.get(s, (s, None, None))
            stops.append([s, cidade,
                          round(la, 5) if la is not None else None,
                          round(lo, 5) if lo is not None else None])
        linhas.append({"codigo": cod, "desc": g["descricao_linha"].iloc[0],
                       "label": f"{seq[0]}x{seq[-1]}", "stops": stops})

    out = p("data", "linhas_rotas.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(linhas, f, ensure_ascii=False)
    print(f"{len(linhas)} linhas gravadas em {out}")


if __name__ == "__main__":
    main()
