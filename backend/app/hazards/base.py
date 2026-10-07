from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import Connection

LEVELS = ("SIN_DATOS", "INFORMATIVO", "BAJO", "MODERADO", "ALTO", "CRITICO")
LEVEL_RANK = {"SIN_DATOS": -1, "INFORMATIVO": 0, "BAJO": 1, "MODERADO": 2, "ALTO": 3, "CRITICO": 4}
LEVEL_LABEL = {
    "SIN_DATOS": "Sin datos suficientes",
    "INFORMATIVO": "Informativo",
    "BAJO": "Bajo",
    "MODERADO": "Moderado",
    "ALTO": "Alto",
    "CRITICO": "Crítico",
}
DATA_CLASS_LABEL = {
    "official": "Oficial",
    "observed": "Observado",
    "forecast": "Pronóstico",
    "official_warning": "Alerta oficial",
    "historical": "Histórico",
    "municipal": "Municipal",
    "derived": "Cálculo de la plataforma",
    "estimated": "Estimado",
    "modelled": "Modelado",
}
DERIVED_NOTICE = (
    "Nivel calculado por esta plataforma con reglas publicadas y configurables. "
    "No es una evaluación ni una alerta oficial. La ausencia de un nivel alto no significa ausencia de peligro."
)


@dataclass
class Evidence:
    label: str
    value: Any
    data_class: str
    source: str
    updated_at: datetime | None = None
    provenance_id: int | None = None
    note: str | None = None


@dataclass
class Exposure:
    category: str
    label: str
    count: float
    data_class: str
    source: str
    items: list[dict[str, Any]] = field(default_factory=list)
    note: str | None = None


@dataclass
class Assessment:
    hazard: str
    hazard_name: str
    level: str
    headline: str
    explanation: list[str]
    evidence: list[Evidence] = field(default_factory=list)
    exposure: list[Exposure] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    thresholds: dict[str, Any] = field(default_factory=dict)
    area_name: str | None = None
    uses_demo_data: bool = False
    rule_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["level_label"] = LEVEL_LABEL[self.level]
        data["data_class"] = "derived"
        data["data_class_label"] = DATA_CLASS_LABEL["derived"]
        data["notice"] = DERIVED_NOTICE
        if self.uses_demo_data:
            data["headline"] = f"[DATOS DEMO] {self.headline}"
            data["notice"] = "Este cálculo usa datos DEMO de ejemplo que no son reales. " + DERIVED_NOTICE
        for item in data["evidence"]:
            item["data_class_label"] = DATA_CLASS_LABEL.get(item["data_class"], item["data_class"])
        for item in data["exposure"]:
            item["data_class_label"] = DATA_CLASS_LABEL.get(item["data_class"], item["data_class"])
        return data


@dataclass
class Area:
    kind: str
    id: int
    name: str

    def geom_sql(self) -> str:
        if self.kind == "comuna":
            return "(select boundary from municipality where id = :area_id)"
        return "(select geom from sector where id = :area_id)"

    def params(self) -> dict[str, Any]:
        return {"area_id": self.id}


@dataclass
class HazardContext:
    conn: Connection
    municipality: dict[str, Any]
    thresholds: dict[str, Any]
    now: datetime
    detail: bool = True

    @property
    def municipality_id(self) -> int:
        return self.municipality["id"]


class HazardModule(ABC):
    key: str
    name: str
    description: str
    modes: tuple[str, ...] = ("riesgo",)
    spatial: bool = True
    default_thresholds: dict[str, Any] = {}
    layers: tuple[str, ...] = ()

    def thresholds(self, overrides: dict[str, Any] | None) -> dict[str, Any]:
        merged = dict(self.default_thresholds)
        for key, value in (overrides or {}).items():
            if key in merged:
                merged[key] = type(merged[key])(value)
        return merged

    @abstractmethod
    def assess(self, ctx: HazardContext, area: Area) -> Assessment: ...

    def assess_sectors(self, ctx: HazardContext, areas: list[Area]) -> list[Assessment]:
        return [self.assess(ctx, area) for area in areas]

    def describe(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "modes": list(self.modes),
            "spatial": self.spatial,
            "default_thresholds": self.default_thresholds,
            "layers": list(self.layers),
        }


def max_level(levels: list[str]) -> str:
    ranked = [lvl for lvl in levels if LEVEL_RANK[lvl] > 0]
    if ranked:
        return max(ranked, key=LEVEL_RANK.__getitem__)
    if "INFORMATIVO" in levels:
        return "INFORMATIVO"
    return "SIN_DATOS"
