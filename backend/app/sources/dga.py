from typing import Any

import httpx

from app.sources import arcgis
from app.sources.base import Batch, FeatureRecord, IngestScope, RawPayload, SourceAdapter, SourceMeta

LAYER = "https://rest-sit.mop.gob.cl/arcgis/rest/services/DGA/Red_Hidrometrica/MapServer/0"


class DgaStationsAdapter(SourceAdapter):
    meta = SourceMeta(
        key="dga_red_hidrometrica",
        name="DGA: Red Hidrométrica Nacional (catálogo de estaciones)",
        organization="Dirección General de Aguas, Ministerio de Obras Públicas",
        url=f"{LAYER}?f=json",
        license="Copyright: Dirección General de Aguas - Ministerio de Obras Públicas; sin licencia explícita",
        commercial_use="UNVERIFIED",
        cache_allowed="UNVERIFIED",
        authority="Oficial",
        attribution="Fuente: DGA, MOP",
        interval_minutes=10080,
    )

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        if not scope.bboxes:
            return []
        return [RawPayload(dataset="dga_station", url=LAYER, body=arcgis.query_esri_points(client, LAYER, scope), options={"scoped": True})]

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        records = []
        for f in parsed:
            p = f.get("properties") or {}
            records.append(
                FeatureRecord(
                    external_id=str(p.get("COD_BNA") or p.get("OBJECTID") or f.get("id")),
                    geometry=f.get("geometry"),
                    name=p.get("NOM_ESTACION"),
                    category=p.get("TIPO_ESTACION"),
                    properties={
                        k.lower(): v
                        for k, v in p.items()
                        if k in {"COD_BNA", "TIPO_ESTACION", "VIGENCIA", "NOM_CUEN", "NOM_SUBC", "ALTITUD", "AREA_DRENAJE_KM2", "INSTITUCION", "COMUNA"}
                    },
                )
            )
        return Batch(dataset=raw.dataset, url=raw.url, records=records, transformation="ArcGIS MapServer query, recorte por bbox de comunas activas")
