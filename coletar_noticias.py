"""
coletar_noticias.py - Coleta as noticias na SUA MAQUINA (IP residencial, que o
Google News nao bloqueia) e salva o resultado no arquivo que o painel consome
(config.yaml -> noticias.arquivo, na pasta do OneDrive).

Por que isso existe: o Streamlit Cloud roda em IP de datacenter, e o Google News
bloqueia esses IPs (retorna vazio). Entao a coleta roda aqui e o site so LE o
resultado pronto do OneDrive, exatamente como o GPS (ultima.CSV) e os Atrasos
(atrasos.TXT).

Uso:
    python coletar_noticias.py           # coleta uma vez e salva
Rode periodicamente com atualizar_noticias_loop.bat.
"""
import json
import os
import sys

from monitor import config as cfgmod
from monitor import pipeline


def _progresso(i, total, label):
    # Contador ao vivo na mesma linha do console (visual de "coletando").
    barra = ("#" * (i * 20 // max(total, 1))).ljust(20)
    print(f"\r  [{barra}] {i}/{total}  {label:<28}", end="", flush=True)


def main():
    cfg = cfgmod.load_config()
    ncfg = cfg.get("noticias", {}) or {}
    destino = ncfg.get("arquivo", "")

    print("Coletando noticias (isso leva alguns minutos)...")
    itens, meta = pipeline.executar(cfg=cfg, usar_nominatim=True, sleep_s=0.4,
                                    status_cb=_progresso)
    print()  # quebra a linha do contador
    payload = {"meta": meta, "itens": [pipeline._serial(i) for i in itens]}

    if not destino:
        print("[ERRO] Configure 'noticias.arquivo' no config.yaml.")
        sys.exit(2)
    os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1, default=str)
    print(f"OK: {len(itens)} noticias salvas em {destino}")


if __name__ == "__main__":
    main()
