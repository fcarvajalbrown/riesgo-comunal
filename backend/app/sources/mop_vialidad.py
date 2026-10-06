import re
from typing import Any

import httpx

from app.sources import arcgis
from app.sources.base import Batch, FeatureRecord, IngestScope, RawPayload, SourceAdapter, SourceMeta

BASE = "https://rest-sit.mop.gob.cl/arcgis/rest/services/VIALIDAD"
ROADS = f"{BASE}/Red_Vial_Chile/MapServer/3"
BRIDGES = f"{BASE}/Puentes/MapServer/0"
ROAD_FIELDS = "OBJECTID,GlobalID,ROL,ROL_LABEL,NOMBRE_CAMINO,CLASIFICACION,CARPETA,CONCESIONADO"
BRIDGE_FIELDS = "OBJECTID,GlobalID,CODIGO_PUENTE,NOMBRE_PUENTE,NOMBRE_CAMINO,CODIGO_CAMINO,CAUCE_QUEB,LARGO,ANCHO_TOTAL,EST_PUENTE,TIPO_INFRA_WEB,SUPER_TIPO_WEB,AÑO_CONTRUCCION"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _key(p: dict[str, Any]) -> str:
    return str(p.get("GlobalID") or p.get("OBJECTID")).strip("{}").lower()


def road_class(classification: str | None) -> str | None:
    if not classification:
        return None
    base = re.sub(r"\s*\(.*\)\s*$", "", classification).strip()
    return "Camino Nacional" if base.startswith("Camino Nacional") else base


def road_record(feature: dict[str, Any]) -> FeatureRecord:
    p = feature.get("properties") or {}
    return FeatureRecord(
        external_id=_key(p),
        geometry=feature.get("geometry"),
        name=_text(p.get("NOMBRE_CAMINO")),
        category=_text(p.get("CLASIFICACION")),
        properties={
            "rol": _text(p.get("ROL_LABEL")) or _text(p.get("ROL")),
            "clase": road_class(_text(p.get("CLASIFICACION"))),
            "carpeta": _text(p.get("CARPETA")),
            "concesionado": _text(p.get("CONCESIONADO")),
        },
    )


def bridge_record(feature: dict[str, Any]) -> FeatureRecord:
    p = feature.get("properties") or {}
    year = p.get("AÑO_CONTRUCCION")
    return FeatureRecord(
        external_id=_key(p),
        geometry=feature.get("geometry"),
        name=_text(p.get("NOMBRE_PUENTE")),
        category=_text(p.get("TIPO_INFRA_WEB")),
        properties={
            "codigo": _text(p.get("CODIGO_PUENTE")),
            "camino": _text(p.get("NOMBRE_CAMINO")),
            "rol_camino": _text(p.get("CODIGO_CAMINO")),
            "cauce": _text(p.get("CAUCE_QUEB")),
            "largo_m": p.get("LARGO"),
            "ancho_m": p.get("ANCHO_TOTAL"),
            "estado": _text(p.get("EST_PUENTE")),
            "superestructura": _text(p.get("SUPER_TIPO_WEB")),
            "anio_construccion": int(year) if isinstance(year, (int, float)) and year > 0 else None,
        },
    )


class MopVialidadAdapter(SourceAdapter):
    meta = SourceMeta(
        key="mop_vialidad",
        name="MOP Vialidad: red vial nacional y puentes",
        organization="Dirección de Vialidad, Ministerio de Obras Públicas",
        url=f"{BASE}?f=json",
        license="Sin licencia declarada en los servicios ArcGIS del MOP; copyright Dirección de Vialidad, MOP",
        commercial_use="UNVERIFIED",
        cache_allowed="UNVERIFIED",
        authority="Oficial (caminos y puentes bajo tuición de Vialidad)",
        attribution="Fuente: Dirección de Vialidad, MOP",
        interval_minutes=10080,
    )

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        if not scope.bboxes:
            return []
        roads = arcgis.query_esri_by_ids(client, ROADS, scope, ROAD_FIELDS, max_offset=0.00002)
        bridges = arcgis.query_esri_by_ids(client, BRIDGES, scope, BRIDGE_FIELDS)
        return [
            RawPayload(dataset="road_segment", url=ROADS, body=roads, options={"scoped": True}),
            RawPayload(dataset="bridge", url=BRIDGES, body=bridges, options={"scoped": True}),
        ]

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        if raw.dataset == "road_segment":
            records = [road_record(f) for f in parsed]
            transformation = "Red_Vial_Chile capa 1:1.128, consulta por recorte y luego por OBJECTID; outSR=4326, geometría simplificada a ~2 m"
        else:
            records = [bridge_record(f) for f in parsed]
            transformation = "Inventario de puentes, viaductos y pasos superiores; consulta por recorte y luego por OBJECTID; outSR=4326"
        return Batch(dataset=raw.dataset, url=raw.url, records=records, transformation=transformation)
