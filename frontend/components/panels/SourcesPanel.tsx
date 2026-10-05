"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiSend } from "@/lib/api";
import { formatTime } from "@/lib/format";

interface SourceRow {
  key: string;
  name: string;
  organization: string;
  url: string;
  license: string;
  commercial_use: string;
  cache_allowed: string;
  authority: string;
  attribution: string;
  interval_minutes: number;
  enabled: boolean;
  requires: string[];
  last_attempt_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  last_record_count: number | null;
}

function interval(minutes: number) {
  if (minutes < 60) return `cada ${minutes} min`;
  if (minutes < 1440) return `cada ${minutes / 60} h`;
  return `cada ${Math.round(minutes / 1440)} día(s)`;
}

export function SourcesPanel({ canRun }: { canRun: boolean }) {
  const queryClient = useQueryClient();
  const sources = useQuery({ queryKey: ["sources"], queryFn: () => apiGet<SourceRow[]>("/sources") });
  const run = useMutation({
    mutationFn: (key: string) => apiSend<{ status: string; error?: string }>(`/sources/${key}/run`, "POST"),
    onSuccess: () => queryClient.invalidateQueries(),
  });
  return (
    <div className="space-y-3">
      <div className="rounded-2xl border border-border bg-surface p-4 text-sm shadow-sm">
        <h3 className="text-base font-semibold">Fuentes de datos</h3>
        <p className="mt-0.5 text-muted">
          La plataforma descarga y normaliza datos oficiales en su propio servidor; el navegador y el asistente nunca consultan servicios externos directamente.
        </p>
      </div>
      {sources.data?.map((s) => {
        const ok = s.last_success_at && !s.last_error;
        return (
          <article key={s.key} className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h4 className="font-semibold">{s.name}</h4>
                <p className="text-xs text-muted">{s.organization}</p>
              </div>
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${ok ? "bg-green-50 text-green-800" : s.last_error ? "bg-red-50 text-red-800" : "bg-slate-100 text-slate-700"}`}>
                {ok ? "Funcionando" : s.last_error ? "Con problemas" : "Sin ejecutar"}
              </span>
            </div>
            <dl className="mt-3 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
              <div>
                <dt className="inline text-muted">Última actualización: </dt>
                <dd className="inline">{s.last_success_at ? formatTime(s.last_success_at) : "nunca"}</dd>
              </div>
              <div>
                <dt className="inline text-muted">Frecuencia: </dt>
                <dd className="inline">{interval(s.interval_minutes)}</dd>
              </div>
              <div>
                <dt className="inline text-muted">Autoridad: </dt>
                <dd className="inline">{s.authority}</dd>
              </div>
              <div>
                <dt className="inline text-muted">Registros última carga: </dt>
                <dd className="inline">{s.last_record_count ?? "-"}</dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="inline text-muted">Licencia: </dt>
                <dd className="inline">{s.license}</dd>
              </div>
              <div>
                <dt className="inline text-muted">Uso comercial: </dt>
                <dd className="inline">{s.commercial_use}</dd>
              </div>
              <div>
                <dt className="inline text-muted">Caché permitido: </dt>
                <dd className="inline">{s.cache_allowed}</dd>
              </div>
            </dl>
            {s.last_error && <p className="mt-2 rounded-lg bg-red-50 px-2 py-1 text-xs text-red-900">{s.last_error.slice(0, 300)}</p>}
            {canRun && (
              <button
                onClick={() => run.mutate(s.key)}
                disabled={run.isPending}
                className="mt-3 rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:bg-slate-50 disabled:opacity-50"
              >
                {run.isPending && run.variables === s.key ? "Actualizando..." : "Actualizar ahora"}
              </button>
            )}
          </article>
        );
      })}
    </div>
  );
}
