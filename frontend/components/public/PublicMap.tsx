"use client";

import { useQueries } from "@tanstack/react-query";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MlMap, Marker } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { BASEMAP, POINT_COLORS, WARNING_COLORS, WILDFIRE_COLORS, addLayerStyle } from "@/components/MapView";
import { publicGet } from "@/lib/publicApi";
import type { PublicComuna } from "@/lib/types";

const PUBLIC_LAYERS: { key: string; name: string; source: string; defaultOn: boolean }[] = [
  { key: "tsunami_evacuation_area", name: "Área de evacuación por tsunami", source: "SENAPRED", defaultOn: true },
  { key: "tsunami_meeting_point", name: "Puntos de encuentro por tsunami", source: "SENAPRED", defaultOn: true },
  { key: "dmc_warning", name: "Avisos y alertas meteorológicas vigentes", source: "Dirección Meteorológica de Chile", defaultOn: false },
  { key: "wildfire_hazard", name: "Recurrencia de incendios forestales", source: "SENAPRED con datos de CONAF", defaultOn: false },
];

type Collection = { type: "FeatureCollection"; features: unknown[] };

function Swatch({ layer }: { layer: string }) {
  if (layer === "tsunami_evacuation_area") return <span className="h-3 w-3 rounded-sm border border-blue-700 bg-blue-600/30" />;
  if (layer === "tsunami_meeting_point") return <span className="h-3 w-3 rounded-full border-2 border-white" style={{ background: POINT_COLORS.tsunami_meeting_point }} />;
  if (layer === "dmc_warning") return <span className="h-3 w-3 rounded-sm" style={{ background: WARNING_COLORS.Aviso }} />;
  return <span className="h-3 w-3 rounded-sm" style={{ background: `linear-gradient(90deg, ${WILDFIRE_COLORS[0]}, ${WILDFIRE_COLORS[4]})` }} />;
}

export function PublicMap({
  slug,
  comuna,
  point,
  meetingPoint,
  onPick,
}: {
  slug: string;
  comuna: PublicComuna;
  point: { lon: number; lat: number } | null;
  meetingPoint: { lon: number; lat: number; name: string | null } | null;
  onPick: (lon: number, lat: number) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const markerRef = useRef<Marker | null>(null);
  const meetingRef = useRef<Marker | null>(null);
  const pickRef = useRef(onPick);
  const [styleReady, setStyleReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);
  const [active, setActive] = useState<string[]>(PUBLIC_LAYERS.filter((l) => l.defaultOn).map((l) => l.key));
  const keys = ["comuna", ...active];
  const layerData = useQueries({
    queries: keys.map((key) => ({ queryKey: ["public-layer", slug, key], queryFn: () => publicGet<Collection>(`/${slug}/capas/${key}`), staleTime: 300_000 })),
  });

  useEffect(() => {
    pickRef.current = onPick;
  }, [onPick]);

  useEffect(() => {
    if (!container.current || mapRef.current) return;
    const [west, south, east, north] = comuna.bbox;
    const map = new maplibregl.Map({
      container: container.current,
      style: BASEMAP,
      bounds: [west, south, east, north],
      fitBoundsOptions: { padding: 20 },
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    let loaded = false;
    map.on("load", () => {
      loaded = true;
      setMapError(null);
      setStyleReady(true);
    });
    map.on("error", (e: { error: unknown; sourceId?: string }) => {
      if (!loaded && !e.sourceId) setMapError("No se pudo cargar el mapa base. Revise la conexión a internet.");
      console.warn(e.error);
    });
    map.on("click", (e) => pickRef.current(e.lngLat.lng, e.lngLat.lat));
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [comuna.bbox]);

  const dataKey = layerData.map((q) => q.dataUpdatedAt).join(",");
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleReady) return;
    const wanted = new Set(keys);
    for (const { key } of PUBLIC_LAYERS) {
      if (wanted.has(key)) continue;
      (map.getStyle().layers ?? []).filter((l) => l.id.startsWith(`lyr-${key}-`)).forEach((l) => map.removeLayer(l.id));
      if (map.getSource(`src-${key}`)) map.removeSource(`src-${key}`);
    }
    keys.forEach((key, i) => {
      const data = layerData[i]?.data;
      if (!data) return;
      const existing = map.getSource(`src-${key}`) as GeoJSONSource | undefined;
      if (existing) existing.setData(data as never);
      else {
        map.addSource(`src-${key}`, { type: "geojson", data: data as never });
        addLayerStyle(map, key);
      }
    });
    if (map.getLayer("lyr-comuna-line")) map.moveLayer("lyr-comuna-line");
  }, [styleReady, dataKey, keys.join(",")]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    markerRef.current?.remove();
    markerRef.current = null;
    if (!point) return;
    markerRef.current = new maplibregl.Marker({ color: "#b42318" }).setLngLat([point.lon, point.lat]).addTo(map);
    map.flyTo({ center: [point.lon, point.lat], zoom: Math.max(map.getZoom(), 14.5) });
  }, [point]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    meetingRef.current?.remove();
    meetingRef.current = null;
    if (!meetingPoint) return;
    meetingRef.current = new maplibregl.Marker({ color: POINT_COLORS.tsunami_meeting_point })
      .setLngLat([meetingPoint.lon, meetingPoint.lat])
      .setPopup(new maplibregl.Popup({ offset: 24 }).setText("Punto de encuentro más cercano (SENAPRED)"))
      .addTo(map);
    if (point) {
      const bounds = new maplibregl.LngLatBounds([point.lon, point.lat], [point.lon, point.lat]).extend([meetingPoint.lon, meetingPoint.lat]);
      map.fitBounds(bounds, { padding: 70, maxZoom: 16 });
    }
  }, [meetingPoint, point]);

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="relative min-h-[360px] flex-1 overflow-hidden rounded-2xl border border-border bg-slate-100">
        <div ref={container} style={{ position: "absolute", inset: 0 }} aria-label={`Mapa de ${comuna.name}`} />
        {mapError && <div className="absolute inset-x-3 top-3 rounded-lg bg-amber-50 p-2 text-sm text-amber-900 shadow">{mapError}</div>}
      </div>
      <fieldset className="rounded-xl border border-border bg-surface p-3">
        <legend className="px-1 text-xs font-semibold text-muted">Capas oficiales en el mapa</legend>
        <ul className="grid gap-1.5 sm:grid-cols-2">
          {PUBLIC_LAYERS.map((layer) => (
            <li key={layer.key}>
              <label className="flex cursor-pointer items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={active.includes(layer.key)}
                  onChange={() => setActive((cur) => (cur.includes(layer.key) ? cur.filter((k) => k !== layer.key) : [...cur, layer.key]))}
                />
                <span className="flex-1">
                  <span className="inline-flex items-center gap-1.5 font-medium">
                    <Swatch layer={layer.key} />
                    {layer.name}
                  </span>
                  <span className="block text-[11px] text-muted">Fuente: {layer.source}</span>
                </span>
              </label>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[11px] text-muted">Toque el mapa para revisar un lugar.</p>
      </fieldset>
    </div>
  );
}
