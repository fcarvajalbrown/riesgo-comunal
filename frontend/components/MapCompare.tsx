"use client";

import { useQuery } from "@tanstack/react-query";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MlMap } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { DataClassBadge } from "@/components/Badges";
import { BASEMAP, LayerLegend, addLayerStyle } from "@/components/mapStyle";
import { apiGet } from "@/lib/api";
import { formatShortTime } from "@/lib/format";
import type { LayerInfo, Me } from "@/lib/types";

type Collection = { type: "FeatureCollection"; features: unknown[] };
type Camera = { center: [number, number]; zoom: number };

const PREFERRED = ["wildfire_hazard", "census_block", "tsunami_evacuation_area", "sectors", "dmc_warning", "municipal_incident", "earthquake"];

function pickDefaults(options: LayerInfo[]): [string, string] {
  const keys = options.map((l) => l.key);
  const ordered = [...PREFERRED.filter((k) => keys.includes(k)), ...keys.filter((k) => !PREFERRED.includes(k))];
  return [ordered[0] ?? "", ordered[1] ?? ordered[0] ?? ""];
}

function ComparePane({
  layer,
  options,
  onLayer,
  camera,
  onReady,
}: {
  layer: LayerInfo | undefined;
  options: LayerInfo[];
  onLayer: (key: string) => void;
  camera: Camera;
  onReady: (map: MlMap | null) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const [styleReady, setStyleReady] = useState(false);
  const boundary = useQuery({ queryKey: ["layer", "comuna"], queryFn: () => apiGet<Collection>("/layers/comuna"), staleTime: 300_000 });
  const data = useQuery({
    queryKey: ["layer", layer?.key],
    queryFn: () => apiGet<Collection>(`/layers/${layer!.key}`),
    enabled: !!layer,
    staleTime: 300_000,
  });

  useEffect(() => {
    if (!container.current || mapRef.current) return;
    const map = new maplibregl.Map({ container: container.current, style: BASEMAP, center: camera.center, zoom: camera.zoom, attributionControl: { compact: true } });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("load", () => setStyleReady(true));
    mapRef.current = map;
    onReady(map);
    return () => {
      onReady(null);
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleReady) return;
    for (const l of map.getStyle().layers ?? []) if (l.id.startsWith("lyr-") && l.id !== "lyr-comuna-line") map.removeLayer(l.id);
    for (const id of Object.keys(map.getStyle().sources ?? {})) if (id.startsWith("src-") && id !== "src-comuna") map.removeSource(id);
    if (layer && data.data) {
      map.addSource(`src-${layer.key}`, { type: "geojson", data: data.data as never });
      addLayerStyle(map, layer.key);
    }
    if (boundary.data) {
      const existing = map.getSource("src-comuna") as GeoJSONSource | undefined;
      if (existing) existing.setData(boundary.data as never);
      else {
        map.addSource("src-comuna", { type: "geojson", data: boundary.data as never });
        addLayerStyle(map, "comuna");
      }
      map.moveLayer("lyr-comuna-line");
    }
  }, [styleReady, layer?.key, data.dataUpdatedAt, boundary.dataUpdatedAt]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-b border-border bg-white px-3 py-2">
        <select
          value={layer?.key ?? ""}
          onChange={(e) => onLayer(e.target.value)}
          aria-label="Capa a comparar"
          className="w-full rounded-lg border border-border px-2 py-1.5 text-sm font-medium"
        >
          {options.map((o) => (
            <option key={o.key} value={o.key}>
              {o.name}
            </option>
          ))}
        </select>
        {layer && (
          <div className="mt-1 text-[11px] text-muted">
            <span className="mr-1">
              <DataClassBadge dataClass={layer.data_class} />
            </span>
            {layer.source}
            {layer.updated_at ? ` · ${formatShortTime(layer.updated_at)}` : ""}
            {data.data && data.data.features.length === 0 && <span className="ml-1 font-medium text-amber-800">· sin elementos en la comuna</span>}
            <LayerLegend layer={layer} />
          </div>
        )}
      </div>
      <div className="relative min-h-[160px] flex-1">
        <div ref={container} style={{ position: "absolute", inset: 0 }} />
        {data.isLoading && <div className="absolute left-2 top-2 rounded bg-white/90 px-2 py-1 text-xs shadow">Cargando capa...</div>}
      </div>
    </div>
  );
}

export function MapCompare({ me, catalog, view, onClose }: { me: Me; catalog: LayerInfo[]; view: MlMap | null; onClose: () => void }) {
  const options = catalog.filter((l) => l.key !== "comuna");
  const [keys, setKeys] = useState<[string, string]>(() => pickDefaults(options));
  const maps = useRef<(MlMap | null)[]>([null, null]);
  const syncing = useRef(false);
  const camera: Camera = view
    ? { center: [view.getCenter().lng, view.getCenter().lat], zoom: view.getZoom() }
    : { center: [me.municipality.lon, me.municipality.lat], zoom: 11.5 };

  function register(index: number) {
    return (map: MlMap | null) => {
      maps.current[index] = map;
      if (!map) return;
      map.on("move", () => {
        if (syncing.current) return;
        const other = maps.current[1 - index];
        if (!other) return;
        syncing.current = true;
        other.jumpTo({ center: map.getCenter(), zoom: map.getZoom(), bearing: map.getBearing(), pitch: map.getPitch() });
        syncing.current = false;
      });
    };
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-white md:absolute md:z-20" role="dialog" aria-label="Comparar amenazas">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <p className="text-sm font-semibold">Comparar amenazas</p>
        <p className="hidden text-xs text-muted md:block">Los dos mapas se mueven juntos. Cada lado muestra una capa con su fuente y tipo de dato.</p>
        <button onClick={onClose} className="ml-auto rounded-lg border border-border px-3 py-1 text-sm hover:bg-slate-50">
          Cerrar
        </button>
      </div>
      <div className="flex min-h-0 flex-1 flex-col md:flex-row md:divide-x md:divide-border">
        {[0, 1].map((i) => (
          <ComparePane
            key={i}
            layer={options.find((o) => o.key === keys[i])}
            options={options}
            onLayer={(key) => setKeys((cur) => (i === 0 ? [key, cur[1]] : [cur[0], key]))}
            camera={camera}
            onReady={register(i)}
          />
        ))}
      </div>
    </div>
  );
}
