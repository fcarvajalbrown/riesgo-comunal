import { formatTime } from "@/lib/format";
import type { SourceState, SourceStatusRow } from "@/lib/types";

const STATE: Record<SourceState, { label: string; dot: string; text: string }> = {
  live: { label: "Funcionando", dot: "bg-green-600", text: "text-green-800" },
  stale: { label: "Sin datos nuevos", dot: "bg-amber-500", text: "text-amber-800" },
  failed: { label: "Falla", dot: "bg-red-600", text: "text-red-800" },
  pending: { label: "Aún sin datos", dot: "bg-slate-400", text: "text-slate-700" },
  unconfigured: { label: "No configurada", dot: "bg-slate-300", text: "text-slate-600" },
};

function names(list: SourceStatusRow[]) {
  return list.map((s) => s.name).join(", ");
}

function lastData(s: SourceStatusRow) {
  return s.last_success_at ? formatTime(s.last_success_at) : "nunca";
}

export function SourceStatus({ sources, showErrors }: { sources: SourceStatusRow[]; showErrors?: boolean }) {
  const alertSources = sources.filter((s) => s.alert);
  const dataSources = sources.filter((s) => !s.alert);
  const alertDown = alertSources.filter((s) => s.state === "failed" || s.state === "stale");
  const alertUp = alertSources.filter((s) => s.state === "live");
  const dataDown = dataSources.filter((s) => s.state !== "live");
  return (
    <div className="text-sm">
      <h3 className="text-base font-semibold">Estado de las fuentes</h3>
      <p className="mt-0.5 text-xs text-muted">
        La plataforma lee varias fuentes independientes. Si una falla, las demás siguen funcionando y se muestra el último dato recibido de cada una.
      </p>
      {alertDown.length > 0 && (
        <p className="mt-2 rounded-lg border border-red-200 bg-red-50 px-2 py-1.5 text-xs text-red-950">
          Sin respuesta reciente: {names(alertDown)}.{" "}
          {alertUp.length > 0
            ? `Siguen funcionando: ${names(alertUp)}.`
            : "Ninguna fuente de alertas responde ahora; consulte senapred.cl y los canales de su municipalidad."}
        </p>
      )}
      <ul className="mt-2 divide-y divide-border rounded-xl border border-border">
        {alertSources.map((s) => (
          <li key={s.key} className="p-2.5 text-xs">
            <p className="flex flex-wrap items-center gap-2">
              <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${STATE[s.state].dot}`} aria-hidden />
              <span className="font-medium">{s.name}</span>
              <span className={`font-semibold ${STATE[s.state].text}`}>{STATE[s.state].label}</span>
            </p>
            <p className="mt-0.5 text-muted">
              {s.organization} · último dato recibido: {lastData(s)}
            </p>
            {showErrors && s.last_error && <p className="mt-1 rounded bg-red-50 px-2 py-1 text-red-900">{s.last_error.slice(0, 200)}</p>}
          </li>
        ))}
        <li className="p-2.5 text-xs">
          <p>
            <span className="font-medium">Otras fuentes de datos:</span> {dataSources.length - dataDown.length} de {dataSources.length} funcionando.
          </p>
          {dataDown.length > 0 && (
            <ul className="mt-1 space-y-0.5 text-muted">
              {dataDown.map((s) => (
                <li key={s.key}>
                  <span className={`font-semibold ${STATE[s.state].text}`}>{STATE[s.state].label}</span>: {s.name}, último dato {lastData(s)}
                </li>
              ))}
            </ul>
          )}
        </li>
      </ul>
    </div>
  );
}
