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
| `branding.display_name`, `branding.primary_color` | header name and brand colour used across the interface (colour must be `#RRGGBB`) |
| `branding.logo_url` | set by uploading a PNG or JPEG logo (up to 1 MB) in "Configuración"; served publicly at `/api/public/<slug>/logo` |
| `hazards.<module>.enabled` | turn a hazard module on or off |
| `hazards.<module>.thresholds` | override any default threshold of that module (unknown keys are rejected) |
| `terminology` | the comuna's own words for the tab names (`tab_ahora` ... `tab_config`) and for `sector` / `sectores` (for example "Unidad vecinal"); unknown keys are rejected, 40 characters each |

Emergency contacts and municipal emergency personnel are uploaded as CSV under "Datos municipales" (see below) and appear in that screen and in the Emergencias report.

Hazard modules and their thresholds are listed in `risk-model.md`. Every change is audited.

## Municipal data

Uploaded under "Datos municipales":

| Kind | Formats | Required fields |
|---|---|---|
| Infrastructure and resources | CSV (lat/lon columns), GeoJSON, KML, KMZ, zipped Shapefile, GeoPackage | `nombre`, `categoria` (or a category chosen in the form) |
| Historical incidents | CSV, GeoJSON, KML, KMZ, zipped Shapefile, GeoPackage | `fecha`, `amenaza`; optional `sector`, `descripcion`, `afectados`, coordinates |
| Sectors | GeoJSON, KML, KMZ, zipped Shapefile, GeoPackage polygons | `nombre`; replaces the analysis cells |
| Raster layers | GeoTIFF with a declared CRS | optional title; stored as uploaded, previewed on the map warped to WGS84 (RGB for 3+ bands, colour ramp with value range for one band, no-data transparent) |
| Emergency contacts and personnel | CSV | `nombre`; optional `cargo`, `institucion`, `telefono`, `email`, `tipo` (`contacto` or `personal`) |
| Inspection records | CSV | `fecha`, `activo` (matched to an uploaded asset by name); optional `estado`, `observaciones`, `inspector` |
| Photos | JPEG, PNG, WebP (checked by file signature) | optional description and linked asset |
| Documents | PDF with text, TXT, MD | optional title |

Recognised categories include `albergue`, `punto critico inundacion` (feeds the flood module), `generador`, `estanque de agua`, `puente`, `sumidero`, `grifo`, `maquinaria`, `vehiculo municipal`, `ruta de evacuacion`; other values are stored as given. Shapefiles (zipped with their `.prj`) and GeoPackages are read with pyogrio (GDAL) and reprojected to WGS84 from any declared CRS, so UTM files work as exported; a file without a CRS is rejected with that reason.

## Adding a hazard module

Create a `HazardModule` subclass in `backend/app/hazards/` with `key`, `name`, `description`, `modes`, `default_thresholds` and `assess()`, put its pure classification in `rules.py` with tests, and register it in `hazards/registry.py`. Nothing else changes.

## Adding a data source

Create a `SourceAdapter` in `backend/app/sources/` with `meta`, `fetch()` and `normalize()`, and register it in `sources/registry.py`. The worker schedules it by `meta.interval_minutes`; the "Fuentes" screen shows it automatically.
