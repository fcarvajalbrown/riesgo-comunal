"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { formatTime } from "@/lib/format";
import type { Alert } from "@/lib/types";

interface HazardRow {
  key: string;
  name: string;
  description: string;
  enabled: boolean;
  thresholds: Record<string, number | string>;
  default_thresholds: Record<string, number | string>;
}

const THRESHOLD_LABELS: Record<string, string> = {
  high_share_critico: "Fracción del área en recurrencia alta para nivel Crítico",
  high_share_alto: "Fracción del área en recurrencia alta para nivel Alto",
  mid_share_moderado: "Fracción del área en recurrencia media para nivel Moderado",
  level_if_in_evacuation_area: "Nivel si el área está dentro de zona a evacuar",
  years: "Años de historia considerados",
  incidents_moderado: "Incidentes para nivel Moderado",
  incidents_alto: "Incidentes para nivel Alto",
  flood_point_buffer_m: "Radio de puntos críticos (m)",
  alerta: "MP2,5 alerta (µg/m³)",
  preemergencia: "MP2,5 preemergencia (µg/m³)",
  emergencia: "MP2,5 emergencia (µg/m³)",
  min_hours: "Horas mínimas con datos",
  station_radius_km: "Radio de estaciones (km)",
  radius_km: "Radio de búsqueda (km)",
  min_magnitude: "Magnitud mínima",
  hours: "Ventana (horas)",
  rain_24h_moderado: "Lluvia 24 h para Moderado (mm, provisional)",
  rain_24h_alto: "Lluvia 24 h para Alto (mm, provisional)",
};

function HazardEditor({ hazard }: { hazard: HazardRow }) {
  const queryClient = useQueryClient();
  const [values, setValues] = useState<Record<string, string>>(Object.fromEntries(Object.entries(hazard.thresholds).map(([k, v]) => [k, String(v)])));
  const [enabled, setEnabled] = useState(hazard.enabled);
  const save = useMutation({
    mutationFn: () => {
      const thresholds = Object.fromEntries(Object.entries(values).map(([k, v]) => [k, typeof hazard.default_thresholds[k] === "number" ? Number(v) : v]));
      return apiSend("/municipality/config", "PUT", { hazards: { [hazard.key]: { enabled, thresholds } } });
    },
    onSuccess: () => queryClient.invalidateQueries(),
  });
  return (
    <article className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h4 className="font-semibold">{hazard.name}</h4>
          <p className="text-xs text-muted">{hazard.description}</p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          Activo
        </label>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {Object.entries(values).map(([k, v]) => (
          <label key={k} className="text-xs">
            <span className="text-muted">{THRESHOLD_LABELS[k] ?? k}</span>
            <input value={v} onChange={(e) => setValues({ ...values, [k]: e.target.value })} className="mt-0.5 w-full rounded-md border border-border px-2 py-1 font-mono text-sm" />
            <span className="text-[10px] text-muted">por defecto {String(hazard.default_thresholds[k])}</span>
          </label>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-3">
        <button onClick={() => save.mutate()} disabled={save.isPending} className="rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50">
          Guardar
        </button>
        {save.isSuccess && <span className="text-xs text-green-800">Guardado. Los niveles se recalculan con estos umbrales.</span>}
        {save.isError && <span className="text-xs text-red-700">{(save.error as Error).message}</span>}
      </div>
    </article>
  );
}

function AlertForm() {
  const queryClient = useQueryClient();
  const alerts = useQuery({ queryKey: ["alerts"], queryFn: () => apiGet<Alert[]>("/alerts") });
  const [form, setForm] = useState({ issuer: "SENAPRED", hazard: "", level: "", title: "", description: "", source_url: "", starts_at: "" });
  const create = useMutation({
    mutationFn: () => apiSend("/alerts", "POST", { ...form, starts_at: new Date(form.starts_at || Date.now()).toISOString(), description: form.description || null }),
    onSuccess: () => {
      setForm({ ...form, title: "", description: "", source_url: "" });
      queryClient.invalidateQueries();
    },
  });
  const end = useMutation({ mutationFn: (id: number) => apiSend(`/alerts/${id}/end`, "POST"), onSuccess: () => queryClient.invalidateQueries() });
  const field = (key: keyof typeof form, label: string, type = "text") => (
    <label className="text-xs">
      <span className="text-muted">{label}</span>
      <input
        type={type}
        required={key !== "description"}
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        className="mt-0.5 w-full rounded-md border border-border px-2 py-1.5 text-sm"
      />
    </label>
  );
  return (
    <section className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
      <h3 className="text-base font-semibold">Registrar alerta oficial</h3>
      <p className="mt-0.5 text-xs text-muted">
        Sólo para alertas emitidas por un organismo oficial. El enlace a la publicación oficial es obligatorio y se muestra junto a la alerta. La plataforma no crea alertas propias.
      </p>
      <form
        className="mt-3 grid gap-2 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        {field("issuer", "Organismo emisor")}
        {field("hazard", "Amenaza")}
        {field("level", "Nivel según el organismo (p. ej. Alerta Roja)")}
        {field("title", "Título")}
        {field("source_url", "Enlace oficial (https://...)", "url")}
        {field("starts_at", "Inicio", "datetime-local")}
        <label className="text-xs sm:col-span-2">
          <span className="text-muted">Descripción</span>
          <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="mt-0.5 w-full rounded-md border border-border px-2 py-1.5 text-sm" />
        </label>
        <div className="sm:col-span-2">
          <button disabled={create.isPending} className="rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50">
            Registrar alerta
          </button>
          {create.isError && <span className="ml-3 text-xs text-red-700">{(create.error as Error).message}</span>}
        </div>
      </form>
      <ul className="mt-4 divide-y divide-border">
        {alerts.data?.map((a) => {
          const active = !a.ends_at || new Date(a.ends_at) > new Date();
          return (
            <li key={a.id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
              <span className="font-medium">{a.title}</span>
              <span className="text-xs text-muted">
                {a.issuer} · {formatTime(a.starts_at)} · {active ? "vigente" : "finalizada"}
              </span>
              {active && (
                <button onClick={() => end.mutate(a.id)} className="ml-auto text-xs text-red-700 hover:underline">
                  Finalizar
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function ConfigPanel({ canConfigure, canAlert }: { canConfigure: boolean; canAlert: boolean }) {
  const hazards = useQuery({ queryKey: ["hazards"], queryFn: () => apiGet<HazardRow[]>("/hazards") });
  return (
    <div className="space-y-4">
      {canAlert && <AlertForm />}
      {canConfigure ? (
        <>
          <div className="rounded-2xl border border-border bg-surface p-4 text-sm shadow-sm">
            <h3 className="text-base font-semibold">Amenazas y umbrales</h3>
            <p className="mt-0.5 text-muted">
              Cada amenaza es un módulo que puede activarse o desactivarse. Los umbrales definen cómo la plataforma calcula los niveles; los cambios quedan registrados en la auditoría.
            </p>
          </div>
          {hazards.data?.map((h) => (
            <HazardEditor key={h.key} hazard={h} />
          ))}
        </>
      ) : (
        !canAlert && <p className="text-sm text-muted">Su rol no tiene opciones de configuración.</p>
      )}
    </div>
  );
}
