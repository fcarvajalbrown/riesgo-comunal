"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { formatTime } from "@/lib/format";
import { TERM_LABELS } from "@/lib/terms";
import type { Alert, Me } from "@/lib/types";

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

function BrandingEditor() {
  const queryClient = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: () => apiGet<Me>("/me") });
  const config = me.data?.municipality.config;
  const [name, setName] = useState<string | null>(null);
  const [color, setColor] = useState<string | null>(null);
  const [terms, setTerms] = useState<Record<string, string> | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () =>
      apiSend("/municipality/config", "PUT", {
        branding: { display_name: name ?? config?.branding.display_name ?? null, primary_color: color ?? config?.branding.primary_color },
        terminology: terms ?? config?.terminology ?? {},
      }),
    onSuccess: () => {
      setMessage("Guardado.");
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
    onError: (e) => setMessage((e as Error).message),
  });
  const logo = useMutation({
    mutationFn: (file: File | null) => {
      if (!file) return apiSend("/municipality/logo", "DELETE");
      const form = new FormData();
      form.set("file", file);
      return apiSend("/municipality/logo", "PUT", form);
    },
    onSuccess: () => {
      setMessage("Logo actualizado.");
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
    onError: (e) => setMessage((e as Error).message),
  });
  if (!config) return null;
  const currentTerms = terms ?? config.terminology ?? {};
  return (
    <div className="rounded-2xl border border-border bg-surface p-4 text-sm shadow-sm">
      <h3 className="text-base font-semibold">Identidad de la comuna</h3>
      <p className="mt-0.5 text-muted">Nombre, color, logo y términos que verá su equipo. Los cambios quedan registrados en la auditoría.</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="block">
          Nombre visible
          <input
            value={name ?? config.branding.display_name ?? ""}
            onChange={(e) => setName(e.target.value)}
            placeholder={`Municipalidad de ${me.data?.municipality.name}`}
            className="mt-1 w-full rounded-lg border border-border px-3 py-2"
          />
        </label>
        <label className="block">
          Color principal
          <input type="color" value={color ?? config.branding.primary_color} onChange={(e) => setColor(e.target.value)} className="mt-1 h-10 w-full rounded-lg border border-border" />
        </label>
      </div>
      <div className="mt-3">
        <p>Logo (PNG o JPEG, hasta 1 MB)</p>
        <div className="mt-1 flex items-center gap-3">
          {config.branding.logo_url && <img src={config.branding.logo_url} alt="Logo actual" className="h-10 w-10 rounded-lg border border-border object-contain" />}
          <input type="file" accept=".png,.jpg,.jpeg" onChange={(e) => e.target.files?.[0] && logo.mutate(e.target.files[0])} className="text-sm" />
          {config.branding.logo_url && (
            <button type="button" onClick={() => logo.mutate(null)} className="text-xs text-red-700 hover:underline">
              Quitar logo
            </button>
          )}
        </div>
      </div>
      <details className="mt-3">
        <summary className="cursor-pointer font-medium">Términos propios de la comuna</summary>
        <p className="mt-1 text-xs text-muted">Deje en blanco para usar el término estándar.</p>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {Object.entries(TERM_LABELS).map(([key, label]) => (
            <label key={key} className="block text-xs">
              {label}
              <input
                value={currentTerms[key] ?? ""}
                maxLength={40}
                onChange={(e) => setTerms({ ...currentTerms, [key]: e.target.value })}
                className="mt-0.5 w-full rounded-lg border border-border px-2 py-1.5 text-sm"
              />
            </label>
          ))}
        </div>
      </details>
      <div className="mt-3 flex items-center gap-3">
        <button onClick={() => save.mutate()} disabled={save.isPending} className="rounded-lg bg-brand px-4 py-2 font-medium text-white disabled:opacity-50">
          Guardar identidad
        </button>
        {message && <span className="text-xs text-muted">{message}</span>}
      </div>
    </div>
  );
}

export function ConfigPanel({ canConfigure, canAlert }: { canConfigure: boolean; canAlert: boolean }) {
  const hazards = useQuery({ queryKey: ["hazards"], queryFn: () => apiGet<HazardRow[]>("/hazards") });
  return (
    <div className="space-y-4">
      {canAlert && <AlertForm />}
      {canConfigure ? (
        <>
          <BrandingEditor />
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
