# Data licensing and usage

This is a record of what each source's own terms say and what that means for a product sold to municipalities. It is not legal advice. Before the first commercial contract, the open items below must be reviewed by a qualified lawyer and, where marked, confirmed in writing with the data owner.

## Rules the platform enforces regardless of source

1. Every record keeps its source, dataset, URL, source timestamp and ingestion timestamp (`provenance` table). Attribution is shown wherever the data is shown, including reports and AI answers.
2. Raw payloads are stored only for sources where caching is allowed or not restricted. Each adapter declares `cache_allowed` and `commercial_use` in its metadata, and the admin "Fuentes" screen shows those flags.
3. A source whose terms forbid commercial use without permission is not ingested in a commercial deployment. Adapters for such sources ship disabled and an operator must turn them on knowingly.

## Per source

| Source | What the terms say | Commercial use | Redistribution / caching | Attribution text used | Open action |
|---|---|---|---|---|---|
| SENAPRED ArcGIS layers (DPA comunas, ICFSR, wildfire, tsunami, schools, health) | No licence on the ArcGIS items. Hazard maps are published to the public under Ley 21.364. | Not addressed. **UNVERIFIED.** | Not addressed | "Fuente: SENAPRED" plus layer name | Ask SENAPRED in writing whether commercial reuse and local caching of these layers is allowed, and under which licence. |
| SENAPRED Magallanes DGA overflow layer | "Uso institucional y público. Cítese la fuente original y a SENAPRED, Dirección Regional de Magallanes y de la Antártica Chilena" | Not addressed | Not addressed | As quoted | Same request as above if used. |
| SINCA (MMA) | No licence text found on the portal. SINCA states realtime data is unvalidated. | **UNVERIFIED** | **UNVERIFIED** | "Fuente: SINCA, Ministerio del Medio Ambiente. Datos en línea no validados." | Ask MMA for terms. |
| DGA Red Hidrométrica | Copyright "Dirección General de Aguas - Ministerio de Obras Públicas"; no licence | **UNVERIFIED** | **UNVERIFIED** | "Fuente: DGA, MOP" | Ask DGA for terms. |
| DMC climatología | "Todos los datos e información publicados en este Portal son de acceso y uso público"; must cite DMC | Public use stated; commercial not explicitly addressed | Not addressed | "Fuente: Dirección Meteorológica de Chile" | Confirm commercial use when registering the key. |
| CSN | Use, reproduction and distribution allowed for academic and outreach purposes with citation; any other purpose needs express written approval | **No, without written approval** | Same | n/a (not ingested) | Request written approval if earthquakes from CSN are wanted. |
| USGS | US Government work, public domain | Yes | Yes | "Fuente: USGS (complementario, no es la fuente oficial chilena)" | None |
| OpenFreeMap / OpenStreetMap basemap | Free, commercial use allowed; attribution required. OSM data is ODbL. | Yes | Self-hosting allowed | "OpenFreeMap © OpenMapTiles Data from OpenStreetMap" | None. For offline municipal installs, self-host tiles. |
| Open-Meteo | Free API for non-commercial use only; data CC BY 4.0 | Paid plan only | Per plan | n/a (not used) | Use only with a paid plan, if ever. |
| NASA FIRMS | NASA open data; free key | Yes | Yes | "Fuente: NASA FIRMS (detección satelital, no confirmación oficial)" | Not yet used. |

## Municipal data

Data uploaded by a municipality belongs to that municipality. It is stored only in that tenant's rows, never mixed into another tenant's queries, never used to answer another tenant's questions, and exported back in open formats on request. When an LLM provider outside the installation is configured, municipal text sent in prompts leaves the server; `docs/ai-rag.md` describes the local-model option for municipalities that cannot allow that.
