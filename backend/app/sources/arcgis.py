import time
from typing import Any

import httpx

from app.sources.base import IngestScope, SourceError

PAGE_SIZE = 1000
MAX_PAGES = 200
RATE_LIMIT_WAIT_SECONDS = 62


def query_geojson(
    client: httpx.Client,
    layer_url: str,
    scope: IngestScope | None = None,
    where: str = "1=1",
    out_fields: str = "*",
    page_size: int = PAGE_SIZE,
    max_offset: float | None = None,
) -> list[dict[str, Any]]:
    envelopes = list(scope.bboxes) if scope and scope.bboxes else [None]
    features: dict[str, dict[str, Any]] = {}
    for envelope in envelopes:
        for feature in _paged(client, layer_url, where, out_fields, envelope, page_size, max_offset):
            key = str(feature.get("id") or feature.get("properties", {}).get("objectid") or len(features))
            features[key] = feature
    return list(features.values())


def query_attributes(client: httpx.Client, layer_url: str, where: str = "1=1") -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    offset = 0
    for _ in range(MAX_PAGES):
        params = {
            "where": where,
            "outFields": "*",
            "returnGeometry": "false",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE,
        }
        data = _get_json(client, f"{layer_url}/query", params)
        page = [f["attributes"] for f in data.get("features", [])]
        result.extend(page)
        if not data.get("exceededTransferLimit") or not page:
            return result
        offset += len(page)
    raise SourceError(f"demasiadas paginas en {layer_url}")


def layer_info(client: httpx.Client, layer_url: str) -> dict[str, Any]:
    return _get_json(client, layer_url, {"f": "json"})


def _paged(client, layer_url, where, out_fields, envelope, page_size, max_offset):
    offset = 0
    for _ in range(MAX_PAGES):
        params: dict[str, Any] = {
            "where": where,
            "outFields": out_fields,
            "outSR": 4326,
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": page_size,
            "geometryPrecision": 6,
        }
        if max_offset:
            params["maxAllowableOffset"] = max_offset
        if envelope:
            params.update(
                {
                    "geometry": ",".join(str(v) for v in envelope),
                    "geometryType": "esriGeometryEnvelope",
                    "inSR": 4326,
                    "spatialRel": "esriSpatialRelIntersects",
                }
            )
        data = _get_json(client, f"{layer_url}/query", params)
        page = data.get("features", [])
        yield from page
        exceeded = data.get("exceededTransferLimit") or data.get("properties", {}).get("exceededTransferLimit")
        if not exceeded or not page:
            return
        offset += len(page)
    raise SourceError(f"demasiadas paginas en {layer_url}")


def query_esri_points(client: httpx.Client, layer_url: str, scope: IngestScope) -> list[dict[str, Any]]:
    features: dict[str, dict[str, Any]] = {}
    for envelope in scope.bboxes:
        params = {
            "where": "1=1",
            "outFields": "*",
            "outSR": 4326,
            "f": "json",
            "geometry": ",".join(str(v) for v in envelope),
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
        }
        data = _get_json(client, f"{layer_url}/query", params)
        if data.get("exceededTransferLimit"):
            raise SourceError(f"{layer_url}: más de {len(data.get('features', []))} registros en un recorte; reduzca el área")
        for f in data.get("features", []):
            g = f.get("geometry") or {}
            if "x" not in g:
                continue
            attributes = f.get("attributes") or {}
            key = str(attributes.get("OBJECTID") or len(features))
            features[key] = {
                "type": "Feature",
                "id": key,
                "geometry": {"type": "Point", "coordinates": [g["x"], g["y"]]},
                "properties": attributes,
            }
    return list(features.values())


def _get_json(client: httpx.Client, url: str, params: dict[str, Any], attempts: int = 4) -> dict[str, Any]:
    for attempt in range(attempts):
        response = client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        error = data.get("error") if isinstance(data, dict) else None
        if error and error.get("code") == 429 and attempt < attempts - 1:
            time.sleep(RATE_LIMIT_WAIT_SECONDS)
            continue
        if error:
            raise SourceError(f"ArcGIS error en {url}: {error}")
        return data
    raise SourceError(f"ArcGIS sin respuesta válida en {url}")
