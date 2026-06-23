"""Geocodificacao: builtin -> cache em disco -> Nominatim (opcional)."""
import json

from .config import normalizar, load_builtin_coords, data_path, uf_por_cidade

try:
    from geopy.geocoders import Nominatim
    from geopy.extra.rate_limiter import RateLimiter
except ImportError:
    Nominatim = None
    RateLimiter = None


def rep_rodovias(cfg):
    """nome_da_rodovia -> (lat, lon) ponto representativo."""
    out = {}
    for r in cfg.get("rodovias", []):
        if r.get("lat") is not None and r.get("lon") is not None:
            out[r["nome"]] = (float(r["lat"]), float(r["lon"]))
    return out


class GeoCoder:
    def __init__(self, cfg=None, usar_nominatim=True):
        cfg = cfg or {"hubs": []}
        builtin = load_builtin_coords()
        self.builtin = {normalizar(k): (v[0], v[1])
                        for k, v in builtin.items()
                        if isinstance(v, list) and len(v) >= 2}
        self.uf_map = uf_por_cidade(cfg)
        self.cache_file = data_path("geocode_cache.json")
        self.cache = self._load_cache()
        self.usar_nominatim = usar_nominatim and Nominatim is not None
        self._geocode = None
        if self.usar_nominatim:
            try:
                geoloc = Nominatim(user_agent="monitor-rodovias-util/1.0",
                                   timeout=10)
                self._geocode = RateLimiter(
                    geoloc.geocode, min_delay_seconds=1.1,
                    swallow_exceptions=True)
            except Exception:
                self.usar_nominatim = False

    def _load_cache(self):
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def salvar(self):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=0)
        except Exception:
            pass

    def geocode_cidade(self, nome, uf=None):
        if not nome:
            return None
        key = normalizar(nome)
        if key in self.builtin:
            return self.builtin[key]
        if key in self.cache:
            v = self.cache[key]
            return tuple(v) if v else None
        if self.usar_nominatim and self._geocode is not None:
            uf = uf or self.uf_map.get(key)
            q = f"{nome}, {uf}, Brasil" if uf else f"{nome}, Brasil"
            loc = self._geocode(q)
            res = [loc.latitude, loc.longitude] if loc else None
            self.cache[key] = res
            return tuple(res) if res else None
        return None

    def localizar(self, item, rod_rep):
        """Define coordenadas e rotulo de local para um item processado.
        Retorna dict com lat, lon, local, geo_origem."""
        cidade = item.get("cidade")
        km = item.get("km")
        if cidade:
            c = self.geocode_cidade(cidade)
            if c:
                label = cidade + (f" - km {km}" if km else "")
                return {"lat": c[0], "lon": c[1], "local": label,
                        "geo_origem": "cidade"}
        rod = item.get("rodovia")
        rep = rod_rep.get(rod)
        if rep:
            label = rod + (f" - km {km}" if km else "") + " (aprox.)"
            return {"lat": rep[0], "lon": rep[1], "local": label,
                    "geo_origem": "rodovia"}
        return {"lat": None, "lon": None,
                "local": cidade or rod or "Local nao identificado",
                "geo_origem": "indefinido"}
