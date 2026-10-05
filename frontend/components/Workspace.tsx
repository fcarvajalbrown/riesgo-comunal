"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { MapView, type MapFocus } from "@/components/MapView";
import { AhoraPanel } from "@/components/panels/AhoraPanel";
import { AssistantPanel } from "@/components/panels/AssistantPanel";
import { ConfigPanel } from "@/components/panels/ConfigPanel";
import { DataPanel } from "@/components/panels/DataPanel";
import { PlanificarPanel } from "@/components/panels/PlanificarPanel";
import { ReportsPanel } from "@/components/panels/ReportsPanel";
import { RiesgoPanel } from "@/components/panels/RiesgoPanel";
import { SourcesPanel } from "@/components/panels/SourcesPanel";
import { apiGet } from "@/lib/api";
import { ROLE_LABEL } from "@/lib/format";
import { getTenantOverride, setTenantOverride, setToken } from "@/lib/session";
import type { Me } from "@/lib/types";

type Tab = "ahora" | "riesgo" | "planificar" | "asistente" | "informes" | "datos" | "fuentes" | "config";

const TABS: { key: Tab; label: string; hint: string }[] = [
  { key: "ahora", label: "Ahora", hint: "¿Qué está pasando?" },
  { key: "riesgo", label: "Riesgo", hint: "¿Qué zonas son vulnerables?" },
  { key: "planificar", label: "Planificar", hint: "Historia y prioridades" },
  { key: "asistente", label: "Asistente", hint: "Pregunte en lenguaje natural" },
  { key: "informes", label: "Informes", hint: "Por rol, en PDF" },
  { key: "datos", label: "Datos municipales", hint: "Cargar información" },
  { key: "fuentes", label: "Fuentes", hint: "Origen de los datos" },
  { key: "config", label: "Configuración", hint: "Umbrales y alertas" },
];

const ROLE_TABS: Record<string, Tab[]> = {
  ALCALDE: ["ahora", "riesgo", "planificar", "asistente", "informes", "fuentes"],
  COMUNICACIONES: ["informes", "ahora", "riesgo", "asistente", "fuentes"],
  SECPLAN: ["planificar", "riesgo", "ahora", "asistente", "informes", "datos", "fuentes"],
  EMERGENCIAS: ["ahora", "riesgo", "planificar", "asistente", "informes", "datos", "fuentes", "config"],
  VIEWER: ["ahora", "riesgo", "planificar", "asistente", "fuentes"],
};

const MAP_LAYERS: Partial<Record<Tab, string[]>> = {
  ahora: ["comuna", "dmc_warning", "aq_station", "earthquake", "school", "health_facility"],
  riesgo: ["comuna", "sectors", "school", "health_facility"],
  planificar: ["comuna", "wildfire_hazard", "tsunami_evacuation_area", "municipal_incident"],
};

export function Workspace() {
  const queryClient = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: () => apiGet<Me>("/me") });
  const role = me.data?.user.role ?? "VIEWER";
  const tabs = (ROLE_TABS[role] ?? TABS.map((t) => t.key)).map((k) => TABS.find((t) => t.key === k)!);
  const [tab, setTab] = useState<Tab | null>(null);
  const current = tab ?? tabs[0]?.key ?? "ahora";
  const [focus, setFocus] = useState<MapFocus | null>(null);
  const [sector, setSector] = useState<number | null>(null);
  const onSectorClick = useCallback((id: number) => {
    setSector(id);
    setTab("riesgo");
  }, []);

  if (me.isLoading) return <p className="p-6 text-sm text-muted">Cargando...</p>;
  if (me.error || !me.data) {
    return (
      <div className="p-6 text-sm">
        <p className="text-red-700">{(me.error as Error)?.message ?? "No se pudo cargar la sesión"}</p>
        <button onClick={() => setToken(null)} className="mt-2 text-brand underline">
          Volver a ingresar
        </button>
      </div>
    );
  }
  const m = me.data;
  const withMap = current in MAP_LAYERS;
  const can = (p: string) => m.permissions.includes(p);

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl text-sm font-bold text-white" style={{ background: m.municipality.config.branding.primary_color }}>
              RC
            </div>
            <div>
              <p className="text-sm font-semibold leading-tight">{m.municipality.config.branding.display_name ?? `Municipalidad de ${m.municipality.name}`}</p>
              <p className="text-xs leading-tight text-muted">{m.municipality.region ? `Región del ${m.municipality.region}` : ""}</p>
            </div>
          </div>
          {m.municipalities.length > 1 && (
            <select
              value={getTenantOverride() ?? String(m.municipality.id)}
              onChange={(e) => {
                setTenantOverride(e.target.value);
                queryClient.clear();
              }}
              className="rounded-lg border border-border px-2 py-1 text-sm"
            >
              {m.municipalities.map((x) => (
                <option key={x.id} value={x.id}>
                  {x.name}
                </option>
              ))}
            </select>
          )}
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span className="hidden text-right sm:block">
              <span className="block leading-tight">{m.user.name}</span>
              <span className="block text-xs leading-tight text-muted">{ROLE_LABEL[m.user.role] ?? m.user.role}</span>
            </span>
            <button
              onClick={() => {
                setToken(null);
                queryClient.clear();
              }}
              className="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-slate-50"
            >
              Salir
            </button>
          </div>
        </div>
        <nav className="mx-auto flex max-w-[1600px] gap-1 overflow-x-auto px-3">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`whitespace-nowrap border-b-2 px-3 py-2.5 text-sm ${current === t.key ? "border-brand font-semibold text-brand" : "border-transparent text-muted hover:text-foreground"}`}
              title={t.hint}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="mx-auto w-full max-w-[1600px] flex-1 overflow-hidden px-4 py-4">
        {withMap ? (
          <div className="flex h-full flex-col gap-4 lg:flex-row">
            <div className="order-2 min-h-0 flex-none overflow-y-auto pr-1 lg:order-1 lg:h-full lg:w-[460px]">
              {current === "ahora" && <AhoraPanel onFocus={setFocus} compact={role === "ALCALDE"} />}
              {current === "riesgo" && <RiesgoPanel onFocus={setFocus} selectedSector={sector} onSelectSector={setSector} />}
              {current === "planificar" && <PlanificarPanel onFocus={setFocus} />}
            </div>
            <div className="order-1 h-[50vh] flex-1 lg:order-2 lg:h-full">
              <MapView key={`${m.municipality.id}-${current}`} me={m} defaultLayers={MAP_LAYERS[current]} focus={focus} onSectorClick={onSectorClick} />
            </div>
          </div>
        ) : (
          <div className="mx-auto h-full max-w-4xl overflow-y-auto pb-6">
            {current === "asistente" && <AssistantPanel />}
            {current === "informes" && <ReportsPanel role={role} />}
            {current === "datos" && <DataPanel canUpload={can("upload")} />}
            {current === "fuentes" && <SourcesPanel canRun={can("source:run")} />}
            {current === "config" && <ConfigPanel canConfigure={can("configure")} canAlert={can("alert:create")} />}
          </div>
        )}
      </main>

      <footer className="border-t border-border bg-surface px-4 py-2 text-center text-[11px] text-muted">
        Plataforma municipal de información. No es SENAPRED ni un sistema oficial de alertas. Los niveles son cálculos de la plataforma; que no haya alerta no significa que no haya
        peligro. Alertas oficiales en{" "}
        <a href="https://senapred.cl" target="_blank" rel="noreferrer" className="underline">
          senapred.cl
        </a>
        .
      </footer>
    </div>
  );
}
