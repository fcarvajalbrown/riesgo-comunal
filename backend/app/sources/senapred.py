from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.sources import arcgis
from app.sources.base import (
    Batch,
    FeatureRecord,
    IndexRecord,
    IngestScope,
    RawPayload,
    SourceAdapter,
    SourceMeta,
)

BASE = "https://services5.arcgis.com/i7S5PSnIJAUcWvSE/ArcGIS/rest/services"


@dataclass(frozen=True)
class Layer:
    dataset: str
    path: str
    scoped: bool
    kind: str = "feature"
    page_size: int = 1000
    max_offset: float | None = None


LAYERS = (
    Layer("comuna_boundary", "DPA_COMUNAS_2023/FeatureServer/0", scoped=False, page_size=20, max_offset=0.00005),
    Layer("icfsr", "Factor_IC_FSR/FeatureServer/0", scoped=False, kind="index"),
    Layer("wildfire_hazard", "Amenaza_por_Incendio_Forestal_2024/FeatureServer/0", scoped=True),
    Layer("tsunami_evacuation_area", "Amenaza_por_Tsunami_2024/FeatureServer/3", scoped=True),
    Layer("tsunami_meeting_point", "Amenaza_por_Tsunami_2024/FeatureServer/0", scoped=True),
)


def _ms_to_dt(value: Any) -> datetime | None:
    if isinstance(value, (int, float)) and value > 0:
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    return None


def _first(props: dict[str, Any], *names: str) -> Any:
    lowered = {k.lower(): v for k, v in props.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value not in (None, ""):
            return value
    return None


class SenapredAdapter(SourceAdapter):
    meta = SourceMeta(
        key="senapred",
        name="SENAPRED: mapas de amenaza y capas base (ArcGIS)",
        organization="Servicio Nacional de Prevención y Respuesta ante Desastres (SENAPRED)",
        url=f"{BASE}?f=json",
        license="Sin licencia declarada en las capas ArcGIS; mapas de amenaza públicos según Ley 21.364",
        commercial_use="UNVERIFIED",
        cache_allowed="UNVERIFIED",
        authority="Oficial",
        attribution="Fuente: SENAPRED",
        interval_minutes=1440,
    )

    def __init__(self, layers: tuple[Layer, ...] = LAYERS):
        self.layers = layers

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        payloads = []
        for layer in self.layers:
            if layer.scoped and not scope.bboxes:
                continue
            url = f"{BASE}/{layer.path}"
            info = arcgis.layer_info(client, url)
            edited = _ms_to_dt((info.get("editingInfo") or {}).get("lastEditDate"))
            if layer.kind == "index":
                body: Any = arcgis.query_attributes(client, url)
            else:
                body = arcgis.query_geojson(
                    client, url, scope if layer.scoped else None, page_size=layer.page_size, max_offset=layer.max_offset
                )
            payloads.append(
                RawPayload(
                    dataset=layer.dataset,
                    url=url,
                    body=body,
                    options={"edited": edited, "layer_name": info.get("name"), "scoped": layer.scoped},
                )
            )
        return payloads

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        edited = raw.options.get("edited")
        handler = getattr(self, f"_normalize_{raw.dataset}", None)
        records = handler(parsed) if handler else self._normalize_generic(raw.dataset, parsed)
        for record in records:
            if isinstance(record, FeatureRecord):
                record.source_updated_at = edited
        return Batch(
            dataset=raw.dataset,
            url=raw.url,
            records=records,
            source_time=edited,
            transformation=f"ArcGIS query paginada, outSR=4326; capa '{raw.options.get('layer_name')}'",
        )

    def _normalize_comuna_boundary(self, features):
        records = []
        for f in features:
            p = f.get("properties") or {}
            records.append(
                FeatureRecord(
                    external_id=str(p.get("cut_com")),
                    geometry=f.get("geometry"),
                    name=p.get("comuna"),
                    category="comuna",
                    properties={
                        "region": p.get("region"),
                        "provincia": p.get("provincia"),
                        "cut_reg": p.get("cut_reg"),
                        "cut_prov": p.get("cut_prov"),
                        "superficie_km2": p.get("superficie"),
                    },
                )
            )
        return records

    def _normalize_icfsr(self, rows):
        records = []
        for p in rows:
            cut = _first(p, "cod_com1", "cod_com")
            if cut is None:
                continue
            year = next((v for k, v in p.items() if k.lower().startswith("a") and k.lower().endswith("aplic")), None)
            records.append(
                IndexRecord(
                    index_key="icfsr",
                    cut_code=str(cut).zfill(5),
                    year=int(year) if year else None,
                    value=p.get("icfsr"),
                    level=_normalize_level(p.get("nivel")),
                    components={
                        "ic_ot": p.get("ic_ot"),
                        "ic_cc": p.get("ic_cc"),
                        "ic_soc": p.get("ic_soc"),
                        "ic_gob": p.get("ic_gob"),
                        "comuna": p.get("nom_com_1"),
                        "region": p.get("nom_reg"),
                    },
                )
            )
        return records

    def _normalize_wildfire_hazard(self, features):
        records = []
        for f in features:
            p = f.get("properties") or {}
            records.append(
                FeatureRecord(
                    external_id=str(p.get("objectid") or f.get("id")),
                    geometry=f.get("geometry"),
                    name=f"Recurrencia {p.get('recurrencia')}",
                    category=str(p.get("recurrencia")),
                    properties={"clase": p.get("gridcode"), "recurrencia": p.get("recurrencia")},
                )
            )
        return records

    def _normalize_generic(self, dataset, features):
        records = []
        for f in features:
            p = f.get("properties") or {}
            external_id = _first(p, "objectid", "fid", "objectid_1") or f.get("id")
            name = _first(p, "nombre", "nombre_pe", "nom_establ", "nombre_est", "name", "sector", "nom_rbd")
            category = _first(p, "tipo", "tipo_estab", "categoria", "dependencia", "nivel")
            records.append(
                FeatureRecord(
                    external_id=str(external_id),
                    geometry=f.get("geometry"),
                    name=str(name) if name is not None else None,
                    category=str(category) if category is not None else None,
                    properties={k: v for k, v in p.items() if not k.lower().startswith("shape")},
                )
            )
        return records


def _normalize_level(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    for target in ("MINIMO", "BAJO", "MODERADO", "ALTO"):
        if text.replace("Í", "I").startswith(target):
            return target
    return text
