from typing import Any

import httpx

from app.sources import arcgis
from app.sources.base import Batch, FeatureRecord, IndexRecord, IngestScope, RawPayload, SourceAdapter, SourceMeta

BASE = "https://services5.arcgis.com/hUyD8u3TeZLKPe4T/arcgis/rest/services/Censo2024_v2/FeatureServer"
BLOCKS = f"{BASE}/5"
COMUNAS = f"{BASE}/11"
COUNTS = ("n_per", "n_vp", "n_hog", "n_edad_0_5", "n_edad_60_mas", "n_discapacidad")
BLOCK_FIELDS = ",".join(("CUT", "MANZENT", "TIPO_MZ", "CATEGORIA", "ENTIDAD", *COUNTS))


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) else 0


def block_record(feature: dict[str, Any]) -> FeatureRecord | None:
    p = feature.get("properties") or {}
    code = p.get("MANZENT")
    if code is None:
        return None
    return FeatureRecord(
        external_id=str(int(code)),
        geometry=feature.get("geometry"),
        name=p.get("ENTIDAD"),
        category=(p.get("TIPO_MZ") or "").lower() or None,
        properties={"cut": str(p.get("CUT") or "").zfill(5), "categoria": p.get("CATEGORIA"), **{k: _int(p.get(k)) for k in COUNTS}},
    )


def comuna_record(attributes: dict[str, Any]) -> IndexRecord | None:
    cut = attributes.get("CUT")
    if cut is None:
        return None
    return IndexRecord(
        index_key="censo2024_poblacion",
        cut_code=str(cut).zfill(5),
        year=2024,
        value=_int(attributes.get("n_per")),
        level=None,
        components={"viviendas_particulares": _int(attributes.get("n_vp")), "hogares": _int(attributes.get("n_hog")), "comuna": attributes.get("COMUNA")},
    )


class IneCensusAdapter(SourceAdapter):
    meta = SourceMeta(
        key="ine_censo2024",
        name="INE: Censo de Población y Vivienda 2024 por manzana y entidad",
        organization="Instituto Nacional de Estadísticas (INE)",
        url=f"{BASE}?f=json",
        license="CC BY-SA 4.0 (términos de uso y licencia de datos abiertos del INE)",
        commercial_use="Permitido con atribución y licencia igual (CC BY-SA 4.0)",
        cache_allowed="Sí, según CC BY-SA 4.0",
        authority="Oficial",
        attribution="Fuente: INE, Censo de Población y Vivienda 2024, base manzana-entidad",
        interval_minutes=43200,
    )

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        payloads = [RawPayload(dataset="census_comuna", url=COMUNAS, body=arcgis.query_attributes(client, COMUNAS), options={"scoped": False})]
        if scope.bboxes:
            blocks = arcgis.query_geojson(client, BLOCKS, scope, out_fields=BLOCK_FIELDS, page_size=2000, max_offset=0.00001)
            payloads.append(RawPayload(dataset="census_block", url=BLOCKS, body=blocks, options={"scoped": True}))
        return payloads

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        if raw.dataset == "census_comuna":
            records = [r for r in (comuna_record(a) for a in parsed) if r]
            transformation = "Totales comunales de la capa Comunal_CPV24 (personas, viviendas particulares, hogares)"
        else:
            records = [r for r in (block_record(f) for f in parsed) if r]
            transformation = "Manzanas urbanas y entidades rurales de Manzanas_Entidades_CPV24; outSR=4326, geometría simplificada a ~1 m; solo conteos agregados"
        return Batch(dataset=raw.dataset, url=raw.url, records=records, transformation=transformation, version="Censo 2024")
