"use client";

import { useQuery } from "@tanstack/react-query";
import { AssessmentCard } from "@/components/AssessmentCard";
import { BarChart } from "@/components/BarChart";
import { DataClassBadge, DemoBadge } from "@/components/Badges";
import type { MapFocus } from "@/components/MapView";
import { ProvenanceButton } from "@/components/Provenance";
import { apiGet } from "@/lib/api";
import { formatTime } from "@/lib/format";
import type { PlanificarResponse, Trend } from "@/lib/types";

function TrendLine({ trend }: { trend: Trend }) {
  const tone = trend.conclusion === "insufficient" ? "bg-slate-50 text-slate-700" : trend.conclusion === "no_trend" ? "bg-slate-50 text-slate-800" : "bg-amber-50 text-amber-900";
  return <p className={`mt-2 rounded-lg px-3 py-2 text-sm ${tone}`}>{trend.statement}</p>;
}

function Meta({ period, n, source, method, limitations }: { period?: string; n?: number; source: string; method?: string; limitations?: string[] }) {
  return (
    <details className="mt-3 text-xs text-muted">
      <summary className="cursor-pointer font-medium text-foreground">
        Período {period ?? "-"} · n = {n ?? 0} · {source}
      </summary>
      {method && <p className="mt-1">Método: {method}</p>}
      {limitations && limitations.length > 0 && (
        <ul className="ml-4 mt-1 list-disc">
          {limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      )}
    </details>
  );
}

export function PlanificarPanel({ onFocus }: { onFocus: (f: MapFocus) => void }) {
  const { data, isLoading, error } = useQuery({ queryKey: ["planificar"], queryFn: () => apiGet<PlanificarResponse>("/planificar") });
  if (isLoading) return <p className="text-sm text-muted">Calculando estadísticas...</p>;
  if (error || !data) return <p className="text-sm text-red-700">{(error as Error)?.message ?? "Sin datos"}</p>;
  const { icfsr, earthquakes, incidents } = data;
  return (
    <div className="space-y-4">
      {icfsr && (
        <section className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-base font-semibold">Factores subyacentes del riesgo (ICFSR)</h3>
            <DataClassBadge dataClass="official" />
          </div>
          <p className="mt-2 text-2xl font-semibold">
            {icfsr.value.toFixed(2)} <span className="text-base font-medium text-muted">nivel {icfsr.level}</span>
          </p>
          <p className="text-sm text-muted">
            Año {icfsr.year}. Posición {icfsr.rank} de {icfsr.total} comunas (1 = mayor índice).
          </p>
          <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
            {Object.entries(icfsr.components).map(([k, v]) => (
              <div key={k} className="rounded-lg bg-slate-50 p-2">
                <dt className="text-xs text-muted">{k}</dt>
                <dd className="font-semibold">{v ?? "-"}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-2 text-xs text-muted">{icfsr.note}</p>
          <div className="mt-1 flex flex-wrap gap-3 text-xs text-muted">
            <span>
              {icfsr.source} · {formatTime(icfsr.updated_at)}
            </span>
            <ProvenanceButton id={icfsr.provenance_id} />
          </div>
        </section>
      )}

      <section className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-base font-semibold">Incidentes registrados por el municipio</h3>
          <span className="flex gap-1">
            {incidents.is_demo && <DemoBadge />}
            <DataClassBadge dataClass="municipal" />
          </span>
        </div>
        {incidents.empty ? (
          <p className="mt-2 text-sm text-muted">{incidents.message}</p>
        ) : (
          <>
            <p className="mt-1 text-sm">
              {incidents.sample_size} incidentes · {incidents.affected_people} personas afectadas registradas
            </p>
            <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-muted">Por año</p>
            <BarChart label="Incidentes por año" data={(incidents.by_year ?? []).map((r) => ({ label: String(r.year).slice(2), value: r.total }))} />
            {incidents.trend && <TrendLine trend={incidents.trend} />}
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">Por amenaza</p>
                <ul className="mt-1 space-y-1 text-sm">
                  {(incidents.by_hazard ?? []).map((h) => (
                    <li key={h.hazard} className="flex justify-between gap-2">
                      <span>{h.label}</span>
                      <span className="font-medium">{h.total}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">Estacionalidad (por mes)</p>
                <BarChart label="Incidentes por mes" color="#b45309" data={(incidents.seasonality ?? []).map((m) => ({ label: m.label, value: m.total }))} />
              </div>
            </div>
            {(incidents.recurrence ?? []).length > 0 && (
              <div className="mt-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">Sectores recurrentes (incidentes en 2 o más años)</p>
                <ul className="mt-1 flex flex-wrap gap-1.5">
                  {(incidents.recurrence ?? []).map((s) => (
                    <li key={s.sector} className="rounded-md bg-amber-50 px-2 py-0.5 text-xs text-amber-900">
                      {s.sector}: {s.total} en {s.years_with_events} años
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <Meta period={incidents.period} n={incidents.sample_size} source="Registro municipal" method={incidents.method} limitations={incidents.limitations} />
          </>
        )}
      </section>

      <section className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-base font-semibold">{earthquakes.title}</h3>
          <DataClassBadge dataClass="historical" />
        </div>
        <BarChart label={earthquakes.title} color="#92400e" data={earthquakes.series.map((r) => ({ label: String(r.year).slice(2), value: r.total }))} />
        <TrendLine trend={earthquakes.trend} />
        <Meta period={earthquakes.period} n={earthquakes.sample_size} source={earthquakes.source} method={earthquakes.method} limitations={earthquakes.limitations} />
        <div className="mt-1">
          <ProvenanceButton id={earthquakes.provenance_id} />
        </div>
      </section>

      <div className="space-y-3">
        {data.assessments.map((a) => (
          <AssessmentCard key={a.hazard} assessment={a} onFocus={(item) => onFocus({ lon: item.lon, lat: item.lat, label: item.name ?? undefined })} />
        ))}
      </div>
    </div>
  );
}
