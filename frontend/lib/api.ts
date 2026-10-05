import { getTenantOverride, getToken, setToken } from "@/lib/session";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function headers(extra?: HeadersInit): Headers {
  const h = new Headers(extra);
  const token = getToken();
  if (token) h.set("Authorization", `Bearer ${token}`);
  const tenant = getTenantOverride();
  if (tenant) h.set("X-Municipality-Id", tenant);
  return h;
}

async function handle<T>(response: Response): Promise<T> {
  if (response.status === 401) {
    setToken(null);
    throw new ApiError(401, "Sesión expirada");
  }
  if (!response.ok) {
    let message = `Error ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {}
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<T>;
}

export async function apiGet<T>(path: string): Promise<T> {
  return handle<T>(await fetch(`/api${path}`, { headers: headers() }));
}

export async function apiSend<T>(path: string, method: "POST" | "PUT" | "DELETE", body?: unknown): Promise<T> {
  const init: RequestInit = { method, headers: headers(body instanceof FormData ? undefined : { "Content-Type": "application/json" }) };
  if (body instanceof FormData) init.body = body;
  else if (body !== undefined) init.body = JSON.stringify(body);
  return handle<T>(await fetch(`/api${path}`, init));
}

export async function apiDownload(path: string, fallbackName: string) {
  const response = await fetch(`/api${path}`, { headers: headers() });
  if (!response.ok) throw new ApiError(response.status, "No se pudo descargar el archivo");
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
