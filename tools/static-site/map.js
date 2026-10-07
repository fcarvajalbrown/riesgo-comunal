import * as maplibregl from "./maplibre-gl.js";

maplibregl.setWorkerUrl(new URL("./maplibre-gl-worker.js", import.meta.url).href);

const BASEMAP = "https://tiles.openfreemap.org/styles/positron";
const WILDFIRE = ["#fde68a", "#fdba74", "#fb923c", "#ea580c", "#9a3412"];

const STYLES = {
  comuna: [{ type: "line", paint: { "line-color": "#1f4e79", "line-width": 2.5 } }],
  tsunami_evacuation_area: [
    { type: "fill", paint: { "fill-color": "#2563eb", "fill-opacity": 0.28 } },
    { type: "line", paint: { "line-color": "#1d4ed8", "line-width": 1.2, "line-dasharray": [2, 1] } },
  ],
  tsunami_meeting_point: [
    { type: "circle", paint: { "circle-color": "#059669", "circle-radius": 5.5, "circle-stroke-color": "#ffffff", "circle-stroke-width": 1.5 } },
  ],
  wildfire_hazard: [
    {
      type: "fill",
      paint: {
        "fill-color": ["match", ["to-string", ["get", "clase"]], "1", WILDFIRE[0], "2", WILDFIRE[1], "3", WILDFIRE[2], "4", WILDFIRE[3], "5", WILDFIRE[4], "#cccccc"],
        "fill-opacity": 0.55,
      },
    },
  ],
  dmc_warning: [
    { type: "fill", paint: { "fill-color": ["match", ["get", "level"], "Alarma", "#b91c1c", "Alerta", "#ea580c", "#eab308"], "fill-opacity": 0.22 } },
    { type: "line", paint: { "line-color": "#a16207", "line-width": 1.5, "line-dasharray": [3, 2] } },
  ],
};

function layerIds(key) {
  return STYLES[key].map((_, i) => `${key}-${i}`);
}

async function show(map, base, key, visible) {
  if (visible && !map.getSource(key)) {
    const response = await fetch(`${base}${key}.json`);
    if (!response.ok) return;
    map.addSource(key, { type: "geojson", data: await response.json() });
    const before = key !== "comuna" && map.getLayer("comuna-0") ? "comuna-0" : undefined;
    STYLES[key].forEach((style, i) => map.addLayer({ id: `${key}-${i}`, source: key, ...style }, before));
  }
  for (const id of layerIds(key)) {
    if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
  }
}

for (const element of document.querySelectorAll("[data-map]")) {
  const base = element.dataset.layers;
  const map = new maplibregl.Map({
    container: element,
    style: BASEMAP,
    bounds: JSON.parse(element.dataset.bbox),
    fitBoundsOptions: { padding: 24 },
    attributionControl: { compact: true },
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
  map.on("error", () => element.classList.add("map-error"));
  map.on("load", async () => {
    await show(map, base, "comuna", true);
    for (const box of document.querySelectorAll("[data-layer]")) {
      if (box.checked) await show(map, base, box.dataset.layer, true);
      box.addEventListener("change", () => show(map, base, box.dataset.layer, box.checked));
    }
  });
}
