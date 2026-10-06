"use client";

import * as maplibregl from "maplibre-gl";
import type { Map as MlMap } from "maplibre-gl";
import { LEVEL_STYLE } from "@/lib/format";
import type { LayerInfo } from "@/lib/types";

maplibregl.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");

export const BASEMAP = "https://tiles.openfreemap.org/styles/positron";

export const POINT_COLORS: Record<string, string> = {
  school: "#2563eb",
  health_facility: "#dc2626",
  tsunami_meeting_point: "#059669",
  aq_station: "#7c3aed",
  dga_station: "#0891b2",
  earthquake: "#92400e",
  municipal_asset: "#0f766e",
  municipal_incident: "#b45309",
};

export const WILDFIRE_COLORS = ["#fde68a", "#fdba74", "#fb923c", "#ea580c", "#9a3412"];
export const DENSITY_COLORS = ["#f2f0f7", "#cbc9e2", "#9e9ac8", "#756bb1", "#54278f"];
export const WARNING_COLORS: Record<string, string> = { Alarma: "#b91c1c", Alerta: "#ea580c", Aviso: "#eab308" };

function levelExpression() {
  const entries = Object.entries(LEVEL_STYLE).flatMap(([level, style]) => [level, style.hex]);
  return ["match", ["get", "level"], ...entries, "#8a929c"] as unknown as maplibregl.ExpressionSpecification;
}

export function addLayerStyle(map: MlMap, key: string) {
  const source = `src-${key}`;
  const before = map.getLayer("lyr-comuna-line") ? "lyr-comuna-line" : undefined;
  if (key === "comuna") {
    map.addLayer({ id: "lyr-comuna-line", type: "line", source, paint: { "line-color": "#1f4e79", "line-width": 2.5 } });
    return;
  }
  if (key === "sectors") {
    map.addLayer({ id: "lyr-sectors-fill", type: "fill", source, paint: { "fill-color": levelExpression(), "fill-opacity": 0.32 } }, before);
    map.addLayer({ id: "lyr-sectors-line", type: "line", source, paint: { "line-color": "#ffffff", "line-width": 0.8 } }, before);
    return;
  }
  if (key === "wildfire_hazard") {
    map.addLayer(
      {
        id: "lyr-wildfire_hazard-fill",
        type: "fill",
        source,
        paint: {
          "fill-color": ["match", ["to-string", ["get", "clase"]], "1", WILDFIRE_COLORS[0], "2", WILDFIRE_COLORS[1], "3", WILDFIRE_COLORS[2], "4", WILDFIRE_COLORS[3], "5", WILDFIRE_COLORS[4], "#cccccc"],
          "fill-opacity": 0.55,
        },
      },
      before,
    );
    return;
  }
  if (key === "dmc_warning") {
    map.addLayer(
      {
        id: "lyr-dmc_warning-fill",
        type: "fill",
        source,
        paint: {
          "fill-color": ["match", ["get", "level"], "Alarma", WARNING_COLORS.Alarma, "Alerta", WARNING_COLORS.Alerta, WARNING_COLORS.Aviso],
          "fill-opacity": 0.22,
        },
      },
      before,
    );
    map.addLayer({ id: "lyr-dmc_warning-line", type: "line", source, paint: { "line-color": "#a16207", "line-width": 1.5, "line-dasharray": [3, 2] } }, before);
    return;
  }
  if (key === "census_block") {
    map.addLayer(
      {
        id: "lyr-census_block-fill",
        type: "fill",
        source,
        paint: {
          "fill-color": ["step", ["coalesce", ["get", "densidad"], 0], DENSITY_COLORS[0], 5, DENSITY_COLORS[1], 20, DENSITY_COLORS[2], 50, DENSITY_COLORS[3], 100, DENSITY_COLORS[4]],
          "fill-opacity": 0.6,
        },
      },
      before,
    );
    map.addLayer({ id: "lyr-census_block-line", type: "line", source, paint: { "line-color": "#ffffff", "line-width": 0.4 } }, before);
    return;
  }
  if (key === "tsunami_evacuation_area") {
    map.addLayer({ id: "lyr-tsunami_evacuation_area-fill", type: "fill", source, paint: { "fill-color": "#2563eb", "fill-opacity": 0.28 } }, before);
    map.addLayer({ id: "lyr-tsunami_evacuation_area-line", type: "line", source, paint: { "line-color": "#1d4ed8", "line-width": 1.2, "line-dasharray": [2, 1] } }, before);
    return;
  }
  const color = POINT_COLORS[key] ?? "#334155";
  if (key === "municipal_asset") {
    map.addLayer({ id: `lyr-${key}-fill`, type: "fill", source, filter: ["==", ["geometry-type"], "Polygon"], paint: { "fill-color": color, "fill-opacity": 0.3 } });
    map.addLayer({ id: `lyr-${key}-line`, type: "line", source, filter: ["==", ["geometry-type"], "LineString"], paint: { "line-color": color, "line-width": 2 } });
  }
  map.addLayer({
    id: `lyr-${key}-circle`,
    type: "circle",
    source,
    filter: ["==", ["geometry-type"], "Point"],
    paint: {
      "circle-color": color,
      "circle-radius": key === "earthquake" ? ["interpolate", ["linear"], ["coalesce", ["get", "magnitude"], 3], 2.5, 4, 6, 14] : 5.5,
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 1.5,
      "circle-opacity": key === "earthquake" ? 0.7 : 0.95,
    },
  });
}


export function LayerLegend({ layer }: { layer: LayerInfo }) {
  const swatches: { key: string; label: string; color: string; round?: boolean }[] =
    layer.key === "sectors"
      ? layer.legend.map((l) => ({ key: l.value, label: l.label, color: LEVEL_STYLE[l.value as keyof typeof LEVEL_STYLE]?.hex }))
      : layer.key === "wildfire_hazard"
        ? layer.legend.map((l) => ({ key: l.value, label: l.label, color: WILDFIRE_COLORS[Number(l.value) - 1] }))
        : layer.key === "dmc_warning"
          ? layer.legend.map((l) => ({ key: l.value, label: l.label, color: WARNING_COLORS[l.value] }))
          : layer.key === "census_block"
            ? layer.legend.map((l) => ({ key: l.value, label: l.label, color: DENSITY_COLORS[{ "0": 0, "5": 1, "20": 2, "50": 3, "100": 4 }[l.value] ?? 0] }))
            : layer.key === "tsunami_evacuation_area"
            ? [{ key: "area", label: "área a evacuar", color: "#2563eb" }]
            : POINT_COLORS[layer.key]
              ? [{ key: "point", label: "símbolo en el mapa", color: POINT_COLORS[layer.key], round: true }]
              : [];
  if (!swatches.length) return null;
  return (
    <span className="mt-1 flex flex-wrap gap-x-2 gap-y-1">
      {swatches.map((s) => (
        <span key={s.key} className="inline-flex items-center gap-1 text-[11px]">
          <span className={`h-2.5 w-2.5 ${s.round ? "rounded-full" : "rounded-sm"}`} style={{ background: s.color }} />
          {s.label}
        </span>
      ))}
    </span>
  );
}
