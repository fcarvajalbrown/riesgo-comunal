from app.sources.base import SourceAdapter
from app.sources.dga import DgaStationsAdapter
from app.sources.dmc import DmcAdapter
from app.sources.geoportal import GeoportalAdapter
from app.sources.senapred import SenapredAdapter
from app.sources.sinca import SincaAdapter
from app.sources.usgs import UsgsAdapter

ADAPTERS: dict[str, type[SourceAdapter]] = {
    cls.meta.key: cls
    for cls in (SenapredAdapter, GeoportalAdapter, SincaAdapter, DgaStationsAdapter, UsgsAdapter, DmcAdapter)
}


def get_adapter(key: str, **options) -> SourceAdapter:
    if key not in ADAPTERS:
        raise KeyError(f"fuente desconocida: {key}")
    return ADAPTERS[key](**options)
