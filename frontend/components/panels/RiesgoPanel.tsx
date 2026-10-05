"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { AssessmentCard } from "@/components/AssessmentCard";
import { DemoBadge, LevelBadge } from "@/components/Badges";
import type { MapFocus } from "@/components/MapView";
import { apiGet } from "@/lib/api";
import { formatTime } from "@/lib/format";
import type { Assessment, Level, RiesgoResponse } from "@/lib/types";

export function RiesgoPanel({ onFocus, selectedSector, onSelectSector }: { onFocus: (f: MapFocus) => void; selectedSector: number | null; onSelectSector: (id: number | null) => void }) {
  const { data, isLoading, error } = useQuery({ queryKey: ["riesgo"], queryFn: () => apiGet<RiesgoResponse>("/riesgo") });
  const sector = useQuery({
    queryKey: ["sector", selectedSector],
    queryFn: () => apiGet<{ sector: { name: string; kind: string }; assessments: Assessment[]; overall_level: Level }>(`/riesgo/sector/${selectedSector}`),
    enabled: selectedSector !== null,
  });
  const [showAll, setShowAll] = useState(false);
  if (isLoading) return <p className="text-sm text-muted">Calculando riesgo territorial...</p>;
  if (error || !data) return <p className="text-sm text-red-700">{(error as Error)?.message ?? "Sin datos"}</p>;
  const ranked = data.sectors.filter((s) => ["CRITICO", "ALTO", "MODERADO"].includes(s.overall_level));
  const visible = showAll ? ranked : ranked.slice(0, 6);
  const focus = (item: { lon: number; lat: number; name: string | null }) => onFocus({ lon: item.lon, lat: item.lat, label: item.name ?? undefined });

  return (
    <div className="space-y-4">
      {selectedSector !== null && (
        <section className="rounded-2xl border-2 border-brand/40 bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-base font-semibold">{sector.data?.sector.name ?? "Sector"}</h3>
            <button onClick={() => onSelectSector(null)} className="text-xs text-muted hover:underline">
              Volver a la comuna
            </button>
          </div>
          {sector.isLoading && <p className="text-sm text-muted">Cargando...</p>}
          {sector.data && (
            <div className="mt-3 space-y-3">
              {sector.data.sector.kind === "analysis_cell" && (
                <p className="text-xs text-muted">Celda de análisis generada por la plataforma (el municipio no ha cargado sectores propios).</p>
              )}
              {sector.data.assessments.map((a) => (
                <AssessmentCard key={a.hazard} assessment={a} onFocus={focus} />
              ))}
            </div>
          )}
        </section>
      )}

      <section className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">Riesgo territorial de {data.municipality.name}</p>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <LevelBadge level={data.overall_level} size="lg" />
          <span className="text-sm text-muted">Nivel más alto entre amenazas con datos. Cálculo de la plataforma, no oficial.</span>
        </div>
        <p className="mt-2 text-xs text-muted">Calculado {formatTime(data.computed_at)}</p>
      </section>

      <section className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
        <h3 className="text-base font-semibold">{data.sector_kind === "municipal" ? "Sectores" : "Celdas de análisis"} que requieren atención</h3>
        <p className="mt-0.5 text-xs text-muted">
          {ranked.length} de {data.sectors.length} con nivel moderado o superior. Toque uno para ver el detalle o selecciónelo en el mapa.
        </p>
        <ul className="mt-3 divide-y divide-border">
          {visible.map((s) => (
            <li key={s.id}>
              <button onClick={() => onSelectSector(s.id)} className="flex w-full items-start gap-3 py-2 text-left hover:bg-slate-50">
                <LevelBadge level={s.overall_level} size="sm" />
                <span className="flex-1 text-sm">
                  <span className="font-medium">{s.name}</span> {s.uses_demo_data && <DemoBadge />}
                  {s.reasons[0] && <span className="block text-xs text-muted">{s.reasons[0]}</span>}
                </span>
              </button>
            </li>
          ))}
        </ul>
        {ranked.length > 6 && (
          <button onClick={() => setShowAll(!showAll)} className="mt-2 text-xs font-medium text-brand hover:underline">
            {showAll ? "Ver menos" : `Ver los ${ranked.length}`}
          </button>
        )}
      </section>

      <div className="space-y-3">
        {data.assessments.map((a) => (
          <AssessmentCard key={a.hazard} assessment={a} onFocus={focus} />
        ))}
      </div>
      <p className="text-xs text-muted">{data.notice}</p>
    </div>
  );
}
