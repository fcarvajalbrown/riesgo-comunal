"use client";

import { useQuery } from "@tanstack/react-query";
import { AssessmentCard } from "@/components/AssessmentCard";
import { LevelBadge } from "@/components/Badges";
import type { MapFocus } from "@/components/MapView";
import { apiGet } from "@/lib/api";
import { formatTime } from "@/lib/format";
import type { AhoraResponse } from "@/lib/types";

export function AhoraPanel({ onFocus, compact }: { onFocus: (f: MapFocus) => void; compact?: boolean }) {
  const { data, isLoading, error } = useQuery({ queryKey: ["ahora"], queryFn: () => apiGet<AhoraResponse>("/ahora"), refetchInterval: 300_000 });
  if (isLoading) return <p className="text-sm text-muted">Cargando situación actual...</p>;
  if (error || !data) return <p className="text-sm text-red-700">{(error as Error)?.message ?? "Sin datos"}</p>;
  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">Ahora en {data.municipality.name}</p>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <LevelBadge level={data.overall_level} size="lg" />
          <span className="text-sm text-muted">Nivel más alto entre las condiciones actuales evaluadas. Cálculo de la plataforma.</span>
        </div>
        <p className="mt-2 text-xs text-muted">Actualizado {formatTime(data.computed_at)}</p>
      </section>

      <section className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
        <h3 className="text-base font-semibold">Alertas oficiales</h3>
        {data.alerts.length === 0 ? (
          <p className="mt-1 text-sm">
            No hay alertas oficiales ingresadas.{" "}
            <span className="text-muted">
              {data.alert_feed_note} Que no haya alerta registrada no significa que no haya peligro.
            </span>{" "}
            <a className="font-medium text-brand underline" href="https://senapred.cl/alertas" target="_blank" rel="noreferrer">
              Ver alertas en senapred.cl
            </a>
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {data.alerts.map((a) => (
              <li key={a.id} className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm">
                <p className="font-semibold text-red-900">{a.title}</p>
                <p className="text-red-900">
                  {a.issuer} · {a.level} · desde {formatTime(a.starts_at)}
                </p>
                {a.description && <p className="mt-1">{a.description}</p>}
                <a href={a.source_url} target="_blank" rel="noreferrer" className="mt-1 inline-block text-xs font-medium text-brand underline">
                  Fuente oficial
                </a>
              </li>
            ))}
          </ul>
        )}
      </section>

      {data.exposure_summary.length > 0 && (
        <section className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
          <h3 className="text-base font-semibold">Si ocurre un evento, lo expuesto es</h3>
          <ul className="mt-2 space-y-2 text-sm">
            {data.exposure_summary.map((s) => (
              <li key={s.hazard} className="flex flex-wrap items-start gap-2">
                <LevelBadge level={s.level} size="sm" />
                <span>
                  <b>{s.hazard_name}:</b> {s.exposure.length ? s.exposure.map((x) => `${x.count} ${x.label.toLowerCase()}`).join(" · ") : "sin establecimientos registrados en la zona"}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-muted">Exposición territorial permanente según mapas de amenaza; no indica un evento en curso.</p>
        </section>
      )}

      <div className="space-y-3">
        {data.assessments.map((a) => (
          <AssessmentCard key={a.hazard} assessment={a} onFocus={(item) => onFocus({ lon: item.lon, lat: item.lat, label: item.name ?? undefined })} />
        ))}
      </div>
      {!compact && <p className="text-xs text-muted">{data.notice}</p>}
    </div>
  );
}
