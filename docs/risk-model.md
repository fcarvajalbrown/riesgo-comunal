# Risk model

## What this is and what it is not

The platform's risk levels are **derived** classifications computed by this software from official and municipal data, with rules that are written down here and configurable per comuna. They are **not** official government assessments, they are **not** SENAPRED alerts, and the absence of a high level does **not** mean the absence of danger. Every screen, report and AI answer that shows a level labels it "Cálculo de la plataforma".

The conceptual frame follows the common disaster-risk vocabulary (UNDRR): risk arises when a **hazard** meets **exposure** (people, assets) with some **vulnerability**. The platform does not claim to quantify risk scientifically. It applies transparent rules to the evidence it has and says which evidence is missing.

## Levels

| Level | Colour | Icon text | Meaning in the platform |
|---|---|---|---|
| `SIN_DATOS` | grey | "Sin datos" | Not enough data to classify. Never shown as "low". |
| `BAJO` | green | "Bajo" | Rules found evidence only at the lowest classes. |
| `MODERADO` | yellow | "Moderado" | |
| `ALTO` | orange | "Alto" | |
| `CRITICO` | red | "Crítico" | |
| `INFORMATIVO` | blue | "Informativo" | Situational information with no risk classification (e.g. recent earthquakes). |

Colour is never the only carrier: each level also has its text label.

## Data classes

| Class | Label in UI | Example |
|---|---|---|
| `official` | Oficial | SENAPRED wildfire hazard class, ICFSR |
| `observed` | Observado | SINCA hourly MP2.5 (also tagged "no validado") |
| `forecast` | Pronóstico | DMC forecast (when configured) |
| `official_warning` | Alerta oficial | SENAPRED alert from an authorised feed or entered with its source URL |
| `historical` | Histórico | USGS earthquakes, municipal past incidents |
| `municipal` | Municipal | uploaded assets, flood points |
| `derived` | Cálculo de la plataforma | every level produced by this engine |
| `estimated` | Estimado | a value inferred from incomplete data (for example interpolated between stations); no source in the MVP is classified this way |
| `modelled` | Modelado | numerical model output that is not a forecast issued by the authority (for example raw WRF fields); no source in the MVP is classified this way |

An adapter only assigns `estimated` or `modelled` when the source's own documentation says the data is an estimate or model output. Official hazard maps keep `official` even when the authority built them from models, because the authority publishes them as its official product.

## Hazard rules in the MVP

Thresholds in `default_thresholds` can be changed per comuna by a municipal admin; changes are audited and the report shows the thresholds in force.

### Incendio forestal (wildfire) (module `wildfire`)

- Evidence: SENAPRED "Amenaza por Incendio Forestal 2024", density of fires 2020-2024, classes 1-5 (Muy baja ... Muy alta). Official.
- Area of a class inside the comuna or sector is computed in PostGIS (`ST_Area(geography)`).
- Rule: the level is driven by the share of area in the two highest classes.
  - `share(class>=4) >= high_share_critical` (default 0.30) → `CRITICO`
  - `share(class>=4) >= high_share_alto` (default 0.10) → `ALTO`
  - `share(class>=3) >= mid_share_moderado` (default 0.10) → `MODERADO`
  - any coverage → `BAJO`
  - no polygons intersecting → `SIN_DATOS`
- Exposure reported, not mixed into the level: schools, health centres and municipal assets inside class 4-5 polygons.

### Tsunami (module `tsunami`)

- Evidence: SENAPRED "Amenaza por Tsunami 2024", layer "Área a Evacuar" (polygons) and "Punto de Encuentro". Official.
- Rule: if the comuna or sector intersects an evacuation area → `ALTO` (configurable `level_if_in_evacuation_area`); otherwise `BAJO` if the comuna has evacuation data elsewhere, `SIN_DATOS` if the comuna has no tsunami layer at all (inland comunas show the module only if an admin enables it).
- Exposure: assets and facilities inside evacuation areas; nearest meeting point for each.

### Calidad del aire (air quality) (module `air_quality`)

- Evidence: SINCA hourly MP2.5 at stations inside the comuna or within `station_radius_km` (default 5 km). **Unvalidated** observations.
- Reference values, quoted from D.S. 12/2011 (MMA) for 24-hour MP2.5: norm 50 µg/m³; alerta 80-109; preemergencia 110-169; emergencia ≥170.
- Rule on the mean of the last available 24 hourly values (requires at least `min_hours` = 18):
  - mean ≥ 170 → `CRITICO`; ≥ 110 → `ALTO`; ≥ 80 → `MODERADO` (labelled "sobre umbral de alerta"); else `BAJO`.
  - fewer than `min_hours` valid hours → `SIN_DATOS`.
- The explanation always states that critical episodes are declared by the competent authority and that this calculation is not a declaration.

### Sismos (earthquakes) (module `earthquake`)

- Evidence: USGS events within `radius_km` (default 150 km) of the comuna in the last 72 h with magnitude ≥ `min_magnitude` (default 4.0). Historical/observed, complementary source.
- Level: always `INFORMATIVO`. The platform does not forecast earthquakes.
- PLANIFICAR shows counts per year and magnitude band since 2000 with the method and limitations.

### Inundación y anegamiento (flooding) (module `flood`)

- Evidence available today: municipal flood points and municipal incident records (uploaded), and nothing official for most comunas (DGA flood maps not machine-readable, see `data-sources.md`).
- Rule: count of municipal flood incidents in the last `years` (default 10) in the comuna or sector:
  - ≥ `incidents_alto` (default 5) → `ALTO`; ≥ `incidents_moderado` (default 2) → `MODERADO`; ≥ 1 → `BAJO`;
  - no municipal flood data uploaded → `SIN_DATOS` with the message "No hay registros municipales de inundación cargados".
- Labelled `historical` + `municipal` evidence, `derived` level.

### Condiciones meteorológicas (module `meteo`)

- **Official warnings**: DMC avisos, alertas and alarmas from the CAP feed whose geometry intersects the comuna. A bulletin in force sets the platform level by a fixed equivalence: Aviso = MODERADO, Alerta = ALTO, Alarma = CRITICO (`classify_dmc_warnings`). This equivalence is a platform rule for ordering the summary; the official status is the DMC bulletin itself, shown with its link. A bulletin whose onset is still in the future gives INFORMATIVO and is listed as "Próximo".
- **Observed rain** (when the DMC credential is configured): rain in the last 24 h at the nearest station above `rain_24h_moderado` / `rain_24h_alto` (defaults 30 / 60 mm). These defaults are **placeholders chosen for the MVP, not official thresholds**, and the UI says so until a municipality sets its own.
- The module level is the higher of the two.

### Alertas de SENAPRED (module `senapred_alert`)

- **Input**: SENAPRED alerts in force whose coverage overlaps the comuna's interior: those read automatically from senapred.cl/alertas (`senapred_alertas`), plus alerts a municipality enters by hand with SENAPRED as issuer. Alerts whose start is still in the future are not counted.
- **Rule** (`classify_senapred_alerts`): Alerta Temprana Preventiva = MODERADO, Alerta Amarilla = ALTO, Alerta Roja = CRITICO; the highest alert in force wins. An alert whose level the platform cannot recognise gives INFORMATIVO, and no alert gives BAJO. As with the DMC equivalence, this is a platform rule for ordering the summary; the official status is SENAPRED's declaration, linked from each evidence row.
- The explanation always says that the absence of a registered alert does not mean there is no danger, and that SENAPRED's site is the place to confirm.

## Population exposure (not a level)

Every spatial hazard module that lists exposed facilities also lists people, persons aged 60 or over, and private dwellings inside the hazard zone, from the INE Censo 2024 block base. Blocks partly inside a zone count in proportion to the share of their area inside it, which assumes people are spread evenly within each block. The figures are labelled **Estimado** with that note. In rural entities, which are large, the estimate is rough. Checked when added: for Lota's tsunami evacuation area the area-weighted estimate is 14,405 persons, counting a block only when its representative point is inside gives 14,646, and counting every block that touches the zone gives 20,776, so the estimate sits close to the first two and well below the upper bound. Exposure never changes a hazard level. Each sector also carries an estimated resident count computed the same way.

Roads and bridges come from MOP's Dirección de Vialidad: the exposure lists the bridges, viaducts and overpasses inside the zone, and the kilometres of national road network inside it with the route roles involved (for Lota's tsunami evacuation area, 10.6 km on routes 160 and O-850). Only roads and bridges under Vialidad are covered; urban streets, which municipalities and SERVIU manage, are not, and the exposure note says so.

## Comuna context (not a level)

SENAPRED's ICFSR (Índice Comunal de Factores Subyacentes del Riesgo) is shown as an official contextual index with its four components and the year of application. It is not merged into hazard levels.

## Sectors

If the municipality uploads sectors, levels are computed per sector. If not, the engine uses derived analysis cells (a regular ~1 km grid clipped to the comuna) labelled "Celda de análisis", never presented as municipal sectors.

## Testing

`backend/tests/test_risk_rules.py` covers every rule boundary above with fixed inputs (given evidence X, expect level Y), the `SIN_DATOS` paths, and that the explanation lists every factor used.
