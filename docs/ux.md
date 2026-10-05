# UX

## Principles

1. Summary first, detail on demand: every assessment card shows level and one headline; "¿Por qué?", "Ver detalle" and "Datos técnicos" open progressively.
2. Every number answers "¿De dónde salió este dato?": a "Fuente" link on each evidence item opens the provenance dialog.
3. Every level shows its data class (Oficial, Observado, Pronóstico, Alerta oficial, Histórico, Municipal, Calculado por la plataforma). Derived levels always carry "No es una evaluación oficial".
4. DEMO records show "[DATOS DEMO]" wherever they appear, including reports and assistant answers.
5. Absence of an alert is never shown as "sin riesgo": AHORA always states that SENAPRED alerts are not received automatically and links to senapred.cl.
6. Spanish copy, plain words, times in Chile local time with UTC in parentheses.

## Screens

| Tab | Question it answers | Content |
|---|---|---|
| Ahora | ¿Qué está pasando? | alerts entered by the municipality, current assessments per hazard, exposure summary, map with air quality stations, recent earthquakes, schools and health facilities |
| Riesgo | ¿Qué zonas son vulnerables? | structural assessments, ranked sectors or analysis cells, map coloured by derived level |
| Planificar | Historia y prioridades | ICFSR, earthquakes per year, municipal incidents per year and by hazard, each with period, n, source, method and limitations |
| Asistente | Preguntas en lenguaje natural | audience selector (ejecutivo, técnico, vecino), example questions, answer with sources |
| Informes | Por rol | Alcalde, Emergencias, SECPLAN, Comunicaciones (draft), PDF download |
| Datos municipales | Cargar información | uploads of CSV, GeoJSON, KML, KMZ, PDF; list with status |
| Fuentes | Origen de los datos | source registry, status, last update, licence flags |
| Configuración | Umbrales y alertas | hazard modules, thresholds, official alert entry |

## Role defaults

| Role | Tabs, in order |
|---|---|
| Alcalde | Ahora, Riesgo, Planificar, Asistente, Informes, Fuentes |
| Emergencias | Ahora, Riesgo, Planificar, Asistente, Informes, Datos, Fuentes, Configuración |
| SECPLAN | Planificar, Riesgo, Ahora, Asistente, Informes, Datos, Fuentes |
| Comunicaciones | Informes, Ahora, Riesgo, Asistente, Fuentes |
| Viewer | Ahora, Riesgo, Planificar, Asistente, Fuentes |
| Admin | all tabs |

## Level colours

SIN_DATOS grey, INFORMATIVO blue, BAJO green, MODERADO yellow, ALTO orange, CRITICO red. Each level is also written out in text so colour is never the only signal.

## Map

MapLibre GL with the OpenFreeMap positron basemap. Layers per tab, toggled from a legend; clicking a feature shows its properties and source. The map never loads data from an external API other than the basemap tiles.

## Not yet done

Mobile layout beyond basic responsiveness, keyboard navigation audit, screen-reader audit, print styles for the web view (the PDF covers printing).
