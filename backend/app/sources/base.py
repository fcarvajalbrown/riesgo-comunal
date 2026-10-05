from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx


@dataclass(frozen=True)
class SourceMeta:
    key: str
    name: str
    organization: str
    url: str
    license: str
    commercial_use: str
    cache_allowed: str
    authority: str
    attribution: str
    interval_minutes: int
    requires: tuple[str, ...] = ()


@dataclass
class FeatureRecord:
    external_id: str
    geometry: dict[str, Any]
    name: str | None = None
    category: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    data_class: str = "official"
    source_updated_at: datetime | None = None


@dataclass
class ObservationRecord:
    station_external_id: str
    station_name: str | None
    parameter: str
    parameter_name: str | None
    value: float | None
    unit: str | None
    observed_at: datetime
    validation_status: str
    lon: float | None
    lat: float | None


@dataclass
class EventRecord:
    external_id: str
    hazard: str
    occurred_at: datetime
    lon: float
    lat: float
    magnitude: float | None = None
    depth_km: float | None = None
    place: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class IndexRecord:
    index_key: str
    cut_code: str
    year: int | None
    value: float | None
    level: str | None
    components: dict[str, Any] = field(default_factory=dict)


Record = FeatureRecord | ObservationRecord | EventRecord | IndexRecord


@dataclass
class RawPayload:
    dataset: str
    url: str
    body: Any
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class Batch:
    dataset: str
    url: str
    records: list[Record]
    source_time: datetime | None = None
    transformation: str = ""
    version: str | None = None
    warnings: list[str] = field(default_factory=list)
    scoped: bool = False
    replace: bool = False


@dataclass(frozen=True)
class IngestScope:
    bboxes: tuple[tuple[float, float, float, float], ...] = ()


class SourceError(Exception):
    pass


class SourceAdapter(ABC):
    meta: SourceMeta

    def missing_requirements(self, settings: Any) -> list[str]:
        return [name for name in self.meta.requires if not getattr(settings, name, None)]

    @abstractmethod
    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]: ...

    def parse(self, raw: RawPayload) -> Any:
        return raw.body

    @abstractmethod
    def normalize(self, raw: RawPayload, parsed: Any) -> Batch: ...

    def validate(self, batch: Batch) -> Batch:
        kept: list[Record] = []
        for record in batch.records:
            problem = self.problem(record)
            if problem:
                batch.warnings.append(problem)
            else:
                kept.append(record)
        batch.records = kept
        return batch

    def problem(self, record: Record) -> str | None:
        if isinstance(record, FeatureRecord) and not record.geometry:
            return f"{record.external_id}: sin geometria"
        if isinstance(record, (ObservationRecord, EventRecord)):
            lat = record.lat
            lon = record.lon
            if lat is not None and not -90 <= lat <= 90 or lon is not None and not -180 <= lon <= 180:
                return f"coordenadas fuera de rango ({lat}, {lon})"
        return None

    def run(self, client: httpx.Client, scope: IngestScope) -> list[Batch]:
        batches = []
        for raw in self.fetch(client, scope):
            batch = self.validate(self.normalize(raw, self.parse(raw)))
            batch.scoped = bool(raw.options.get("scoped"))
            batch.replace = "scoped" in raw.options
            batches.append(batch)
        return batches
