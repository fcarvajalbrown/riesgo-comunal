"use client";

import { useQuery } from "@tanstack/react-query";
import { AssessmentCard } from "@/components/AssessmentCard";
import { DataClassBadge, LevelBadge } from "@/components/Badges";
import type { MapFocus } from "@/components/MapView";
import { ProvenanceButton } from "@/components/Provenance";
import { apiGet } from "@/lib/api";
import { formatTime } from "@/lib/format";
import type { AhoraResponse } from "@/lib/types";

const ALERT_ORIGIN: Record<string, string> = {
  dmc_cap: "Recibido automáticamente desde el canal oficial CAP de la Dirección Meteorológica de Chile.",
  senapred_alertas: "Leído automáticamente de la página pública senapred.cl/alertas. Confirme en senapred.cl.",
};

const WARNING_TONE: Record<string, string> = {
  Alarma: "border-red-300 bg-red-50 text-red-950",
  Alerta: "border-orange-300 bg-orange-50 text-orange-950",
  Aviso: "border-yellow-300 bg-yellow-50 text-yellow-950",
  "Alerta Roja": "border-red-300 bg-red-50 text-red-950",
  "Alerta Amarilla": "border-yellow-400 bg-yellow-50 text-yellow-950",
  "Alerta Temprana Preventiva": "border-green-300 bg-green-50 text-green-950",
  default: "border-red-200 bg-red-50 text-red-950",
};

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
        <h3 className="text-base font-semibold">Avisos y alertas oficiales</h3>
        {data.alerts.length === 0 ? (
          <p className="mt-1 text-sm">No hay avisos ni alertas oficiales vigentes para la comuna en la plataforma.</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {data.alerts.map((a) => {
              const started = new Date(a.starts_at).getTime() <= Date.now();
              const tone = WARNING_TONE[a.level] ?? WARNING_TONE.default;
              return (
                <li key={a.id} className={`rounded-xl border p-3 text-sm ${tone}`}>
                  <p className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-current px-2 py-0.5 text-xs font-semibold">{a.level}</span>
                    <span className="text-xs font-medium">{started ? "Vigente" : "Próximo"}</span>
                    <DataClassBadge dataClass="official_warning" />
                  </p>
                  <p className="mt-1 font-semibold">{a.title}</p>
                  <p className="text-xs">
                    {a.issuer} · {started ? "desde" : "comienza"} {formatTime(a.starts_at)}
                    {a.ends_at ? ` · hasta ${formatTime(a.ends_at)}` : ""}
                  </p>
                  <p className="text-xs text-muted">
                    {ALERT_ORIGIN[a.source_key ?? ""] ?? "Ingresado por el municipio con su enlace oficial."}
                  </p>
                  <span className="mt-1 flex flex-wrap gap-3 text-xs">
                    <a href={a.source_url} target="_blank" rel="noreferrer" className="font-medium text-brand underline">
                      Boletín oficial
                    </a>
                    {a.provenance_id ? <ProvenanceButton id={a.provenance_id} /> : null}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
        <p className="mt-2 text-xs text-muted">
          {data.alert_feed_note} Que no haya alerta registrada no significa que no haya peligro.{" "}
          <a className="font-medium text-brand underline" href="https://senapred.cl/alertas" target="_blank" rel="noreferrer">
            Ver alertas en senapred.cl
          </a>
        </p>
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
