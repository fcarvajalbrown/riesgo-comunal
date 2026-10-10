from app.sources.base import SourceAdapter
from app.sources.dga import DgaStationsAdapter
from app.sources.dmc import DmcAdapter
from app.sources.dmc_cap import DmcCapAdapter
from app.sources.emsc import EmscAdapter
from app.sources.geoportal import GeoportalAdapter
from app.sources.ine_census import IneCensusAdapter
from app.sources.inpe_queimadas import InpeQueimadasAdapter
from app.sources.ioc_sea_level import IocSeaLevelAdapter
from app.sources.international_alerts import GdacsAdapter, PtwcAdapter
from app.sources.mop_vialidad import MopVialidadAdapter
from app.sources.nasa_firms import NasaFirmsAdapter
from app.sources.open_meteo import OpenMeteoAdapter
from app.sources.senapred import SenapredAdapter
from app.sources.senapred_alerts import SenapredAlertsAdapter
from app.sources.shoa_snam import ShoaSnamAdapter
from app.sources.sinca import SincaAdapter
from app.sources.usgs import UsgsAdapter

ADAPTERS: dict[str, type[SourceAdapter]] = {
    cls.meta.key: cls
    for cls in (SenapredAdapter, GeoportalAdapter, SincaAdapter, DgaStationsAdapter, UsgsAdapter, EmscAdapter, InpeQueimadasAdapter, NasaFirmsAdapter, IocSeaLevelAdapter, DmcAdapter, DmcCapAdapter, SenapredAlertsAdapter, IneCensusAdapter, MopVialidadAdapter, GdacsAdapter, PtwcAdapter, ShoaSnamAdapter, OpenMeteoAdapter)
}


def get_adapter(key: str, **options) -> SourceAdapter:
    if key not in ADAPTERS:
        raise KeyError(f"fuente desconocida: {key}")
    return ADAPTERS[key](**options)
