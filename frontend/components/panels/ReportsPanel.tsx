"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { DataClassBadge, LevelBadge } from "@/components/Badges";
import { apiDownload, apiGet } from "@/lib/api";
import type { Report } from "@/lib/types";

const ROLE_FOR_REPORT: Record<string, string> = {
  ALCALDE: "alcalde",
  EMERGENCIAS: "emergencias",
  SECPLAN: "secplan",
  COMUNICACIONES: "comunicaciones",
};

export function ReportsPanel({ role }: { role: string }) {
  const list = useQuery({ queryKey: ["reports"], queryFn: () => apiGet<{ role: string; title: string }[]>("/reports") });
  const [selected, setSelected] = useState(ROLE_FOR_REPORT[role] ?? "alcalde");
  const report = useQuery({ queryKey: ["report", selected], queryFn: () => apiGet<Report>(`/reports/${selected}`) });
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    setDownloading(true);
    setError(null);
    try {
      await apiDownload(`/reports/${selected}/pdf`, `informe-${selected}.pdf`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {list.data?.map((r) => (
          <button
            key={r.role}
            onClick={() => setSelected(r.role)}
            className={`rounded-full border px-3 py-1.5 text-sm ${selected === r.role ? "border-brand bg-brand text-white" : "border-border bg-surface hover:bg-slate-50"}`}
          >
            {r.title}
          </button>
        ))}
        <button onClick={download} disabled={downloading} className="ml-auto rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white disabled:opacity-60">
          {downloading ? "Generando PDF..." : "Descargar PDF"}
        </button>
      </div>
      {error && <p className="text-sm text-red-700">{error}</p>}
      {report.isLoading && <p className="text-sm text-muted">Preparando informe...</p>}
      {report.data && (
        <article className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
          <header className="border-b border-border pb-3">
            <h2 className="text-xl font-semibold">{report.data.title}</h2>
            <p className="text-sm text-muted">
              Comuna de {report.data.municipality} · Generado {report.data.generated_at_local}
            </p>
            <div className="mt-2 flex items-center gap-2 text-sm">
              Nivel general calculado: <LevelBadge level={report.data.overall_level} size="sm" />
              <span className="text-xs text-muted">cálculo de la plataforma</span>
            </div>
          </header>
          {report.data.sections.map((section) => (
            <section key={section.title} className="mt-4">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-brand">{section.title}</h3>
              <ul className="mt-2 space-y-1.5">
                {section.items.map((item, i) => (
                  <li key={i} className="text-sm">
                    <span className={item.text.startsWith("   ") ? "ml-4 inline-block" : ""}>{item.text.trim()}</span>
                    {(item.data_class || item.source) && (
                      <span className="ml-2 inline-flex flex-wrap items-center gap-1 align-middle">
                        <DataClassBadge dataClass={item.data_class} />
                        {item.source && item.source !== item.data_class_label && <span className="text-[11px] text-muted">{item.source}</span>}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          ))}
          <section className="mt-5 border-t border-border pt-3">
            <h3 className="text-sm font-semibold">Fuentes</h3>
            <ul className="mt-1 text-xs text-muted">
              {report.data.sources.map((s) => (
                <li key={s.source}>
                  {s.source}
                  {s.updated_at_local ? ` (actualizado ${s.updated_at_local})` : ""}
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs italic text-muted">{report.data.disclaimer}</p>
          </section>
        </article>
      )}
    </div>
  );
}
