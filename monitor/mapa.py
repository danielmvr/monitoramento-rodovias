"""Construcao dos mapas (folium): mapa geral e mini-mapa por noticia."""
import html as _html

import folium
from folium.plugins import MarkerCluster

# categoria -> cor de marcador folium (paleta fixa do Leaflet/AwesomeMarkers)
COR_FOLIUM = {
    "Interdicao": "darkred",
    "Acidente": "red",
    "Clima/Natureza": "blue",
    "Manifestacao": "purple",
    "Obras": "orange",
    "Congestionamento": "beige",
    "Outros": "gray",
}

TILES = "CartoDB dark_matter"

CENTRO_BR = (-16.5, -48.0)


def _fmt_data(d):
    try:
        return d.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return ""


def _popup_html(item):
    t = _html.escape(item.get("titulo", ""))
    resumo = _html.escape(item.get("resumo", ""))
    fonte = _html.escape(item.get("fonte", ""))
    local = _html.escape(item.get("local", ""))
    cat = _html.escape(item.get("categoria", ""))
    sev = _html.escape(item.get("severidade", ""))
    link = item.get("link", "")
    data = _fmt_data(item.get("publicado"))
    cor = item.get("cor", "#7f8c8d")
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:300px">
      <div style="font-weight:bold;font-size:13px;margin-bottom:4px">{t}</div>
      <div style="margin:4px 0">
        <span style="background:{cor};color:#fff;padding:1px 6px;border-radius:3px;
        font-size:11px">{cat} - {sev}</span>
      </div>
      <div style="font-size:12px;color:#333;margin:6px 0">{resumo}</div>
      <div style="font-size:11px;color:#666">Local: {local}</div>
      <div style="font-size:11px;color:#666">{fonte} - {data}</div>
      <a href="{link}" target="_blank" style="font-size:12px">Abrir noticia</a>
    </div>
    """


def construir_mapa(itens, usar_cluster=True, carros=None, so_proximos=False):
    pts = [(i["lat"], i["lon"]) for i in itens
           if i.get("lat") is not None and i.get("lon") is not None]
    if pts:
        lat = sum(p[0] for p in pts) / len(pts)
        lon = sum(p[1] for p in pts) / len(pts)
        centro, zoom = (lat, lon), 5
    else:
        centro, zoom = CENTRO_BR, 4

    m = folium.Map(location=centro, zoom_start=zoom, control_scale=True,
                   tiles=TILES)
    alvo = MarkerCluster().add_to(m) if usar_cluster else m
    for it in itens:
        if it.get("lat") is None or it.get("lon") is None:
            continue
        cor = COR_FOLIUM.get(it.get("categoria"), "gray")
        folium.Marker(
            location=[it["lat"], it["lon"]],
            popup=folium.Popup(_popup_html(it), max_width=320),
            tooltip=it.get("titulo", "")[:80],
            icon=folium.Icon(color=cor, icon="info-sign"),
        ).add_to(alvo)

    if carros:
        fg = folium.FeatureGroup(name="Carros (GPS)").add_to(m)
        for c in carros:
            prox = c.get("proximo")
            if so_proximos and not prox:
                continue
            dist = c.get("dist_ocor")
            dtxt = c["dh"].strftime("%d/%m %H:%M") if c.get("dh") else ""
            tip = f"{c.get('veiculo', '')} ({c.get('empresa', '')}) {dtxt}"
            if dist is not None:
                tip += f" - {dist:.0f} km da ocorrencia"
            if prox:
                folium.Marker(
                    location=[c["lat"], c["lon"]], tooltip=tip,
                    icon=folium.Icon(color="green", icon="bus", prefix="fa"),
                ).add_to(fg)
            else:
                folium.CircleMarker(
                    location=[c["lat"], c["lon"]], radius=3, color="#2f6fd0",
                    fill=True, fill_color="#2f6fd0", fill_opacity=0.7,
                    weight=1, tooltip=tip,
                ).add_to(fg)
    return m


def construir_mini_mapa(item, zoom=11):
    if item.get("lat") is None or item.get("lon") is None:
        return None
    m = folium.Map(location=[item["lat"], item["lon"]], zoom_start=zoom,
                   control_scale=True, tiles=TILES)
    cor = COR_FOLIUM.get(item.get("categoria"), "gray")
    folium.Marker(
        location=[item["lat"], item["lon"]],
        tooltip=item.get("local", ""),
        icon=folium.Icon(color=cor, icon="info-sign"),
    ).add_to(m)
    return m
