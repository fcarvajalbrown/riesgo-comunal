"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MlMap } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { DataClassBadge } from "@/components/Badges";
import { apiGet } from "@/lib/api";
import { DATA_CLASS_STYLE, LEVEL_STYLE, formatShortTime } from "@/lib/format";
import type { LayerInfo, Me } from "@/lib/types";

const BASEMAP = "https://tiles.openfreemap.org/styles/positron";
maplibregl.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");

const POINT_COLORS: Record<string, string> = {
  school: "#2563eb",
  health_facility: "#dc2626",
  tsunami_meeting_point: "#059669",
  aq_station: "#7c3aed",
  dga_station: "#0891b2",
  earthquake: "#92400e",
  municipal_asset: "#0f766e",
  municipal_incident: "#b45309",
};
type FeatureCollectionLike = { type: "FeatureCollection"; features: unknown[] };

const WILDFIRE_COLORS = ["#fde68a", "#fdba74", "#fb923c", "#ea580c", "#9a3412"];
const WARNING_COLORS: Record<string, string> = { Alarma: "#b91c1c", Alerta: "#ea580c", Aviso: "#eab308" };

export interface MapFocus {
  lon: number;
  lat: number;
  zoom?: number;
  label?: string;
}

function levelExpression() {
  const entries = Object.entries(LEVEL_STYLE).flatMap(([level, style]) => [level, style.hex]);
  return ["match", ["get", "level"], ...entries, "#8a929c"] as unknown as maplibregl.ExpressionSpecification;
}

function addLayerStyle(map: MlMap, key: string) {
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

function popupHtml(layer: LayerInfo | undefined, props: Record<string, unknown>): string {
  const esc = (v: unknown) => String(v ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string);
  const lines: string[] = [];
  const title = props.name ?? props.place ?? props.hazard ?? layer?.name ?? "";
  lines.push(`<div style="font-weight:600;font-size:14px;margin-bottom:4px">${esc(title)}</div>`);
  if (props.is_demo === true) lines.push(`<div style="color:#86198f;font-weight:700;font-size:11px">DEMO: dato de ejemplo, no real</div>`);
  if (props.level_label) lines.push(`<div>Nivel calculado: <b>${esc(props.level_label)}</b></div>`);
  if (Array.isArray(props.reasons)) (props.reasons as string[]).slice(0, 3).forEach((r) => lines.push(`<div style="color:#475569;font-size:12px">${esc(r)}</div>`));
  if (props.uses_demo_data === true) lines.push(`<div style="color:#86198f;font-size:11px">Incluye datos DEMO</div>`);
  const fields: [string, string][] = [
    ["category", "Tipo"],
    ["tipo", "Tipo"],
    ["recurrencia", "Recurrencia"],
    ["category", "Categoría"],
    ["sector", "Sector"],
    ["matricula", "Matrícula"],
    ["direccion", "Dirección"],
    ["pm25", "MP2,5 (µg/m³)"],
    ["magnitude", "Magnitud"],
    ["depth_km", "Profundidad (km)"],
    ["occurred_on", "Fecha"],
    ["affected_people", "Personas afectadas"],
    ["vigencia", "Vigencia"],
  ];
  const seen = new Set<string>();
  for (const [key, label] of fields) {
    if (seen.has(key) || props[key] === undefined || props[key] === null || props[key] === "") continue;
    seen.add(key);
    lines.push(`<div><span style="color:#64748b">${label}:</span> ${esc(props[key])}</div>`);
  }
  if (props.observed_at) lines.push(`<div style="color:#64748b;font-size:12px">Medido ${esc(formatShortTime(String(props.observed_at)))} (no validado)</div>`);
  if (props.occurred_at) lines.push(`<div style="color:#64748b;font-size:12px">${esc(formatShortTime(String(props.occurred_at)))}</div>`);
  if (layer) {
    lines.push(
      `<div style="margin-top:6px;padding-top:6px;border-top:1px solid #e2e8f0;font-size:11px;color:#64748b">${esc(DATA_CLASS_STYLE[layer.data_class].label)} · ${esc(layer.source)}</div>`,
    );
  }
  return lines.join("");
}

export function MapView({
  me,
  defaultLayers,
  focus,
  onSectorClick,
}: {
  me: Me;
  defaultLayers?: string[];
  focus?: MapFocus | null;
  onSectorClick?: (id: number) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const [styleReady, setStyleReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);
  const catalog = useQuery({ queryKey: ["layers"], queryFn: () => apiGet<LayerInfo[]>("/layers") });
  const [active, setActive] = useState<string[] | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [search, setSearch] = useState("");
  const results = useQuery({
    queryKey: ["search", search],
    queryFn: () => apiGet<{ name: string; layer: string; lon: number; lat: number }[]>(`/search?q=${encodeURIComponent(search)}`),
    enabled: search.trim().length >= 2,
  });

  const activeLayers = active ?? defaultLayers ?? catalog.data?.filter((l) => l.default_on).map((l) => l.key) ?? [];
  const layerData = useQueries({
    queries: activeLayers.map((key) => ({ queryKey: ["layer", key], queryFn: () => apiGet<FeatureCollectionLike>(`/layers/${key}`), staleTime: 300_000 })),
  });

  useEffect(() => {
    if (!container.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: BASEMAP,
      center: [me.municipality.lon, me.municipality.lat],
      zoom: 11.5,
      attributionControl: { compact: true, customAttribution: "OpenFreeMap © OpenMapTiles Data from OpenStreetMap" },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    let loaded = false;
    map.on("load", () => {
      loaded = true;
      setMapError(null);
      const ring = me.municipality.bbox_geojson?.coordinates?.[0];
      if (ring) {
        const xs = ring.map((c) => c[0]);
        const ys = ring.map((c) => c[1]);
        map.fitBounds([Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)], { padding: 30, duration: 0 });
      }
      setStyleReady(true);
    });
    map.on("error", (e: { error: unknown; sourceId?: string }) => {
      if (!loaded && !e.sourceId) setMapError("No se pudo cargar el mapa base. Revise la conexión a internet.");
      console.warn(e.error);
    });
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [me.municipality.lon, me.municipality.lat, me.municipality.bbox_geojson]);

  const dataKey = layerData.map((q) => q.dataUpdatedAt).join(",");
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleReady || !catalog.data) return;
    const wanted = new Set(activeLayers);
    for (const layer of catalog.data) {
      const ids = (map.getStyle().layers ?? []).map((l) => l.id).filter((id) => id.startsWith(`lyr-${layer.key}-`));
      if (!wanted.has(layer.key)) {
        ids.forEach((id) => map.removeLayer(id));
        if (map.getSource(`src-${layer.key}`)) map.removeSource(`src-${layer.key}`);
      }
    }
    activeLayers.forEach((key, i) => {
      const data = layerData[i]?.data;
      if (!data) return;
      const sourceId = `src-${key}`;
      const existing = map.getSource(sourceId) as GeoJSONSource | undefined;
      if (existing) existing.setData(data as never);
      else {
        map.addSource(sourceId, { type: "geojson", data: data as never });
        addLayerStyle(map, key);
      }
    });
    for (const key of ["lyr-comuna-line"]) if (map.getLayer(key)) map.moveLayer(key);
  }, [styleReady, catalog.data, dataKey, activeLayers.join(",")]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleReady) return;
    const handler = (e: maplibregl.MapMouseEvent) => {
      const layers = (map.getStyle().layers ?? []).map((l) => l.id).filter((id) => id.startsWith("lyr-") && id !== "lyr-comuna-line" && !id.endsWith("-line"));
      const features = map.queryRenderedFeatures(e.point, { layers });
      if (!features.length) return;
      const feature = features[0];
      const key = feature.layer.id.replace(/^lyr-/, "").replace(/-(fill|circle|line)$/, "");
      const info = catalog.data?.find((l) => l.key === key);
      const props: Record<string, unknown> = { ...feature.properties };
      for (const k of ["reasons", "levels"]) if (typeof props[k] === "string") try { props[k] = JSON.parse(props[k] as string); } catch {}
      new maplibregl.Popup({ maxWidth: "300px" }).setLngLat(e.lngLat).setHTML(popupHtml(info, props)).addTo(map);
      if (key === "sectors" && onSectorClick && typeof props.id === "number") onSectorClick(props.id);
    };
    map.on("click", handler);
    return () => {
      map.off("click", handler);
    };
  }, [styleReady, catalog.data, onSectorClick]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focus) return;
    map.flyTo({ center: [focus.lon, focus.lat], zoom: focus.zoom ?? 15 });
    if (focus.label) new maplibregl.Popup().setLngLat([focus.lon, focus.lat]).setText(focus.label).addTo(map);
  }, [focus]);

  function toggle(key: string) {
    setActive(activeLayers.includes(key) ? activeLayers.filter((k) => k !== key) : [...activeLayers, key]);
  }

  return (
    <div className="relative h-full min-h-[420px] w-full overflow-hidden rounded-2xl border border-border bg-slate-100">
      <div ref={container} className="absolute inset-0" />
      {mapError && <div className="absolute inset-x-3 top-3 rounded-lg bg-amber-50 p-2 text-sm text-amber-900 shadow">{mapError}</div>}
      <div className="absolute left-3 top-3 w-64 max-w-[calc(100%-5rem)]">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar establecimiento, sector o activo"
          className="w-full rounded-lg border border-border bg-white/95 px-3 py-2 text-sm shadow outline-none focus:border-brand"
        />
        {results.data && search.trim().length >= 2 && (
          <ul className="mt-1 max-h-60 overflow-auto rounded-lg border border-border bg-white text-sm shadow">
            {results.data.length === 0 && <li className="px-3 py-2 text-muted">Sin resultados</li>}
            {results.data.map((r, i) => (
              <li key={i}>
                <button
                  className="w-full px-3 py-2 text-left hover:bg-slate-50"
                  onClick={() => {
                    mapRef.current?.flyTo({ center: [r.lon, r.lat], zoom: 15.5 });
                    new maplibregl.Popup().setLngLat([r.lon, r.lat]).setText(r.name).addTo(mapRef.current!);
                    setSearch("");
                  }}
                >
                  {r.name}
                  <span className="ml-1 text-xs text-muted">{catalog.data?.find((l) => l.key === r.layer)?.name}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="absolute bottom-8 right-3 w-72 max-w-[calc(100%-1.5rem)]">
        <button onClick={() => setPanelOpen(!panelOpen)} className="ml-auto block rounded-lg bg-white/95 px-3 py-1.5 text-sm font-medium shadow">
          {panelOpen ? "Ocultar capas" : `Capas (${activeLayers.length})`}
        </button>
        {panelOpen && catalog.data && (
          <div className="mt-2 max-h-[55vh] overflow-auto rounded-xl border border-border bg-white/97 p-3 shadow-lg">
            <p className="mb-2 text-xs text-muted">Active pocas capas a la vez para leer mejor el mapa.</p>
            <ul className="space-y-2.5">
              {catalog.data.map((layer) => {
                const on = activeLayers.includes(layer.key);
                return (
                  <li key={layer.key} className="text-sm">
                    <label className="flex cursor-pointer items-start gap-2">
                      <input type="checkbox" checked={on} onChange={() => toggle(layer.key)} className="mt-1" />
                      <span className="flex-1">
                        <span className="font-medium">{layer.name}</span> <DataClassBadge dataClass={layer.data_class} />
                        <span className="block text-xs text-muted">{layer.description}</span>
                        <span className="block text-[11px] text-muted">
                          {layer.source}
                          {layer.updated_at ? ` · ${formatShortTime(layer.updated_at)}` : ""}
                        </span>
                        {on && layer.key === "sectors" && (
                          <span className="mt-1 flex flex-wrap gap-1">
                            {layer.legend.map((l) => (
                              <span key={l.value} className="inline-flex items-center gap-1 text-[11px]">
                                <span className="h-2.5 w-2.5 rounded-sm" style={{ background: LEVEL_STYLE[l.value as keyof typeof LEVEL_STYLE]?.hex }} />
                                {l.label}
                              </span>
                            ))}
                          </span>
                        )}
                        {on && layer.key === "wildfire_hazard" && (
                          <span className="mt-1 flex flex-wrap gap-1">
                            {layer.legend.map((l) => (
                              <span key={l.value} className="inline-flex items-center gap-1 text-[11px]">
                                <span className="h-2.5 w-2.5 rounded-sm" style={{ background: WILDFIRE_COLORS[Number(l.value) - 1] }} />
                                {l.label}
                              </span>
                            ))}
                          </span>
                        )}
                        {on && layer.key === "dmc_warning" && (
                          <span className="mt-1 flex flex-wrap gap-1">
                            {layer.legend.map((l) => (
                              <span key={l.value} className="inline-flex items-center gap-1 text-[11px]">
                                <span className="h-2.5 w-2.5 rounded-sm" style={{ background: WARNING_COLORS[l.value] }} />
                                {l.label}
                              </span>
                            ))}
                          </span>
                        )}
                        {on && POINT_COLORS[layer.key] && (
                          <span className="mt-1 inline-flex items-center gap-1 text-[11px]">
                            <span className="h-2.5 w-2.5 rounded-full" style={{ background: POINT_COLORS[layer.key] }} /> símbolo en el mapa
                          </span>
                        )}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
