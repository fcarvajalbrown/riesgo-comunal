from app.hazards.active_fire import ActiveFireModule
from app.hazards.air_quality import AirQualityModule
from app.hazards.base import HazardModule
from app.hazards.earthquake import EarthquakeModule
from app.hazards.flood import FloodModule
from app.hazards.international_alert import InternationalAlertModule
from app.hazards.meteo import MeteoModule
from app.hazards.river_flood import RiverFloodModule
from app.hazards.sea_level import SeaLevelModule
from app.hazards.senapred_alert import SenapredAlertModule
from app.hazards.tsunami import TsunamiModule
from app.hazards.weather_forecast import WeatherForecastModule
from app.hazards.wildfire import WildfireModule

MODULES: dict[str, HazardModule] = {
    module.key: module
    for module in (WildfireModule(), ActiveFireModule(), TsunamiModule(), SeaLevelModule(), FloodModule(), RiverFloodModule(), AirQualityModule(), EarthquakeModule(), MeteoModule(), SenapredAlertModule(), InternationalAlertModule(), WeatherForecastModule())
}


def enabled_modules(config: dict) -> list[HazardModule]:
    hazards = config.get("hazards", {})
    return [module for key, module in MODULES.items() if hazards.get(key, {}).get("enabled", True)]
