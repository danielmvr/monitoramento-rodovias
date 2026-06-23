"""
Autoteste OFFLINE da logica (nao acessa a internet).
Valida: filtragem, deduplicacao, resumo, classificacao, extracao de local,
geocodificacao builtin e geracao do mapa.  Rode:  python teste_offline.py
"""
import os
import sys
import datetime as dt

from monitor import config as cfgmod
from monitor import pipeline, mapa

RSS_AMOSTRA = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Amostra</title>
<item>
  <title>Acidente na BR-040 deixa transito lento em Juiz de Fora</title>
  <link>https://news.google.com/rss/articles/aaa1</link>
  <pubDate>Mon, 23 Jun 2026 12:00:00 GMT</pubDate>
  <description>Uma colisao entre dois caminhoes interditou parcialmente a
  pista da BR-040 na altura do km 776, em Juiz de Fora, na manha desta terca.
  O acidente provocou congestionamento de varios quilometros no sentido Rio.
  A concessionaria trabalha para liberar a via. Nao ha vitimas confirmadas.</description>
  <source url="https://g1.globo.com">G1</source>
</item>
<item>
  <title>Via Dutra tem congestionamento apos tombamento de carreta em Resende</title>
  <link>https://news.google.com/rss/articles/bbb2</link>
  <pubDate>Mon, 23 Jun 2026 09:30:00 GMT</pubDate>
  <description>O tombamento de uma carreta provocou congestionamento de cerca
  de 8 km na Via Dutra, em Resende, no Rio de Janeiro, no inicio da manha.
  Houve lentidao de varios quilometros. Equipes foram acionadas para o local.</description>
  <source url="https://www.cnn.com.br">CNN</source>
</item>
<item>
  <title>Obras interditam a BR-381 Fernao Dias em Pouso Alegre</title>
  <link>https://news.google.com/rss/articles/ccc3</link>
  <pubDate>Sun, 22 Jun 2026 18:00:00 GMT</pubDate>
  <description>Obras de recuperacao do pavimento interditam uma faixa da
  BR-381, a Fernao Dias, em Pouso Alegre, no Sul de Minas. O servico deve
  durar uma semana e ha lentidao na regiao durante o dia.</description>
  <source url="https://oglobo.globo.com">O Globo</source>
</item>
<item>
  <title>Prefeitura inaugura nova praca no centro</title>
  <link>https://news.google.com/rss/articles/ddd4</link>
  <pubDate>Sun, 22 Jun 2026 10:00:00 GMT</pubDate>
  <description>Evento cultural reuniu moradores no fim de semana.</description>
  <source url="https://exemplo.com">Exemplo</source>
</item>
</channel></rss>"""


def fetch_fake(url):
    return RSS_AMOSTRA


def main():
    cfg = cfgmod.load_config()
    cfg["app"]["fetch_artigo"] = False
    cfg["app"]["buscar_hubs"] = True

    itens, meta = pipeline.executar(
        cfg=cfg, fetch_fn=fetch_fake, usar_nominatim=False, sleep_s=0)

    print("Itens coletados (deduplicados):", len(itens))
    assert len(itens) == 3, "esperado 3 itens relevantes"

    cats = {i["categoria"] for i in itens}
    print("Categorias:", cats)
    assert "Interdicao" in cats and "Acidente" in cats

    falhas = 0
    for i in itens:
        loc_ok = i["lat"] is not None and i["lon"] is not None
        print("\n- " + i["titulo"])
        print("  categoria=%s sev=%s cidade=%s km=%s geo=%s" % (
            i["categoria"], i["severidade"], i["cidade"], i["km"],
            i["geo_origem"]))
        print("  lat/lon=%s,%s  local=%s" % (i["lat"], i["lon"], i["local"]))
        print("  resumo: " + i["resumo"][:110] + "...")
        if not loc_ok or not i["resumo"]:
            falhas += 1
    assert falhas == 0, "todos os itens deveriam ter local e resumo"

    bn = next(i for i in itens if "BR-040" in i["titulo"])
    assert bn["km"] == "776", "km esperado 776, obtido %s" % bn["km"]
    assert bn["cidade"] == "JUIZ DE FORA"

    dutra = next(i for i in itens if "Dutra" in i["titulo"])
    assert dutra["cidade"] == "RESENDE", "esperado RESENDE, obtido %s" % dutra["cidade"]

    m = mapa.construir_mapa(itens)
    out_html = os.path.join(os.environ.get("OUT_DIR", "."), "mapa_teste.html")
    m.save(out_html)
    assert os.path.exists(out_html)
    assert mapa.construir_mini_mapa(itens[0]) is not None

    rec = pipeline.carregar_resultados()
    assert rec and len(rec["itens"]) == 3
    assert isinstance(rec["itens"][0]["publicado"], dt.datetime)

    print("\nOK: todos os testes passaram. Mapa salvo em", out_html)


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print("FALHA:", e)
        sys.exit(1)
