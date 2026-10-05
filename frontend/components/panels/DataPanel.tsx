"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { DemoBadge } from "@/components/Badges";
import { apiGet, apiObjectUrl, apiSend } from "@/lib/api";
import { formatShortTime } from "@/lib/format";

interface UploadRow {
  id: number;
  filename: string;
  kind: string;
  category: string | null;
  size_bytes: number;
  status: string;
  record_count: number;
  error: string | null;
  is_demo: boolean;
  uploaded_at: string;
  uploaded_by: string | null;
}

const KINDS = [
  { key: "assets", label: "Infraestructura y recursos", hint: "CSV con columnas nombre, categoria, latitud, longitud; o GeoJSON, KML/KMZ, shapefile en .zip (con su .prj) o GeoPackage. Coordenadas UTM se convierten solas.", accept: ".csv,.geojson,.json,.kml,.kmz,.zip,.gpkg" },
  { key: "incidents", label: "Incidentes históricos", hint: "Columnas fecha (AAAA-MM-DD), amenaza, sector, descripcion, afectados y coordenadas opcionales. También shapefile en .zip o GeoPackage.", accept: ".csv,.geojson,.json,.kml,.kmz,.zip,.gpkg" },
  { key: "sectors", label: "Sectores del municipio", hint: "Polígonos en GeoJSON, KML, shapefile en .zip o GeoPackage, con la propiedad nombre. Reemplazan las celdas de análisis.", accept: ".geojson,.json,.kml,.kmz,.zip,.gpkg" },
  { key: "raster", label: "Capas raster (GeoTIFF)", hint: "GeoTIFF con su proyección (por ejemplo un mapa de amenaza municipal o un modelo de elevación). Se muestra como capa en el mapa.", accept: ".tif,.tiff" },
  { key: "contacts", label: "Contactos y personal", hint: "CSV con columnas nombre, cargo, institucion, telefono, email y tipo (contacto o personal).", accept: ".csv" },
  { key: "inspections", label: "Inspecciones", hint: "CSV con columnas fecha, activo (nombre igual al de la infraestructura cargada), estado, observaciones, inspector.", accept: ".csv" },
  { key: "photo", label: "Fotografías", hint: "JPEG, PNG o WebP. Puede asociarla a un activo municipal.", accept: ".jpg,.jpeg,.png,.webp" },
  { key: "document", label: "Documentos", hint: "PDF con texto (planes, protocolos). El asistente podrá citarlos.", accept: ".pdf,.txt,.md" },
] as const;

const CATEGORIES = ["albergue", "punto critico inundacion", "generador", "estanque de agua", "puente", "sumidero", "grifo", "maquinaria", "vehiculo municipal", "ruta de evacuacion"];
const KIND_LABEL: Record<string, string> = {
  assets: "Infraestructura",
  incidents: "Incidentes",
  sectors: "Sectores",
  document: "Documento",
  raster: "Capa raster",
  contacts: "Contactos",
  inspections: "Inspecciones",
  photo: "Fotografía",
};

interface AssetFeature {
  id: number;
  properties: { name: string; category: string };
}

export function DataPanel({ canUpload }: { canUpload: boolean }) {
  const queryClient = useQueryClient();
  const uploads = useQuery({ queryKey: ["uploads"], queryFn: () => apiGet<UploadRow[]>("/uploads") });
  const [kind, setKind] = useState<(typeof KINDS)[number]["key"]>("assets");
  const [category, setCategory] = useState("");
  const [title, setTitle] = useState("");
  const [assetId, setAssetId] = useState("");
  const assets = useQuery({
    queryKey: ["layer", "municipal_asset"],
    queryFn: () => apiGet<{ features: AssetFeature[] }>("/layers/municipal_asset"),
    enabled: kind === "photo",
  });
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const upload = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.set("kind", kind);
      if (category) form.set("category", category);
      if (title) form.set("title", title);
      if (kind === "photo" && assetId) form.set("asset_id", assetId);
      form.set("file", file as File);
      return apiSend<{ status: string; records?: number; error?: string }>("/uploads", "POST", form);
    },
    onSuccess: (r) => {
      setMessage(r.status === "done" ? { ok: true, text: `Carga exitosa: ${r.records} registros.` } : { ok: false, text: r.error ?? "La carga falló" });
      setFile(null);
      queryClient.invalidateQueries();
    },
    onError: (e) => setMessage({ ok: false, text: (e as Error).message }),
  });
  const remove = useMutation({
    mutationFn: (id: number) => apiSend(`/uploads/${id}`, "DELETE"),
    onSuccess: () => queryClient.invalidateQueries(),
  });
  const current = KINDS.find((k) => k.key === kind)!;

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
        <h3 className="text-base font-semibold">Datos municipales</h3>
        <p className="mt-0.5 text-sm text-muted">Lo que cargue aquí se muestra siempre como información municipal, separada de los datos oficiales, y sólo es visible para esta comuna.</p>
        {canUpload ? (
          <form
            className="mt-4 space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (file) upload.mutate();
            }}
          >
            <div className="grid gap-2 sm:grid-cols-4">
              {KINDS.map((k) => (
                <button
                  type="button"
                  key={k.key}
                  onClick={() => setKind(k.key)}
                  className={`rounded-xl border p-2.5 text-left text-sm ${kind === k.key ? "border-brand bg-brand/5 font-medium" : "border-border hover:bg-slate-50"}`}
                >
                  {k.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-muted">{current.hint}</p>
            {kind === "assets" && (
              <label className="block text-sm">
                Categoría (si el archivo no trae columna categoria)
                <select value={category} onChange={(e) => setCategory(e.target.value)} className="mt-1 w-full rounded-lg border border-border px-3 py-2">
                  <option value="">Según el archivo</option>
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {kind === "contacts" && (
              <label className="block text-sm">
                Tipo por defecto (si el archivo no trae columna tipo)
                <select value={category} onChange={(e) => setCategory(e.target.value)} className="mt-1 w-full rounded-lg border border-border px-3 py-2">
                  <option value="">Contacto de emergencia</option>
                  <option value="personal">Personal municipal de emergencia</option>
                </select>
              </label>
            )}
            {kind === "photo" && (
              <label className="block text-sm">
                Activo asociado (opcional)
                <select value={assetId} onChange={(e) => setAssetId(e.target.value)} className="mt-1 w-full rounded-lg border border-border px-3 py-2">
                  <option value="">Sin activo</option>
                  {assets.data?.features.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.properties.name} ({f.properties.category})
                    </option>
                  ))}
                </select>
              </label>
            )}
            {(kind === "document" || kind === "photo" || kind === "raster") && (
              <label className="block text-sm">
                {kind === "photo" ? "Descripción" : "Título"}
                <input value={title} onChange={(e) => setTitle(e.target.value)} className="mt-1 w-full rounded-lg border border-border px-3 py-2" placeholder={kind === "photo" ? "Estado del puente tras el temporal" : "Plan comunal de emergencia"} />
              </label>
            )}
            <input type="file" accept={current.accept} onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="block w-full text-sm" />
            <button disabled={!file || upload.isPending} className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
              {upload.isPending ? "Cargando..." : "Cargar archivo"}
            </button>
            {message && <p className={`rounded-lg px-3 py-2 text-sm ${message.ok ? "bg-green-50 text-green-900" : "bg-red-50 text-red-900"}`}>{message.text}</p>}
          </form>
        ) : (
          <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm">Su rol puede consultar los datos cargados, pero no cargar archivos.</p>
        )}
      </section>

      <section className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
        <h3 className="text-base font-semibold">Cargas realizadas</h3>
        <ul className="mt-2 divide-y divide-border">
          {uploads.data?.length === 0 && <li className="py-2 text-sm text-muted">Aún no hay cargas.</li>}
          {uploads.data?.map((u) => (
            <li key={u.id} className="flex flex-wrap items-center gap-2 py-2.5 text-sm">
              <span className="font-medium">{u.filename}</span>
              {u.is_demo && <DemoBadge />}
              <span className="text-xs text-muted">
                {KIND_LABEL[u.kind]} · {u.record_count} registros · {formatShortTime(u.uploaded_at)} · {u.uploaded_by ?? ""}
              </span>
              {u.status === "failed" && <span className="w-full text-xs text-red-700">Error: {u.error}</span>}
              {canUpload && (
                <button onClick={() => confirm(`¿Eliminar ${u.filename} y sus registros?`) && remove.mutate(u.id)} className="ml-auto text-xs text-red-700 hover:underline">
                  Eliminar
                </button>
              )}
            </li>
          ))}
        </ul>
      </section>

      <MunicipalRecords />
    </div>
  );
}

interface ContactRow {
  id: number;
  kind: string;
  name: string;
  role: string | null;
  organization: string | null;
  phone: string | null;
  email: string | null;
  is_demo: boolean;
}

interface InspectionRow {
  id: number;
  asset_name: string;
  asset_id: number | null;
  inspected_on: string;
  status: string | null;
  notes: string | null;
  inspector: string | null;
  is_demo: boolean;
}

interface PhotoRow {
  id: number;
  asset_name: string | null;
  caption: string | null;
  created_at: string;
  is_demo: boolean;
}

function PhotoThumb({ photo }: { photo: PhotoRow }) {
  const image = useQuery({ queryKey: ["photo", photo.id], queryFn: () => apiObjectUrl(`/photos/${photo.id}/file`), staleTime: Infinity });
  return (
    <figure className="overflow-hidden rounded-lg border border-border">
      {image.data ? <img src={image.data} alt={photo.caption ?? "Fotografía municipal"} className="h-28 w-full object-cover" /> : <div className="h-28 bg-slate-100" />}
      <figcaption className="p-1.5 text-[11px]">
        {photo.caption ?? "Sin descripción"}
        {photo.asset_name && <span className="block text-muted">{photo.asset_name}</span>}
      </figcaption>
    </figure>
  );
}

function MunicipalRecords() {
  const contacts = useQuery({ queryKey: ["contacts"], queryFn: () => apiGet<ContactRow[]>("/contacts") });
  const inspections = useQuery({ queryKey: ["inspections"], queryFn: () => apiGet<InspectionRow[]>("/inspections") });
  const photos = useQuery({ queryKey: ["photos"], queryFn: () => apiGet<PhotoRow[]>("/photos") });
  return (
    <>
      <section className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
        <h3 className="text-base font-semibold">Contactos y personal de emergencia</h3>
        {contacts.data?.length === 0 && <p className="mt-1 text-sm text-muted">Sin contactos cargados.</p>}
        <ul className="mt-2 divide-y divide-border text-sm">
          {contacts.data?.map((c) => (
            <li key={c.id} className="flex flex-wrap gap-x-2 py-2">
              <span className="font-medium">{c.name}</span>
              {c.is_demo && <DemoBadge />}
              <span className="text-muted">
                {[c.kind === "personal" ? "Personal municipal" : "Contacto", c.role, c.organization].filter(Boolean).join(" · ")}
              </span>
              <span className="ml-auto">
                {c.phone && (
                  <a href={`tel:${c.phone.replace(/\s/g, "")}`} className="text-brand underline">
                    {c.phone}
                  </a>
                )}
                {c.email && <span className="ml-2 text-muted">{c.email}</span>}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
        <h3 className="text-base font-semibold">Inspecciones recientes</h3>
        {inspections.data?.length === 0 && <p className="mt-1 text-sm text-muted">Sin inspecciones cargadas.</p>}
        <ul className="mt-2 divide-y divide-border text-sm">
          {inspections.data?.slice(0, 30).map((i) => (
            <li key={i.id} className="py-2">
              <span className="font-medium">{i.asset_name}</span> {i.is_demo && <DemoBadge />}
              <span className="ml-2 text-muted">
                {i.inspected_on} · {i.status ?? "sin estado"}
                {i.inspector ? ` · ${i.inspector}` : ""}
                {i.asset_id === null ? " · activo no encontrado en la infraestructura cargada" : ""}
              </span>
              {i.notes && <span className="block text-xs">{i.notes}</span>}
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
        <h3 className="text-base font-semibold">Fotografías</h3>
        {photos.data?.length === 0 && <p className="mt-1 text-sm text-muted">Sin fotografías cargadas.</p>}
        <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
          {photos.data?.map((p) => <PhotoThumb key={p.id} photo={p} />)}
        </div>
      </section>
    </>
  );
}
