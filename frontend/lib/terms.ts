import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { Me } from "@/lib/types";

export const TERM_LABELS: Record<string, string> = {
  tab_ahora: "Pestaña Ahora",
  tab_riesgo: "Pestaña Riesgo",
  tab_planificar: "Pestaña Planificar",
  tab_asistente: "Pestaña Asistente",
  tab_informes: "Pestaña Informes",
  tab_datos: "Pestaña Datos municipales",
  tab_fuentes: "Pestaña Fuentes",
  tab_config: "Pestaña Configuración",
  sector: "Nombre de un sector (singular)",
  sectores: "Nombre de los sectores (plural)",
};

export function useTerms() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => apiGet<Me>("/me") });
  const terminology = me.data?.municipality.config.terminology ?? {};
  return (key: string, fallback: string) => terminology[key] || fallback;
}
