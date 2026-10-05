import threading
import time
from collections import OrderedDict
from typing import Any

import httpx

from app.config import get_settings

MIN_INTERVAL_SECONDS = 1.1
CACHE_SIZE = 2000
ATTRIBUTION = "Búsqueda de direcciones: Nominatim, datos © OpenStreetMap (ODbL)"

_lock = threading.Lock()
_last_call = 0.0
_cache: OrderedDict[tuple, list[dict[str, Any]]] = OrderedDict()


class GeocodeError(RuntimeError):
    pass


def _normalize(query: str) -> str:
    return " ".join(query.lower().split())


def search_address(query: str, bbox: tuple[float, float, float, float], comuna: str, limit: int = 5) -> list[dict[str, Any]]:
    cleaned = _normalize(query)
    if len(cleaned) < 3:
        return []
    key = (cleaned, tuple(round(v, 3) for v in bbox), limit)
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    settings = get_settings()
    west, south, east, north = bbox
    params = {
        "q": f"{query}, {comuna}, Chile",
        "format": "jsonv2",
        "limit": limit,
        "countrycodes": "cl",
        "viewbox": f"{west},{north},{east},{south}",
        "bounded": 1,
        "accept-language": "es",
    }
    global _last_call
    with _lock:
        wait = MIN_INTERVAL_SECONDS - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()
        try:
            response = httpx.get(settings.geocoder_url, params=params, headers={"User-Agent": settings.http_user_agent}, timeout=15)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise GeocodeError(f"El servicio de direcciones no respondió: {exc}")
    results = [
        {"name": item.get("display_name", ""), "lon": float(item["lon"]), "lat": float(item["lat"]), "kind": "address", "attribution": ATTRIBUTION}
        for item in payload
        if "lon" in item and "lat" in item
    ]
    with _lock:
        _cache[key] = results
        if len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return results
