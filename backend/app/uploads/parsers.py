import csv
import io
import json
import os
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

from pypdf import PdfReader

LAT_KEYS = ("lat", "latitud", "latitude", "y")
LON_KEYS = ("lon", "lng", "long", "longitud", "longitude", "x")
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 150


class ParseError(ValueError):
    pass


@dataclass
class ParsedFeature:
    geometry: dict[str, Any] | None
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class TextChunk:
    page: int | None
    content: str


def normalize_key(key: str) -> str:
    text = unicodedata.normalize("NFKD", key or "").encode("ascii", "ignore").decode().strip().lower()
    return text.replace(" ", "_")


def normalize_value(value: str) -> str:
    return normalize_key(value).replace("_", " ").strip()


def decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ParseError("No se pudo leer el archivo como texto")


def parse_csv(data: bytes) -> list[ParsedFeature]:
    text = decode(data)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ParseError("El CSV no tiene encabezados")
    keys = {normalize_key(k): k for k in reader.fieldnames}
    lat_key = next((keys[k] for k in LAT_KEYS if k in keys), None)
    lon_key = next((keys[k] for k in LON_KEYS if k in keys), None)
    features = []
    for line, raw in enumerate(reader, start=2):
        props = {normalize_key(k): (v.strip() if isinstance(v, str) else v) for k, v in raw.items() if k}
        geometry = None
        if lat_key and lon_key and raw.get(lat_key) and raw.get(lon_key):
            try:
                lat = float(str(raw[lat_key]).replace(",", "."))
                lon = float(str(raw[lon_key]).replace(",", "."))
            except ValueError:
                raise ParseError(f"Coordenadas no numéricas en la línea {line}")
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ParseError(f"Coordenadas fuera de rango en la línea {line}")
            geometry = {"type": "Point", "coordinates": [lon, lat]}
        features.append(ParsedFeature(geometry, props))
    return features


def parse_geojson(data: bytes) -> list[ParsedFeature]:
    try:
        doc = json.loads(decode(data))
    except json.JSONDecodeError as exc:
        raise ParseError(f"GeoJSON inválido: {exc}")
    if doc.get("type") == "FeatureCollection":
        items = doc.get("features", [])
    elif doc.get("type") == "Feature":
        items = [doc]
    else:
        raise ParseError("Se esperaba un GeoJSON de tipo FeatureCollection o Feature")
    crs = ((doc.get("crs") or {}).get("properties") or {}).get("name", "")
    if crs and "4326" not in crs and "CRS84" not in crs:
        raise ParseError(f"El GeoJSON declara el sistema de coordenadas {crs}; conviértalo a WGS84 (EPSG:4326)")
    return [
        ParsedFeature(f.get("geometry"), {normalize_key(k): v for k, v in (f.get("properties") or {}).items()})
        for f in items
    ]


def parse_kml(data: bytes) -> list[ParsedFeature]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ParseError(f"KML inválido: {exc}")
    features = []
    for placemark in root.iter():
        if not placemark.tag.endswith("Placemark"):
            continue
        props: dict[str, Any] = {}
        geometry = None
        for child in placemark.iter():
            tag = child.tag.split("}")[-1]
            if tag == "name" and child.text:
                props["nombre"] = child.text.strip()
            elif tag == "description" and child.text:
                props["descripcion"] = child.text.strip()
            elif tag == "Data" and child.get("name"):
                value = next((c.text for c in child if c.tag.endswith("value")), None)
                props[normalize_key(child.get("name"))] = value
            elif tag == "SimpleData" and child.get("name"):
                props[normalize_key(child.get("name"))] = child.text
        geometry = _kml_geometry(placemark)
        features.append(ParsedFeature(geometry, props))
    if not features:
        raise ParseError("El KML no contiene elementos Placemark")
    return features


def _coords(text: str) -> list[list[float]]:
    points = []
    for token in (text or "").split():
        parts = token.split(",")
        if len(parts) >= 2:
            points.append([float(parts[0]), float(parts[1])])
    return points


def _kml_geometry(placemark: ET.Element) -> dict[str, Any] | None:
    polygons, lines, points = [], [], []
    for element in placemark.iter():
        tag = element.tag.split("}")[-1]
        if tag == "Polygon":
            rings = []
            for ring_parent in element:
                ring_tag = ring_parent.tag.split("}")[-1]
                if ring_tag in ("outerBoundaryIs", "innerBoundaryIs"):
                    coords = next((c.text for c in ring_parent.iter() if c.tag.endswith("coordinates")), "")
                    ring = _coords(coords)
                    if ring:
                        rings.append(ring)
            if rings:
                polygons.append(rings)
        elif tag == "LineString":
            coords = next((c.text for c in element if c.tag.endswith("coordinates")), "")
            lines.append(_coords(coords))
        elif tag == "Point":
            coords = next((c.text for c in element if c.tag.endswith("coordinates")), "")
            pts = _coords(coords)
            if pts:
                points.append(pts[0])
    if polygons:
        return {"type": "MultiPolygon", "coordinates": polygons}
    if lines:
        return {"type": "MultiLineString", "coordinates": lines} if len(lines) > 1 else {"type": "LineString", "coordinates": lines[0]}
    if points:
        return {"type": "Point", "coordinates": points[0]}
    return None


def _plain(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and value != value:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def parse_gis(data: bytes) -> list[ParsedFeature]:
    from pyogrio import raw
    from pyogrio.errors import DataSourceError, DataLayerError

    try:
        meta, _, geometries, field_data = raw.read(data)
    except (DataSourceError, DataLayerError) as exc:
        raise ParseError(f"No se pudo leer el archivo SIG: {exc}")
    if not meta.get("crs"):
        raise ParseError("El archivo no declara su sistema de coordenadas (falta el .prj en el shapefile). Inclúyalo o exporte en WGS84.")
    if geometries is None or len(geometries) == 0:
        return []
    with tempfile.TemporaryDirectory() as folder:
        target = os.path.join(folder, "convertido.geojson")
        raw.write(
            target,
            geometries,
            field_data,
            fields=meta["fields"],
            geometry_type=meta["geometry_type"],
            crs=meta["crs"],
            driver="GeoJSON",
            layer_options={"RFC7946": "YES"},
        )
        with open(target, "rb") as handle:
            converted = json.loads(handle.read().decode("utf-8"))
    return [
        ParsedFeature(f.get("geometry"), {normalize_key(k): _plain(v) for k, v in (f.get("properties") or {}).items()})
        for f in converted.get("features", [])
    ]


def parse_features(filename: str, data: bytes) -> list[ParsedFeature]:
    name = filename.lower()
    if name.endswith(".csv") or name.endswith(".txt"):
        return parse_csv(data)
    if name.endswith(".geojson") or name.endswith(".json"):
        return parse_geojson(data)
    if name.endswith(".kml"):
        return parse_kml(data)
    if name.endswith(".kmz"):
        import zipfile

        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            kml_name = next((n for n in archive.namelist() if n.lower().endswith(".kml")), None)
            if not kml_name:
                raise ParseError("El KMZ no contiene un archivo KML")
            return parse_kml(archive.read(kml_name))
    if name.endswith(".zip") or name.endswith(".gpkg"):
        return parse_gis(data)
    raise ParseError("Formato no soportado. Use CSV, GeoJSON, KML, KMZ, shapefile comprimido en .zip o GeoPackage.")


def extract_text(filename: str, data: bytes) -> tuple[list[TextChunk], int]:
    name = filename.lower()
    if name.endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(data))
        except Exception as exc:
            raise ParseError(f"PDF ilegible: {exc}")
        pages = [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
    elif name.endswith((".txt", ".md")):
        pages = [(None, decode(data))]
    else:
        raise ParseError("Documento no soportado. Use PDF, TXT o MD.")
    chunks = []
    for page, text in pages:
        clean = " ".join(text.split())
        start = 0
        while start < len(clean):
            end = min(len(clean), start + CHUNK_CHARS)
            if end < len(clean):
                cut = clean.rfind(". ", start + CHUNK_CHARS // 2, end)
                end = cut + 1 if cut > 0 else end
            chunks.append(TextChunk(page, clean[start:end].strip()))
            if end >= len(clean):
                break
            start = max(end - CHUNK_OVERLAP, start + 1)
    if not chunks:
        raise ParseError("No se encontró texto en el documento (¿es un PDF escaneado sin OCR?)")
    return chunks, len(pages)
