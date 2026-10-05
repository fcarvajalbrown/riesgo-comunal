"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { apiGet } from "@/lib/api";
import { formatTime } from "@/lib/format";

interface ProvenanceDetail {
  id: number;
  dataset: string;
  url: string | null;
  source_time: string | null;
  acquired_at: string | null;
  ingested_at: string | null;
  transformation: string | null;
  version: string | null;
  source_name: string | null;
  organization: string | null;
  license: string | null;
  commercial_use: string | null;
  authority: string | null;
  attribution: string | null;
  job_status: string | null;
  job_records: number | null;
  upload_filename: string | null;
  uploaded_at: string | null;
  upload_is_demo: boolean | null;
  uploaded_by: string | null;
}

export function ProvenanceButton({ id, label = "¿De dónde salió este dato?" }: { id: number | null | undefined; label?: string }) {
  const [open, setOpen] = useState(false);
  if (!id) return null;
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="text-xs font-medium text-brand underline-offset-2 hover:underline">
        {label}
      </button>
      {open && <ProvenanceDialog id={id} onClose={() => setOpen(false)} />}
    </>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="grid grid-cols-[9rem_1fr] gap-2 py-1.5 text-sm">
      <dt className="text-muted">{label}</dt>
      <dd className="break-words">{value}</dd>
    </div>
  );
}

function ProvenanceDialog({ id, onClose }: { id: number; onClose: () => void }) {
  const { data, isLoading, error } = useQuery({ queryKey: ["provenance", id], queryFn: () => apiGet<ProvenanceDetail>(`/provenance/${id}`) });
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" onClick={onClose}>
      <div role="dialog" aria-modal className="max-h-[85vh] w-full max-w-lg overflow-auto rounded-2xl bg-surface p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-start justify-between gap-4">
          <h2 className="text-lg font-semibold">Origen del dato</h2>
          <button onClick={onClose} className="rounded-md px-2 py-1 text-sm text-muted hover:bg-slate-100">
            Cerrar
          </button>
        </div>
        {isLoading && <p className="text-sm text-muted">Cargando...</p>}
        {error && <p className="text-sm text-red-700">{(error as Error).message}</p>}
        {data && (
          <dl className="divide-y divide-border">
            {data.upload_filename ? (
              <>
                <Row label="Fuente" value={`Registro municipal${data.upload_is_demo ? " (DEMO, datos de ejemplo)" : ""}`} />
                <Row label="Archivo" value={data.upload_filename} />
                <Row label="Cargado por" value={data.uploaded_by} />
                <Row label="Fecha de carga" value={formatTime(data.uploaded_at)} />
              </>
            ) : (
              <>
                <Row label="Fuente" value={data.source_name} />
                <Row label="Organismo" value={data.organization} />
                <Row label="Autoridad" value={data.authority} />
                <Row label="Conjunto de datos" value={data.dataset} />
                <Row
                  label="Servicio"
                  value={
                    data.url ? (
                      <a href={data.url} target="_blank" rel="noreferrer" className="text-brand underline">
                        {data.url}
                      </a>
                    ) : null
                  }
                />
                <Row label="Fecha en la fuente" value={data.source_time ? formatTime(data.source_time) : "La fuente no informa fecha"} />
                <Row label="Descargado" value={formatTime(data.acquired_at)} />
                <Row label="Licencia" value={data.license} />
                <Row label="Uso comercial" value={data.commercial_use} />
                <Row label="Registros" value={data.job_records} />
              </>
            )}
            <Row label="Transformación" value={data.transformation} />
            <Row label="Versión" value={data.version} />
          </dl>
        )}
      </div>
    </div>
  );
}
