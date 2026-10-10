import * as maplibregl from "./maplibre-gl.js";

maplibregl.setWorkerUrl(new URL("./maplibre-gl-worker.js", import.meta.url).href);

const BASEMAP = "https://tiles.openfreemap.org/styles/positron";
const RAIN_TILES = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/IMERG_Precipitation_Rate_30min/default/default/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png";
const WILDFIRE = ["#fde68a", "#fdba74", "#fb923c", "#ea580c", "#9a3412"];

const STYLES = {
  comuna: [{ type: "line", paint: { "line-color": "#1a2b3d", "line-width": 2.5 } }],
  lluvia: [{ type: "raster", paint: { "raster-opacity": 0.5 } }],
  wildfire_hazard: [
    {
      type: "fill",
      paint: {
        "fill-color": ["match", ["to-string", ["get", "clase"]], "1", WILDFIRE[0], "2", WILDFIRE[1], "3", WILDFIRE[2], "4", WILDFIRE[3], "5", WILDFIRE[4], "#cccccc"],
        "fill-opacity": 0.3,
      },
    },
  ],
  dmc_warning: [
    { type: "fill", paint: { "fill-color": ["match", ["get", "level"], "Alarma", "#b91c1c", "Alerta", "#ea580c", "#eab308"], "fill-opacity": 0.1 } },
    { type: "line", paint: { "line-color": "#a16207", "line-width": 1.5, "line-dasharray": [3, 2] } },
  ],
  tsunami_evacuation_area: [
    { type: "fill", paint: { "fill-color": "#2563eb", "fill-opacity": 0.28 } },
    { type: "line", paint: { "line-color": "#1d4ed8", "line-width": 1.2, "line-dasharray": [2, 1] } },
  ],
  tsunami_meeting_point: [
    { type: "circle", paint: { "circle-color": "#059669", "circle-radius": 6, "circle-stroke-color": "#ffffff", "circle-stroke-width": 1.5 } },
  ],
  viento: [
    {
      type: "symbol",
      layout: {
        "icon-image": "flecha",
        "icon-size": ["interpolate", ["linear"], ["get", "speed"], 0, 0.6, 60, 1.3],
        "icon-rotate": ["+", ["get", "dir"], 180],
        "icon-rotation-alignment": "map",
        "icon-allow-overlap": false,
        "text-field": ["concat", ["to-string", ["round", ["get", "speed"]]], " km/h"],
        "text-size": 11,
        "text-offset": [0, 1.6],
        "text-allow-overlap": false,
      },
      paint: { "icon-color": "#0f172a", "text-color": "#0f172a", "text-halo-color": "#ffffff", "text-halo-width": 1.5 },
    },
  ],
};

const ORDER = ["wildfire_hazard", "dmc_warning", "tsunami_evacuation_area", "lluvia", "tsunami_meeting_point", "viento", "comuna"];

function text(tag, value) {
  const node = document.createElement(tag);
  node.textContent = value;
  return node;
}

function chileTime(value) {
  return value ? new Date(value).toLocaleString("es-CL", { timeZone: "America/Santiago", dateStyle: "short", timeStyle: "short" }) : "sin término indicado";
}

function describe(key, props) {
  const box = document.createElement("div");
  box.className = "popup";
  if (key === "tsunami_meeting_point") {
    box.append(text("strong", "Punto de encuentro por tsunami"), text("p", props.direccion || props.name || ""), text("span", "Fuente: SENAPRED"));
  } else if (key === "tsunami_evacuation_area") {
    box.append(text("strong", "Área de evacuación por tsunami"), text("p", props.sector || props.name || ""), text("span", "Ante un tsunami, salga de esta zona hacia un punto de encuentro."));
  } else if (key === "wildfire_hazard") {
    box.append(text("strong", `Recurrencia de incendios forestales: ${props.category || props.clase || ""}`), text("span", "Densidad de incendios 2020-2024, SENAPRED con datos de CONAF"));
  } else if (key === "dmc_warning") {
    box.append(text("strong", props.level || "Aviso meteorológico"), text("p", props.title || ""), text("span", `Hasta: ${chileTime(props.ends_at)}`));
    if (props.source_url) {
      const link = text("a", "Ver el anuncio oficial");
      link.href = props.source_url;
      link.rel = "noreferrer";
      box.append(document.createElement("br"), link);
    }
  } else if (key === "viento") {
    box.append(text("strong", `Viento: ${Math.round(props.speed)} km/h`), text("p", `Ráfagas de hasta ${Math.round(props.gust)} km/h`), text("span", "Modelo Open-Meteo, ahora"));
  }
  return box;
}

function arrowImage() {
  const size = 32;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#000";
  ctx.beginPath();
  ctx.moveTo(16, 2);
  ctx.lineTo(26, 16);
  ctx.lineTo(19, 16);
  ctx.lineTo(19, 30);
  ctx.lineTo(13, 30);
  ctx.lineTo(13, 16);
  ctx.lineTo(6, 16);
  ctx.closePath();
  ctx.fill();
  return ctx.getImageData(0, 0, size, size);
}

function beforeId(map, key) {
  for (const later of ORDER.slice(ORDER.indexOf(key) + 1)) {
    if (map.getLayer(`${later}-0`)) return `${later}-0`;
  }
  return undefined;
}

async function show(map, urls, key, visible) {
  if (visible && !map.getSource(key)) {
    if (key === "lluvia") {
      map.addSource(key, { type: "raster", tiles: [RAIN_TILES], tileSize: 256, maxzoom: 6, attribution: "Lluvia: NASA GIBS, GPM IMERG" });
    } else {
      const response = await fetch(urls[key]);
      if (!response.ok) return;
      map.addSource(key, { type: "geojson", data: await response.json() });
    }
    STYLES[key].forEach((style, i) => map.addLayer({ id: `${key}-${i}`, source: key, ...style }, beforeId(map, key)));
  }
  for (let i = 0; i < STYLES[key].length; i++) {
    if (map.getLayer(`${key}-${i}`)) map.setLayoutProperty(`${key}-${i}`, "visibility", visible ? "visible" : "none");
  }
}

function addPopups(map) {
  const clickable = ["tsunami_meeting_point", "viento", "dmc_warning", "tsunami_evacuation_area", "wildfire_hazard"];
  map.on("click", (event) => {
    const layers = clickable.map((key) => `${key}-0`).filter((id) => map.getLayer(id));
    const hit = map.queryRenderedFeatures(event.point, { layers })[0];
    if (!hit) return;
    new maplibregl.Popup({ maxWidth: "280px" }).setLngLat(event.lngLat).setDOMContent(describe(hit.layer.id.replace(/-0$/, ""), hit.properties)).addTo(map);
  });
  for (const key of clickable) {
    map.on("mouseenter", `${key}-0`, () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", `${key}-0`, () => (map.getCanvas().style.cursor = ""));
  }
}

function regionLayers(map, url) {
  map.addSource("region", { type: "geojson", data: url });
  map.addLayer({ id: "region-fill", type: "fill", source: "region", paint: { "fill-color": ["get", "color"], "fill-opacity": 0.72 } }, beforeId(map, "wildfire_hazard"));
  map.addLayer({ id: "region-line", type: "line", source: "region", paint: { "line-color": "#ffffff", "line-width": 1.2 } }, beforeId(map, "wildfire_hazard"));
  const hover = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
  map.on("mousemove", "region-fill", (event) => {
    const props = event.features[0].properties;
    const box = document.createElement("div");
    box.append(text("strong", props.name), document.createElement("br"), `Situación: ${props.label}. Toque para ver la comuna.`);
    map.getCanvas().style.cursor = "pointer";
    hover.setLngLat(event.lngLat).setDOMContent(box).addTo(map);
  });
  map.on("mouseleave", "region-fill", () => {
    map.getCanvas().style.cursor = "";
    hover.remove();
  });
  map.on("click", "region-fill", (event) => {
    const others = map.queryRenderedFeatures(event.point, { layers: ["tsunami_meeting_point-0", "viento-0"].filter((id) => map.getLayer(id)) });
    if (!others.length) window.location.href = `${event.features[0].properties.slug}/index.html`;
  });
}

for (const element of document.querySelectorAll("[data-map]")) {
  const urls = { lluvia: null, viento: element.dataset.wind };
  for (const key of ["comuna", "wildfire_hazard", "dmc_warning", "tsunami_evacuation_area", "tsunami_meeting_point"]) {
    if (element.dataset.layers) urls[key] = `${element.dataset.layers}${key}.json`;
  }
  const map = new maplibregl.Map({
    container: element,
    style: BASEMAP,
    bounds: JSON.parse(element.dataset.bbox),
    fitBoundsOptions: { padding: element.dataset.region ? 8 : 24 },
    attributionControl: { compact: true },
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
  map.on("error", () => element.classList.add("map-error"));
  map.on("load", async () => {
    map.addImage("flecha", arrowImage(), { sdf: true });
    if (element.dataset.layers && !element.dataset.region) await show(map, urls, "comuna", true);
    for (const box of document.querySelectorAll("[data-layer]")) {
      if (box.checked) await show(map, urls, box.dataset.layer, true);
      box.addEventListener("change", () => show(map, urls, box.dataset.layer, box.checked));
    }
    if (element.dataset.region) regionLayers(map, element.dataset.region);
    addPopups(map);
  });
}
