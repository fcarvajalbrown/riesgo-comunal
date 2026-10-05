import re
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import get_settings
from app.sources.base import (
    Batch,
    FeatureRecord,
    IngestScope,
    ObservationRecord,
    RawPayload,
    SourceAdapter,
    SourceError,
    SourceMeta,
)

URL = "https://climatologia.meteochile.gob.cl/application/servicios/getDatosRecientesRedEma"
NUMBER_UNIT = re.compile(r"^\s*([-+]?\d+(?:\.\d+)?)\s*(.*)$")
PARAMETERS = {
    "temperatura": "Temperatura del aire",
    "humedadRelativa": "Humedad relativa",
    "aguaCaida6Horas": "Precipitación 6 horas",
    "aguaCaida24Horas": "Precipitación 24 horas",
    "fuerzaDelVientoPromedio10Minutos": "Viento medio 10 minutos",
    "fuerzaDelViento10MinutosMax": "Ráfaga máxima 10 minutos",
    "presionNivelDelMar": "Presión a nivel del mar",
}


def split_value(raw: Any) -> tuple[float | None, str | None]:
    if raw is None:
        return None, None
    match = NUMBER_UNIT.match(str(raw))
    if not match:
        return None, None
    return float(match.group(1)), match.group(2).strip() or None


class DmcAdapter(SourceAdapter):
    meta = SourceMeta(
        key="dmc",
        name="DMC: red de estaciones meteorológicas automáticas (12 horas recientes)",
        organization="Dirección Meteorológica de Chile",
        url="https://climatologia.meteochile.gob.cl/application/index/menuTematicoJson",
        license="Portal: datos de acceso y uso público, citando a la Dirección Meteorológica de Chile",
        commercial_use="No abordado explícitamente",
        cache_allowed="No abordado",
        authority="Oficial",
        attribution="Fuente: Dirección Meteorológica de Chile",
        interval_minutes=30,
        requires=("dmc_user", "dmc_token"),
    )

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        settings = get_settings()
        response = client.get(URL, params={"usuario": settings.dmc_user, "token": settings.dmc_token})
        response.raise_for_status()
        body = response.json()
        if "datosEstaciones" not in body:
            raise SourceError(f"DMC rechazó la consulta: {body.get('mensaje') or str(body)[:200]}")
        return [RawPayload(dataset="dmc_station", url=URL, body=body), RawPayload(dataset="dmc_observation", url=URL, body=body)]

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        stations = parsed.get("datosEstaciones", [])
        if raw.dataset == "dmc_station":
            records = []
            for item in stations:
                s = item.get("estacion", {})
                records.append(
                    FeatureRecord(
                        external_id=str(s.get("codigoNacional")),
                        geometry={"type": "Point", "coordinates": [float(s["longitud"]), float(s["latitud"])]},
                        name=s.get("nombreEstacion"),
                        category="estacion_meteorologica",
                        properties={"codigo_omm": s.get("codigoOMM"), "codigo_oaci": s.get("codigoOACI"), "altura_m": s.get("altura")},
                    )
                )
            return Batch(dataset=raw.dataset, url=URL, records=records, transformation="Catálogo desde getDatosRecientesRedEma")

        records = []
        latest = None
        for item in stations:
            s = item.get("estacion", {})
            for d in item.get("datos", []):
                observed_at = datetime.strptime(d["momento"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
                if observed_at.minute != 0:
                    continue
                latest = max(latest, observed_at) if latest else observed_at
                for key, label in PARAMETERS.items():
                    value, unit = split_value(d.get(key))
                    if value is None:
                        continue
                    records.append(
                        ObservationRecord(
                            station_external_id=str(s.get("codigoNacional")),
                            station_name=s.get("nombreEstacion"),
                            parameter=key,
                            parameter_name=label,
                            value=value,
                            unit=unit,
                            observed_at=observed_at,
                            validation_status="preliminary",
                            lon=float(s["longitud"]),
                            lat=float(s["latitud"]),
                        )
                    )
        return Batch(
            dataset=raw.dataset,
            url=URL,
            records=records,
            source_time=latest,
            transformation="Se conservan registros horarios (minuto 00); valores y unidades separados del texto; hora UTC",
        )
