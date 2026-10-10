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

## Audience of the Maule public site

Read this before any layout, copy or styling change to the static site (`tools/static-site/`). Every design decision is checked against these readers, not against a generic web user.

Sourced facts:

| Fact | Value | Source |
|---|---|---|
| Maule population | 1,123,008 | Censo 2024 (INE), via BCN |
| Average years of schooling, ages 18+ | 11.1 years, second lowest in Chile after Ñuble (11.0) | Censo 2024, reported by CNN Chile |
| Illiteracy, ages 15+ | 6.2% in Maule, highest region, against 3.1% nationally | CASEN 2015 regional fiche |
| Older population, Curepto | 33.5% of residents are older people, among the highest shares in Chile | UDD, from INE 2024 projections |
| Older population, Talca | 20.4% aged 60+ | INE 2024 projection |
| Mobile-only internet | 25% of Chilean households connect only through a mobile phone, concentrated in rural areas | SUBTEL XII Encuesta de Acceso y Usos de Internet (2025) |
| Fixed fibre coverage | Fibre plan reaches 21 of 30 Maule comunas | SUBTEL |

Not found, do not fill in: the Censo 2024 rural share of Maule and its share of people aged 65+.

What follows for design:

- Many readers are older, with lower schooling and a real share with reading difficulty: plain Spanish, short sentences, no technical codes or English, one idea per line.
- Large body text and touch targets, high contrast (WCAG AA at minimum), level shown by word and colour, never colour alone.
- Phone first: assume a small screen on a mobile connection, so the page stays light and the most urgent item is first on a narrow screen.
- The official alert and our own analysis of the same hazard sit side by side (stacked, official first, on a phone), each alert shown once.

## Layout research: map placement and type size

Twelve web searches on how public hazard sites place the map and size their text. No published study compares a sticky side map against a map below the content.

- VicEmergency (Victoria) and Hazards Near Me (NSW) show warnings as a map, a list, or both, with a toggle ([VicEmergency](https://support.emergency.vic.gov.au/hc/en-gb/articles/218578948-What-are-the-features-of-the-VicEmergency-website), [NSW Digital](https://www.digital.nsw.gov.au/delivery/government-technology-platforms/products/hazards-ecosystem/hazardwatch-and-hazards-near-me)).
- Met Office marine warnings put a clickable map with the detail panel beside it ([Met Office](https://weather.metoffice.gov.uk/guides/coast-and-sea/index)); Meteoalarm colours a map and links to per-country lists.
- The SBB design system puts the map beside the content on desktop and sticky above it on mobile, with the content scrolling over it ([SBB](https://digital.sbb.ch/en/design-system/lyne/components/map-container/)).
- The GOV.UK Check for flooding service was built mobile first because over 70% of its users are on a phone ([go-live briefing, Oct 2021](https://kingstonseymourparish.gov.uk/wp-content/uploads/Check-for-flooding-go-live-briefing-Oct-2021.pdf)).
- Australian Warning System: built from research with more than 14,000 people; a design agency's testing with older Canberrans led to simplifying and standardising ([cre8ive](https://cre8ive.com.au/node/91), vendor account).
- Nielsen Norman Group, mobile store-finder study (Harley, 19 January 2014): "the default view should be the list layout", with a toggle to a map as good practice, because lists are denser and faster to choose from; maps low on a phone screen catch the thumb, so people pan the map when they meant to scroll, fixed with side gutters and a link to hide the map; on mobile websites such maps "can safely be omitted" ([NN/g](https://www.nngroup.com/articles/mobile-maps-locations/)). The study's participant count is not stated in the article.
- Scottish Government Design System: give users another way to get what a map shows, as alternative content ([gov.scot](https://designsystem.gov.scot/guidance/maps/building-accessible-maps)).
- Conclusion for this site: the hazard rows are the primary content and the map is secondary; the rows carry everything the map shows in words.
- Type size for older readers: a thesis found 16 pt (about 21 px) preferred by UK and Thai older adults ([Kamollimsakul](https://etheses.whiterose.ac.uk/id/eprint/9027/1/Thesis_Sorachai_Kamollimsakul_CS.pdf)); a US federal publication recommends 16 or 18 pt; an ACL tip sheet at least 14 pt ([ACL](https://ACL.gov/sites/default/files/nutrition/BasicTipsOnWebDesignForAnOlderAdultAudience.pdf)). Every source says to let the reader enlarge text, so sizes are in rem and never fixed in px.

## Not yet done

Mobile layout beyond basic responsiveness, keyboard navigation audit, screen-reader audit, print styles for the web view (the PDF covers printing).
