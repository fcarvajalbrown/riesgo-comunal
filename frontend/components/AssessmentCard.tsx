"use client";

import { useState } from "react";
import { DataClassBadge, DemoBadge, LevelBadge } from "@/components/Badges";
import { ProvenanceButton } from "@/components/Provenance";
import { formatTime } from "@/lib/format";
import type { Assessment, ExposureItem } from "@/lib/types";

type Depth = 0 | 1 | 2 | 3;
const STEPS = ["Por qué", "Detalle", "Datos técnicos"];

export function AssessmentCard({ assessment, onFocus }: { assessment: Assessment; onFocus?: (item: ExposureItem) => void }) {
  const [depth, setDepth] = useState<Depth>(0);
  const a = assessment;
  return (
    <article className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-semibold">{a.hazard_name}</h3>
        <div className="flex items-center gap-2">
          {a.uses_demo_data && <DemoBadge />}
          <LevelBadge level={a.level} />
        </div>
      </header>
      <p className="mt-2 text-[15px] leading-snug">{a.headline}</p>
      <p className="mt-1 text-[11px] text-muted">Nivel: cálculo de la plataforma, no es una alerta oficial.</p>

      {depth >= 1 && (
        <div className="mt-3 space-y-1.5 border-t border-border pt-3 text-sm">
          {a.explanation.map((line, i) => (
            <p key={i}>{line}</p>
          ))}
          {a.missing.length > 0 && (
            <div className="rounded-lg bg-slate-50 p-2.5 text-xs">
              <p className="font-medium">Falta información:</p>
              <ul className="ml-4 list-disc">
                {a.missing.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </div>
          )}
          {a.actions.length > 0 && (
            <div className="rounded-lg bg-blue-50 p-2.5 text-xs text-blue-950">
              <p className="font-medium">El municipio podría considerar revisar:</p>
              <ul className="ml-4 list-disc">
                {a.actions.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
              <p className="mt-1 opacity-80">Sugerencias de apoyo; las decisiones corresponden a las autoridades.</p>
            </div>
          )}
        </div>
      )}

      {depth >= 2 && (
        <div className="mt-3 space-y-3 border-t border-border pt-3">
          {a.evidence.length > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted">Evidencia</p>
              <ul className="space-y-2">
                {a.evidence.map((e, i) => (
                  <li key={i} className="rounded-lg border border-border p-2.5 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium">{e.label}</span>
                      <DataClassBadge dataClass={e.data_class} />
                    </div>
                    <p className="mt-0.5">{String(e.value)}</p>
                    {e.note && <p className="mt-0.5 text-xs text-amber-800">{e.note}</p>}
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                      <span>{e.source}</span>
                      {e.updated_at && <span>Actualizado {formatTime(e.updated_at)}</span>}
                      <ProvenanceButton id={e.provenance_id} />
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {a.exposure.some((x) => x.count > 0) && (
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted">Exposición</p>
              <ul className="space-y-2">
                {a.exposure
                  .filter((x) => x.count > 0)
                  .map((x) => (
                    <li key={x.category} className="rounded-lg border border-border p-2.5 text-sm">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-medium">
                          {x.count.toLocaleString("es-CL")} · {x.label}
                        </span>
                        <DataClassBadge dataClass={x.data_class} />
                      </div>
                      {x.note && <p className="mt-1 text-xs text-muted">{x.note}</p>}
                      <ul className="mt-1 flex flex-wrap gap-1.5">
                        {x.items.map((item) => (
                          <li key={item.id}>
                            <button
                              type="button"
                              onClick={() => onFocus?.(item)}
                              className="rounded-md bg-slate-100 px-2 py-0.5 text-xs hover:bg-slate-200"
                              title="Ver en el mapa"
                            >
                              {item.name}
                            </button>
                          </li>
                        ))}
                      </ul>
                      <p className="mt-1 text-xs text-muted">{x.source}</p>
                    </li>
                  ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {depth >= 3 && (
        <div className="mt-3 border-t border-border pt-3 text-xs">
          <p className="mb-1 font-semibold uppercase tracking-wide text-muted">Umbrales en uso</p>
          <table className="w-full">
            <tbody>
              {Object.entries(a.thresholds).map(([k, v]) => (
                <tr key={k} className="border-b border-border last:border-0">
                  <td className="py-1 font-mono text-muted">{k}</td>
                  <td className="py-1 text-right font-mono">{String(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-muted">{a.notice}</p>
          <p className="mt-1 text-muted">Método: ver documento docs/risk-model.md de la plataforma (módulo {a.hazard}).</p>
        </div>
      )}

      <footer className="mt-3 flex flex-wrap gap-2">
        {STEPS.map((label, i) => {
          const target = (i + 1) as Depth;
          const active = depth >= target;
          return (
            <button
              key={label}
              type="button"
              onClick={() => setDepth(active ? ((target - 1) as Depth) : target)}
              className={`rounded-full border px-3 py-1 text-xs font-medium ${active ? "border-brand bg-brand text-white" : "border-border hover:bg-slate-50"}`}
            >
              {label}
            </button>
          );
        })}
      </footer>
    </article>
  );
}
