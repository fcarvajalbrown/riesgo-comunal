from dataclasses import dataclass
from typing import Any

import httpx

from app.sources.base import Batch, FeatureRecord, IngestScope, RawPayload, SourceAdapter, SourceError, SourceMeta

BASE = "https://geoportal.cl/geoserver"
PAGE_SIZE = 2000


@dataclass(frozen=True)
class WfsLayer:
    dataset: str
    workspace: str
    type_name: str
    id_field: str
    name_field: str
    category_field: str
    owner: str


LAYERS = (
    WfsLayer(
        "school",
        "Establecimientos_Educacion_Escolar",
        "Establecimientos_Educacion_Escolar:establecimientos_educacin_escolar",
        id_field="rbd",
        name_field="nom_rbd",
        category_field="tipo_depen",
        owner="MINEDUC",
    ),
    WfsLayer(
        "health_facility",
        "Establecimientos_Salud",
        "Establecimientos_Salud:establecimientos_de_salud",
        id_field="cod_vig",
        name_field="nombre",
        category_field="tipo",
        owner="MINSAL",
    ),
)


class GeoportalAdapter(SourceAdapter):
    meta = SourceMeta(
        key="ide_geoportal",
        name="IDE Chile Geoportal: establecimientos educacionales y de salud (WFS)",
        organization="Infraestructura de Datos Geoespaciales de Chile (geoportal.cl), datos de MINEDUC y MINSAL",
        url=f"{BASE}/Establecimientos_Salud/wfs?service=WFS&request=GetCapabilities",
        license="Capabilities WFS declaran Fees=NONE y AccessConstraints=NONE; sin licencia explícita",
        commercial_use="UNVERIFIED",
        cache_allowed="UNVERIFIED",
        authority="Oficial (MINEDUC, MINSAL vía IDE Chile)",
        attribution="Fuente: IDE Chile (geoportal.cl), MINEDUC y MINSAL",
        interval_minutes=10080,
    )

    def __init__(self, layers: tuple[WfsLayer, ...] = LAYERS):
        self.layers = layers

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        payloads = []
        if not scope.bboxes:
            return payloads
        for layer in self.layers:
            url = f"{BASE}/{layer.workspace}/wfs"
            features: dict[str, Any] = {}
            for bbox in scope.bboxes:
                for feature in self._paged(client, url, layer.type_name, bbox):
                    features[str(feature.get("id"))] = feature
            payloads.append(RawPayload(dataset=layer.dataset, url=url, body=list(features.values()), options={"layer": layer, "scoped": True}))
        return payloads

    def _paged(self, client, url, type_name, bbox):
        start = 0
        while True:
            params: dict[str, Any] = {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": type_name,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": PAGE_SIZE,
                "startIndex": start,
            }
            if bbox:
                params["bbox"] = ",".join(str(v) for v in bbox) + ",EPSG:4326"
            response = client.get(url, params=params)
            response.raise_for_status()
            if "json" not in response.headers.get("content-type", ""):
                raise SourceError(f"WFS no devolvió JSON: {response.text[:300]}")
            data = response.json()
            page = data.get("features", [])
            yield from page
            if len(page) < PAGE_SIZE:
                return
            start += len(page)

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        layer: WfsLayer = raw.options["layer"]
        records = []
        for f in parsed:
            p = f.get("properties") or {}
            records.append(
                FeatureRecord(
                    external_id=str(p.get(layer.id_field) or f.get("id")),
                    geometry=f.get("geometry"),
                    name=p.get(layer.name_field),
                    category=str(p.get(layer.category_field)) if p.get(layer.category_field) is not None else None,
                    properties={k: v for k, v in p.items() if v is not None},
                )
            )
        version = None
        if raw.dataset == "school" and parsed:
            version = f"año {parsed[0].get('properties', {}).get('agno')}"
        return Batch(
            dataset=raw.dataset,
            url=raw.url,
            records=records,
            transformation=f"WFS 2.0 GetFeature {layer.type_name}, recorte por bbox de comunas activas; datos de {layer.owner}",
            version=version,
        )
