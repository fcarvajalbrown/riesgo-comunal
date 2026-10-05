# Municipal customisation

Same codebase for every comuna; differences live in data and configuration.

## Onboarding a comuna

```bash
python -m app.cli create-tenant --cut <CUT> --slug <slug> [--name "<name>"]
python -m app.cli create-user --email <email> --role MUNICIPAL_ADMIN --tenant <slug>
```

The boundary comes from SENAPRED's DPA layer; the worker then pulls hazard and facility layers clipped to the new comuna on its next run. With Docker, the same happens through `TENANT_CUT` / `TENANT_SLUG` in `.env`.

## Configuration (`municipality.config`, edited in "Configuración")

| Key | Content |
|---|---|
| `branding.display_name`, `branding.primary_color`, `branding.logo_url` | header name and colour |
| `hazards.<module>.enabled` | turn a hazard module on or off |
| `hazards.<module>.thresholds` | override any default threshold of that module (unknown keys are rejected) |
| `terminology` | reserved for label overrides |
| `contacts` | reserved for emergency contacts |

Hazard modules and their thresholds are listed in `risk-model.md`. Every change is audited.

## Municipal data

Uploaded under "Datos municipales":

| Kind | Formats | Required fields |
|---|---|---|
| Infrastructure and resources | CSV (lat/lon columns), GeoJSON, KML, KMZ | `nombre`, `categoria` (or a category chosen in the form) |
| Historical incidents | CSV, GeoJSON, KML, KMZ | `fecha`, `amenaza`; optional `sector`, `descripcion`, `afectados`, coordinates |
| Sectors | GeoJSON, KML, KMZ polygons | `nombre`; replaces the analysis cells |
| Documents | PDF with text, TXT, MD | optional title |

Recognised categories include `albergue`, `punto critico inundacion` (feeds the flood module), `generador`, `estanque de agua`, `puente`, `sumidero`, `grifo`, `maquinaria`, `vehiculo municipal`, `ruta de evacuacion`; other values are stored as given. Shapefile and GeoPackage need GDAL and are planned.

## Adding a hazard module

Create a `HazardModule` subclass in `backend/app/hazards/` with `key`, `name`, `description`, `modes`, `default_thresholds` and `assess()`, put its pure classification in `rules.py` with tests, and register it in `hazards/registry.py`. Nothing else changes.

## Adding a data source

Create a `SourceAdapter` in `backend/app/sources/` with `meta`, `fetch()` and `normalize()`, and register it in `sources/registry.py`. The worker schedules it by `meta.interval_minutes`; the "Fuentes" screen shows it automatically.
