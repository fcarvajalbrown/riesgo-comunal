import type { DataClass, Level } from "@/lib/types";

export const LEVEL_STYLE: Record<Level, { bg: string; fg: string; ring: string; hex: string; label: string }> = {
  CRITICO: { bg: "bg-red-700", fg: "text-white", ring: "ring-red-200", hex: "#b42318", label: "Crítico" },
  ALTO: { bg: "bg-orange-600", fg: "text-white", ring: "ring-orange-200", hex: "#d4590f", label: "Alto" },
  MODERADO: { bg: "bg-yellow-400", fg: "text-yellow-950", ring: "ring-yellow-200", hex: "#e3b505", label: "Moderado" },
  BAJO: { bg: "bg-green-700", fg: "text-white", ring: "ring-green-200", hex: "#2f7d4a", label: "Bajo" },
  INFORMATIVO: { bg: "bg-blue-700", fg: "text-white", ring: "ring-blue-200", hex: "#2b5ea7", label: "Informativo" },
  SIN_DATOS: { bg: "bg-slate-400", fg: "text-white", ring: "ring-slate-200", hex: "#8a929c", label: "Sin datos" },
};

export const LEVEL_ICON: Record<Level, string> = {
  CRITICO: "!!",
  ALTO: "!",
  MODERADO: "~",
  BAJO: "-",
  INFORMATIVO: "i",
  SIN_DATOS: "?",
};

export const DATA_CLASS_STYLE: Record<DataClass, { label: string; className: string }> = {
  official: { label: "Oficial", className: "bg-sky-50 text-sky-800 border-sky-200" },
  observed: { label: "Observado", className: "bg-emerald-50 text-emerald-800 border-emerald-200" },
  forecast: { label: "Pronóstico", className: "bg-violet-50 text-violet-800 border-violet-200" },
  official_warning: { label: "Alerta oficial", className: "bg-red-50 text-red-800 border-red-200" },
  historical: { label: "Histórico", className: "bg-amber-50 text-amber-800 border-amber-200" },
  municipal: { label: "Municipal", className: "bg-teal-50 text-teal-800 border-teal-200" },
  derived: { label: "Cálculo de la plataforma", className: "bg-slate-100 text-slate-700 border-slate-300" },
  estimated: { label: "Estimado", className: "bg-orange-50 text-orange-800 border-orange-200" },
  modelled: { label: "Modelado", className: "bg-indigo-50 text-indigo-800 border-indigo-200" },
  international: { label: "Aviso internacional", className: "bg-stone-100 text-stone-700 border-stone-300" },
};

const chile = new Intl.DateTimeFormat("es-CL", {
  timeZone: "America/Santiago",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});
const utc = new Intl.DateTimeFormat("es-CL", { timeZone: "UTC", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });

export function formatTime(value: string | null | undefined): string {
  if (!value) return "sin fecha";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${chile.format(date)} hora de Chile (${utc.format(date)} UTC)`;
}

export function formatShortTime(value: string | null | undefined): string {
  if (!value) return "sin fecha";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return chile.format(date);
}

export const ROLE_LABEL: Record<string, string> = {
  SUPER_ADMIN: "Administración plataforma",
  MUNICIPAL_ADMIN: "Administración municipal",
  ALCALDE: "Alcaldía",
  EMERGENCIAS: "Emergencias",
  SECPLAN: "SECPLAN",
  COMUNICACIONES: "Comunicaciones",
  VIEWER: "Consulta",
};

export const WARNING_TONE: Record<string, string> = {
  Alarma: "border-red-300 bg-red-50 text-red-950",
  Alerta: "border-orange-300 bg-orange-50 text-orange-950",
  Aviso: "border-yellow-300 bg-yellow-50 text-yellow-950",
  "Alerta Roja": "border-red-300 bg-red-50 text-red-950",
  "Alerta Amarilla": "border-yellow-400 bg-yellow-50 text-yellow-950",
  "Alerta Temprana Preventiva": "border-green-300 bg-green-50 text-green-950",
  default: "border-red-200 bg-red-50 text-red-950",
};
