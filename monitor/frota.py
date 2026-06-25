"""
Leitura do relatorio de ultimas posicoes GPS (ultima.CSV do sistema SIGLA).

Regras (piloto):
- So carros com formato de frota operante xxxx.x / xxxxx.x e sufixo U/S/F/R
  (Util, Sampaio, Rapido Federal, Real Expresso).
- So posicoes da data vigente (hoje) e dentro de uma janela de tempo
  (padrao 60 min) contada a partir do horario mais recente do relatorio.
- Marca os carros proximos das ocorrencias (raio em km).

Observacao: o arquivo fica em pasta local/OneDrive; quando ausente (ex.: app
publicado na nuvem), a funcao retorna lista vazia e o painel apenas omite a
camada de carros.
"""
import re
import math
import datetime as dt

FORMATO = re.compile(r"^\d{4,5}\.[USFR]$", re.IGNORECASE)
EMPRESA = {"U": "Util", "S": "Sampaio", "F": "Rapido Federal",
           "R": "Real Expresso"}


def _to_float(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_dt(s):
    s = (s or "").strip()
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def _linhas(path):
    """Le o CSV tratando a virgula decimal de lat/lon/distancia.
    Linhas com posicao tem 16 campos; sem posicao, 13."""
    out = []
    with open(path, encoding="latin-1") as f:
        f.readline()  # cabecalho
        for ln in f:
            p = ln.rstrip("\n").rstrip("\r").split(",")
            if len(p) == 16:
                rec = (p[0], p[3], p[4], p[5] + "." + p[6],
                       p[7] + "." + p[8], p[9], p[10] + "." + p[11])
            elif len(p) == 13:
                rec = (p[0], p[3], p[4], p[5], p[6], p[7], p[8])
            else:
                continue
            veic, frota, dh, lat, lon, local, dist = rec
            out.append({"veiculo": veic.strip(), "frota": frota.strip(),
                        "dh": dh.strip(), "lat": lat.strip(),
                        "lon": lon.strip(), "local": local.strip(),
                        "dist": dist.strip()})
    return out


def carregar_frota(path, janela_min=60, hoje=None):
    """Retorna (carros, ref). carros = lista de dicts com veiculo, empresa,
    dh (datetime), lat, lon, local. ref = horario mais recente considerado."""
    hoje = hoje or dt.date.today()
    try:
        brutos = _linhas(path)
    except (FileNotFoundError, OSError):
        return [], None

    cand = []
    for r in brutos:
        if not FORMATO.match(r["veiculo"]):
            continue
        d = _parse_dt(r["dh"])
        if not d or d.date() != hoje:
            continue
        la, lo = _to_float(r["lat"]), _to_float(r["lon"])
        if la is None or lo is None:
            continue
        cand.append({
            "veiculo": r["veiculo"],
            "empresa": EMPRESA.get(r["veiculo"].split(".")[-1].upper(), ""),
            "dh": d, "lat": la, "lon": lo, "local": r["local"],
            "dist_local": _to_float(r.get("dist", "")),
        })

    if not cand:
        return [], None
    ref = max(c["dh"] for c in cand)
    limite = ref - dt.timedelta(minutes=int(janela_min))
    frescos = [c for c in cand if c["dh"] >= limite]
    frescos.sort(key=lambda c: c["dh"], reverse=True)
    return frescos, ref


def _dist_km(la1, lo1, la2, lo2):
    latm = math.radians((la1 + la2) / 2.0)
    kx = 111.320 * math.cos(latm)
    ky = 110.574
    return math.hypot((lo1 - lo2) * kx, (la1 - la2) * ky)


def marcar_proximos(carros, ocorrencias, raio_km=15.0):
    """Anota cada carro com dist_ocor (km ate a ocorrencia mais proxima) e
    proximo (bool). Retorna o numero de carros proximos."""
    pts = [(o["lat"], o["lon"]) for o in ocorrencias
           if o.get("lat") is not None and o.get("lon") is not None]
    n = 0
    for c in carros:
        best = None
        for la, lo in pts:
            d = _dist_km(c["lat"], c["lon"], la, lo)
            if best is None or d < best:
                best = d
        c["dist_ocor"] = best
        c["proximo"] = best is not None and best <= raio_km
        if c["proximo"]:
            n += 1
    return n
