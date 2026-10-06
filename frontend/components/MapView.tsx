"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MlMap, Marker } from "maplibre-gl";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { DataClassBadge } from "@/components/Badges";
import { MapCompare } from "@/components/MapCompare";
import { BASEMAP, LayerLegend, addLayerStyle } from "@/components/mapStyle";
import { ApiError, apiGet, apiObjectUrl } from "@/lib/api";
import { DATA_CLASS_STYLE, formatShortTime } from "@/lib/format";
import type { GeocodeResult, LayerInfo, Me, PlaceReport, RasterInfo } from "@/lib/types";

type FeatureCollectionLike = { type: "FeatureCollection"; features: unknown[] };

export interface MapFocus {
  lon: number;
  lat: number;
  zoom?: number;
  label?: string;
}

const escapeHtml = (v: unknown) => String(v ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string);

export function placeHtml(label: string, report: PlaceReport): string {
  const lines = [`<div style="font-weight:600;font-size:13px;margin-bottom:6px">${escapeHtml(label)}</div>`];
  for (const item of report.items) {
    lines.push(`<div style="margin-bottom:6px">${escapeHtml(item.text)}<div style="color:#64748b;font-size:11px">${escapeHtml(DATA_CLASS_STYLE[item.data_class].label)} · ${escapeHtml(item.source)}</div></div>`);
  }
  for (const w of report.warnings) lines.push(`<div style="margin-bottom:6px"><b>${escapeHtml(w.level)} DMC:</b> ${escapeHtml(w.title)}</div>`);
  for (const a of report.alerts) lines.push(`<div style="margin-bottom:6px"><b>${escapeHtml(a.issuer)}:</b> ${escapeHtml(a.title)}</div>`);
  if (!report.items.length && !report.warnings.length && !report.alerts.length) {
    lines.push(`<div>Fuera de las áreas de tsunami e incendios publicadas y sin avisos meteorológicos vigentes.</div>`);
  }
  lines.push(`<div style="margin-top:6px;padding-top:6px;border-top:1px solid #e2e8f0;font-size:11px;color:#64748b">${escapeHtml(report.notice)}</div>`);
  return lines.join("");
}

function popupHtml(layer: LayerInfo | undefined, props: Record<string, unknown>): string {
  const esc = escapeHtml;
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
    ["n_per", "Personas (Censo 2024)"],
    ["n_vp", "Viviendas particulares"],
    ["n_edad_60_mas", "Personas de 60 años o más"],
    ["densidad", "Personas por hectárea"],
    ["population_estimate", "Población estimada (Censo 2024)"],
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
  const rasters = useQuery({ queryKey: ["rasters"], queryFn: () => apiGet<RasterInfo[]>("/rasters") });
  const [rasterOn, setRasterOn] = useState<number[]>([]);
  const [active, setActive] = useState<string[] | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [addressQuery, setAddressQuery] = useState("");
  const [comparing, setComparing] = useState(false);
  const addressMarker = useRef<Marker | null>(null);
  const addresses = useQuery({
    queryKey: ["geocode", addressQuery],
    queryFn: () => apiGet<GeocodeResult[]>(`/geocode?q=${encodeURIComponent(addressQuery)}`),
    enabled: addressQuery.length >= 3,
    staleTime: Infinity,
    retry: false,
  });
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
      attributionControl: { compact: true },
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

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleReady || !rasters.data) return;
    let cancelled = false;
    for (const raster of rasters.data) {
      const id = `raster-${raster.id}`;
      const wanted = rasterOn.includes(raster.id);
      if (!wanted && map.getSource(id)) {
        map.removeLayer(id);
        map.removeSource(id);
      }
      if (wanted && !map.getSource(id)) {
        apiObjectUrl(`/rasters/${raster.id}/preview.png`)
          .then((url) => {
            if (cancelled || map.getSource(id)) return;
            map.addSource(id, {
              type: "image",
              url,
              coordinates: [
                [raster.west, raster.north],
                [raster.east, raster.north],
                [raster.east, raster.south],
                [raster.west, raster.south],
              ],
            });
            map.addLayer({ id, type: "raster", source: id, paint: { "raster-opacity": 0.75 } }, map.getLayer("lyr-comuna-line") ? "lyr-comuna-line" : undefined);
          })
          .catch(() => setMapError("No se pudo cargar la capa raster."));
      }
    }
    return () => {
      cancelled = true;
    };
  }, [rasterOn, rasters.data, styleReady]);

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

  function submitAddress(e: FormEvent) {
    e.preventDefault();
    setAddressQuery(search.trim());
  }

  async function checkPlace(r: GeocodeResult) {
    const map = mapRef.current;
    if (!map) return;
    setSearch("");
    setAddressQuery("");
    addressMarker.current?.remove();
    map.flyTo({ center: [r.lon, r.lat], zoom: 16 });
    const popup = new maplibregl.Popup({ maxWidth: "320px", offset: 30 }).setHTML(`<div style="font-size:13px">Revisando ${escapeHtml(r.name)}...</div>`);
    addressMarker.current = new maplibregl.Marker({ color: "#b42318" }).setLngLat([r.lon, r.lat]).setPopup(popup).addTo(map);
    addressMarker.current.togglePopup();
    try {
      const report = await apiGet<PlaceReport>(`/lugar?lon=${r.lon}&lat=${r.lat}`);
      popup.setHTML(placeHtml(r.name, report));
    } catch (err) {
      popup.setHTML(`<div style="font-size:13px">${escapeHtml(err instanceof ApiError && err.status === 422 ? "La dirección está fuera de la comuna." : (err as Error).message)}</div>`);
    }
  }

  function toggle(key: string) {
    setActive(activeLayers.includes(key) ? activeLayers.filter((k) => k !== key) : [...activeLayers, key]);
  }

  return (
    <div className="relative h-full min-h-[420px] w-full overflow-hidden rounded-2xl border border-border bg-slate-100">
      <div ref={container} style={{ position: "absolute", inset: 0 }} />
      {comparing && catalog.data && <MapCompare me={me} catalog={catalog.data} view={mapRef.current} onClose={() => setComparing(false)} />}
      {mapError && <div className="absolute inset-x-3 top-3 rounded-lg bg-amber-50 p-2 text-sm text-amber-900 shadow">{mapError}</div>}
      <div className="absolute left-3 top-3 z-10 w-72 max-w-[calc(100%-5rem)]">
        <form onSubmit={submitAddress}>
          <input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setAddressQuery("");
            }}
            placeholder="Buscar lugar o dirección (Enter)"
            aria-label="Buscar establecimiento, sector, activo o dirección"
            className="w-full rounded-lg border border-border bg-white/95 px-3 py-2 text-sm shadow outline-none focus:border-brand"
          />
        </form>
        {search.trim().length >= 2 && (
          <div className="mt-1 max-h-72 overflow-auto rounded-lg border border-border bg-white text-sm shadow">
            <ul>
              {results.data?.map((r, i) => (
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
            <div className="border-t border-border px-3 py-2">
              {!addressQuery && (
                <button type="button" className="text-left text-xs font-medium text-brand underline disabled:opacity-50" onClick={() => setAddressQuery(search.trim())} disabled={search.trim().length < 3}>
                  {results.data && results.data.length === 0 ? "Sin resultados en las capas. " : ""}Buscar como dirección
                </button>
              )}
              {addresses.isFetching && <p className="text-xs text-muted">Buscando dirección...</p>}
              {addresses.error && <p className="text-xs text-red-700">{(addresses.error as Error).message}</p>}
              {addresses.data && (
                <>
                  <p className="text-xs font-semibold text-muted">Direcciones</p>
                  {addresses.data.length === 0 && <p className="text-xs text-muted">No se encontró la dirección en la comuna.</p>}
                  <ul>
                    {addresses.data.map((r, i) => (
                      <li key={i}>
                        <button type="button" className="w-full py-1.5 text-left text-sm hover:text-brand" onClick={() => checkPlace(r)}>
                          {r.name}
                        </button>
                      </li>
                    ))}
                  </ul>
                  {addresses.data[0] && <p className="text-[10px] text-muted">{addresses.data[0].attribution}</p>}
                </>
              )}
            </div>
          </div>
        )}
      </div>
      <div className="absolute bottom-8 right-3 z-10 w-72 max-w-[calc(100%-1.5rem)]">
        <div className="flex justify-end gap-2">
          <button onClick={() => setComparing(true)} className="rounded-lg bg-white/95 px-3 py-1.5 text-sm font-medium shadow">
            Comparar amenazas
          </button>
          <button onClick={() => setPanelOpen(!panelOpen)} className="rounded-lg bg-white/95 px-3 py-1.5 text-sm font-medium shadow">
            {panelOpen ? "Ocultar capas" : `Capas (${activeLayers.length})`}
          </button>
        </div>
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
                        {on && <LayerLegend layer={layer} />}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
            {rasters.data && rasters.data.length > 0 && (
              <div className="mt-3 border-t border-border pt-2">
                <p className="text-xs font-semibold text-muted">Capas raster municipales</p>
                <ul className="mt-1 space-y-1.5">
                  {rasters.data.map((r) => (
                    <li key={r.id}>
                      <label className="flex cursor-pointer items-start gap-2 text-sm">
                        <input
                          type="checkbox"
                          className="mt-1"
                          checked={rasterOn.includes(r.id)}
                          onChange={() => setRasterOn((cur) => (cur.includes(r.id) ? cur.filter((x) => x !== r.id) : [...cur, r.id]))}
                        />
                        <span className="flex-1">
                          <span className="font-medium">{r.name}</span> <DataClassBadge dataClass="municipal" />
                          <span className="block text-[11px] text-muted">
                            GeoTIFF cargado por el municipio · {r.properties.crs ?? "sin CRS"}
                            {r.properties.min !== undefined ? ` · valores ${r.properties.min.toFixed(1)} a ${r.properties.max?.toFixed(1)}` : ""}
                          </span>
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
