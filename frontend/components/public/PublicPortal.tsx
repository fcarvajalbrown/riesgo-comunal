"use client";

import { useQuery } from "@tanstack/react-query";
import { type FormEvent, useCallback, useState } from "react";
import { DataClassBadge, LevelBadge } from "@/components/Badges";
import { PublicMap } from "@/components/public/PublicMap";
import { ApiError } from "@/lib/api";
import { WARNING_TONE, formatTime } from "@/lib/format";
import { publicGet } from "@/lib/publicApi";
import type { GeocodeResult, PlaceReport, PublicComuna, PublicSummary } from "@/lib/types";

const OFFICIAL_LINKS = [
  { label: "SENAPRED", detail: "Servicio Nacional de Prevención y Respuesta ante Desastres", href: "https://senapred.cl" },
  { label: "Alertas vigentes de SENAPRED", detail: "Listado oficial de alertas declaradas", href: "https://senapred.cl/alertas" },
  { label: "Dirección Meteorológica de Chile", detail: "Pronósticos, avisos, alertas y alarmas meteorológicas", href: "https://www.meteochile.gob.cl" },
];

const EMERGENCY_PHONES = [
  { number: "131", label: "Ambulancia (SAMU)" },
  { number: "132", label: "Bomberos" },
  { number: "133", label: "Carabineros" },
];

function Section({ title, children, id }: { title: string; children: React.ReactNode; id: string }) {
  return (
    <section aria-labelledby={id} className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
      <h2 id={id} className="text-lg font-semibold">
        {title}
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function CurrentSituation({ summary }: { summary: PublicSummary }) {
  return (
    <div className="space-y-4">
      {summary.alerts.length === 0 ? (
        <div className="rounded-xl border border-border bg-slate-50 p-3 text-sm">
          <p className="font-medium">No hay avisos ni alertas oficiales registrados para la comuna en este momento.</p>
          <p className="mt-1 text-muted">Que no aparezca una alerta no significa que no exista peligro. Confirme en senapred.cl.</p>
        </div>
      ) : (
        <ul className="space-y-2">
          {summary.alerts.map((alert, i) => (
            <li key={i} className={`rounded-xl border p-3 text-sm ${WARNING_TONE[alert.level] ?? WARNING_TONE.default}`}>
              <p className="flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-current px-2 py-0.5 text-xs font-semibold">{alert.level}</span>
                <span className="text-xs font-medium">{alert.in_force ? "Vigente" : "Próximo"}</span>
                <DataClassBadge dataClass="official_warning" />
              </p>
              <p className="mt-1 font-semibold">{alert.title}</p>
              <p className="text-xs">
                {alert.issuer} · {alert.in_force ? "desde" : "comienza"} {formatTime(alert.starts_at)}
                {alert.ends_at ? ` · hasta ${formatTime(alert.ends_at)}` : ""}
              </p>
              <p className="mt-1 text-xs opacity-80">Origen: {alert.origin}.</p>
              {alert.source_url && (
                <a href={alert.source_url} target="_blank" rel="noreferrer" className="mt-1 inline-block text-xs font-semibold underline">
                  Ver el anuncio oficial
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-muted">{summary.alert_feed_note}</p>

      <div>
        <h3 className="flex flex-wrap items-center gap-2 text-sm font-semibold">
          Resumen por amenaza <DataClassBadge dataClass="derived" />
        </h3>
        <ul className="mt-2 divide-y divide-border rounded-xl border border-border">
          {summary.items.map((item) => (
            <li key={item.hazard} className="flex flex-col gap-1 p-3 text-sm sm:flex-row sm:items-start sm:gap-3">
              <span className="shrink-0">
                <LevelBadge level={item.level} size="sm" />
              </span>
              <span>
                <span className="font-medium">{item.hazard}.</span> {item.headline}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-muted">{summary.notice}</p>
        <p className="mt-1 text-xs text-muted">Actualizado: {formatTime(summary.computed_at)}.</p>
      </div>
    </div>
  );
}

function PlaceResult({ report }: { report: PlaceReport }) {
  const nothing = report.items.length === 0 && report.warnings.length === 0 && report.alerts.length === 0;
  return (
    <div className="space-y-2">
      {nothing && (
        <p className="rounded-xl border border-border bg-slate-50 p-3 text-sm">
          Este lugar no está dentro de las áreas de tsunami ni de incendios forestales publicadas, y no tiene avisos meteorológicos vigentes.
        </p>
      )}
      {report.items.map((item, i) => (
        <div key={i} className={`rounded-xl border p-3 text-sm ${item.status === "dentro" ? "border-blue-300 bg-blue-50" : "border-border bg-surface"}`}>
          <p>{item.text}</p>
          {item.action && <p className="mt-1 font-semibold">{item.action}</p>}
          <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
            <DataClassBadge dataClass={item.data_class} /> Fuente: {item.source}
          </p>
        </div>
      ))}
      {report.warnings.map((w, i) => (
        <div key={`w${i}`} className={`rounded-xl border p-3 text-sm ${WARNING_TONE[w.level] ?? WARNING_TONE.default}`}>
          <p className="font-semibold">
            {w.level} meteorológico: {w.title}
          </p>
          <p className="text-xs">{w.ends_at ? `Hasta ${formatTime(w.ends_at)}` : "Sin término indicado"}</p>
          {w.source_url && (
            <a href={w.source_url} target="_blank" rel="noreferrer" className="text-xs font-semibold underline">
              Ver el boletín oficial
            </a>
          )}
        </div>
      ))}
      {report.alerts.map((a, i) => (
        <div key={`a${i}`} className={`rounded-xl border p-3 text-sm ${WARNING_TONE[a.level] ?? WARNING_TONE.default}`}>
          <p className="font-semibold">{a.title}</p>
          <p className="text-xs">{a.issuer}</p>
        </div>
      ))}
      <p className="text-xs text-muted">{report.notice}</p>
    </div>
  );
}

function AddressCheck({
  slug,
  point,
  onPoint,
}: {
  slug: string;
  point: { lon: number; lat: number; label?: string } | null;
  onPoint: (p: { lon: number; lat: number; label?: string } | null) => void;
}) {
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [locating, setLocating] = useState<string | null>(null);
  const results = useQuery({
    queryKey: ["public-geocode", slug, submitted],
    queryFn: () => publicGet<GeocodeResult[]>(`/${slug}/geocode?q=${encodeURIComponent(submitted)}`),
    enabled: submitted.length >= 3,
    staleTime: Infinity,
    retry: false,
  });
  const report = useQuery({
    queryKey: ["public-place", slug, point?.lon, point?.lat],
    queryFn: () => publicGet<PlaceReport>(`/${slug}/lugar?lon=${point!.lon}&lat=${point!.lat}`),
    enabled: point !== null,
    retry: false,
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setSubmitted(query.trim());
  }

  function locate() {
    if (!("geolocation" in navigator)) {
      setLocating("Su navegador no permite obtener la ubicación.");
      return;
    }
    setLocating("Buscando su ubicación...");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(null);
        onPoint({ lon: pos.coords.longitude, lat: pos.coords.latitude, label: "Su ubicación" });
      },
      () => setLocating("No se pudo obtener su ubicación. Puede escribir la dirección o tocar el mapa."),
      { enableHighAccuracy: true, timeout: 15000 },
    );
  }

  const reportError = report.error as ApiError | null;
  return (
    <div className="space-y-3">
      <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor="address" className="sr-only">
          Dirección
        </label>
        <input
          id="address"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Calle y número, por ejemplo Pedro Aguirre Cerda 100"
          className="min-w-0 flex-1 rounded-lg border border-border bg-white px-3 py-2.5 text-base outline-none focus:border-brand"
        />
        <button type="submit" disabled={query.trim().length < 3} className="rounded-lg bg-brand px-4 py-2.5 font-semibold text-white disabled:opacity-50">
          Buscar
        </button>
      </form>
      <button type="button" onClick={locate} className="text-sm font-medium text-brand underline">
        Usar mi ubicación actual
      </button>
      {locating && <p className="text-sm text-muted">{locating}</p>}

      {results.isFetching && <p className="text-sm text-muted">Buscando dirección...</p>}
      {results.error && <p className="text-sm text-red-700">{(results.error as Error).message}</p>}
      {results.data && submitted && (
        <div>
          {results.data.length === 0 ? (
            <p className="text-sm text-muted">No encontramos esa dirección en la comuna. Pruebe con otra forma de escribirla o toque el mapa.</p>
          ) : (
            <ul className="divide-y divide-border rounded-xl border border-border text-sm">
              {results.data.map((r, i) => (
                <li key={i}>
                  <button
                    type="button"
                    className="w-full px-3 py-2.5 text-left hover:bg-slate-50"
                    onClick={() => {
                      onPoint({ lon: r.lon, lat: r.lat, label: r.name });
                      setSubmitted("");
                    }}
                  >
                    {r.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {results.data[0] && <p className="mt-1 text-[11px] text-muted">{results.data[0].attribution}</p>}
        </div>
      )}

      {point && (
        <div className="space-y-2 border-t border-border pt-3">
          <p className="text-sm">
            <span className="font-semibold">Lugar revisado:</span> {point.label ?? `${point.lat.toFixed(5)}, ${point.lon.toFixed(5)}`}
          </p>
          {report.isFetching && <p className="text-sm text-muted">Revisando el lugar...</p>}
          {reportError && <p className="text-sm text-red-700">{reportError.status === 422 ? "Ese lugar está fuera de la comuna." : reportError.message}</p>}
          {report.data && <PlaceResult report={report.data} />}
          <button type="button" onClick={() => onPoint(null)} className="text-xs text-muted underline">
            Limpiar
          </button>
        </div>
      )}
    </div>
  );
}

export function PublicPortal({ slug }: { slug: string }) {
  const comuna = useQuery({ queryKey: ["public-comuna", slug], queryFn: () => publicGet<PublicComuna>(`/${slug}/comuna`), retry: false });
  const summary = useQuery({
    queryKey: ["public-summary", slug],
    queryFn: () => publicGet<PublicSummary>(`/${slug}/resumen`),
    refetchInterval: 300_000,
    enabled: comuna.isSuccess,
  });
  const [point, setPoint] = useState<{ lon: number; lat: number; label?: string } | null>(null);
  const pick = useCallback((lon: number, lat: number) => setPoint({ lon, lat }), []);
  const place = useQuery({
    queryKey: ["public-place", slug, point?.lon, point?.lat],
    queryFn: () => publicGet<PlaceReport>(`/${slug}/lugar?lon=${point!.lon}&lat=${point!.lat}`),
    enabled: point !== null,
    retry: false,
  });
  const meeting = place.data?.items.find((i) => i.meeting_point)?.meeting_point ?? null;

  if (comuna.isLoading) return <p className="p-6 text-sm text-muted">Cargando...</p>;
  if (comuna.error || !comuna.data) {
    const status = (comuna.error as ApiError | null)?.status;
    return <p className="p-6 text-sm text-red-700">{status === 404 ? "No encontramos esta comuna." : "No se pudo cargar la información. Intente más tarde."}</p>;
  }
  const c = comuna.data;
  const brandStyle = c.primary_color ? ({ "--brand": c.primary_color } as React.CSSProperties) : undefined;

  return (
    <div className="min-h-full bg-background" style={brandStyle}>
      <header className="bg-brand text-white">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-4">
          {c.logo_url ? (
            <img src={c.logo_url} alt="" className="h-12 w-12 rounded-lg bg-white object-contain p-1" />
          ) : (
            <span className="flex h-12 w-12 items-center justify-center rounded-lg bg-white/15 text-lg font-bold">{c.name.slice(0, 2).toUpperCase()}</span>
          )}
          <div>
            <h1 className="text-xl font-semibold leading-tight">{c.display_name}</h1>
            <p className="text-sm opacity-90">Información sobre riesgos de desastre para la comunidad de {c.name}</p>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-4 py-4">
        <p className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
          Esta página reúne información oficial de SENAPRED y de la Dirección Meteorológica de Chile, y un cálculo de referencia hecho por la plataforma.
          No reemplaza las instrucciones de la autoridad. <span className="font-semibold">En una emergencia, siga las indicaciones de SENAPRED y de su municipalidad.</span>
        </p>

        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <div className="space-y-4">
            <Section title="Qué está pasando ahora" id="ahora">
              {summary.isLoading && <p className="text-sm text-muted">Cargando situación actual...</p>}
              {summary.error && <p className="text-sm text-red-700">{(summary.error as Error).message}</p>}
              {summary.data && <CurrentSituation summary={summary.data} />}
            </Section>

            <Section title="¿Mi casa está en una zona de riesgo?" id="lugar">
              <p className="mb-3 text-sm text-muted">Escriba su dirección, use su ubicación o toque el mapa para ver si el lugar está en un área de evacuación por tsunami, su recurrencia de incendios forestales y los avisos vigentes.</p>
              <AddressCheck slug={slug} point={point} onPoint={setPoint} />
            </Section>
          </div>

          <div className="lg:sticky lg:top-4 lg:h-[calc(100vh-2rem)]">
            <PublicMap slug={slug} comuna={c} point={point} meetingPoint={point ? meeting : null} onPick={pick} />
          </div>
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <Section title="Teléfonos de emergencia" id="telefonos">
            <ul className="grid grid-cols-3 gap-2">
              {EMERGENCY_PHONES.map((p) => (
                <li key={p.number}>
                  <a href={`tel:${p.number}`} className="flex flex-col items-center rounded-xl border border-border p-3 text-center hover:bg-slate-50">
                    <span className="text-2xl font-bold text-brand">{p.number}</span>
                    <span className="text-xs text-muted">{p.label}</span>
                  </a>
                </li>
              ))}
            </ul>
          </Section>
          <Section title="Información oficial" id="enlaces">
            <ul className="space-y-2 text-sm">
              {OFFICIAL_LINKS.map((l) => (
                <li key={l.href}>
                  <a href={l.href} target="_blank" rel="noreferrer" className="font-semibold text-brand underline">
                    {l.label}
                  </a>
                  <span className="block text-xs text-muted">{l.detail}</span>
                </li>
              ))}
            </ul>
          </Section>
        </div>

        <footer className="mt-6 border-t border-border pb-8 pt-4 text-xs text-muted">
          <p>Fuentes: SENAPRED, Dirección Meteorológica de Chile, CONAF. Mapa base © OpenStreetMap y OpenFreeMap.</p>
          <p className="mt-1">
            <a href="/" className="underline">
              Acceso para funcionarios municipales
            </a>
          </p>
        </footer>
      </div>
    </div>
  );
}
