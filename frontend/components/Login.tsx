"use client";

import { useState } from "react";
import { apiSend } from "@/lib/api";
import { setToken } from "@/lib/session";

export function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await apiSend<{ token: string }>("/auth/login", "POST", { email, password });
      setToken(result.token);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo iniciar sesión");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-full items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-brand text-lg font-bold text-white">RC</div>
          <h1 className="text-2xl font-semibold">Riesgo Comunal</h1>
          <p className="mt-1 text-sm text-muted">Información de riesgo para la gestión municipal</p>
        </div>
        <form onSubmit={submit} className="space-y-4 rounded-2xl border border-border bg-surface p-6 shadow-sm">
          <label className="block">
            <span className="text-sm font-medium">Correo</span>
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border px-3 py-2 outline-none focus:border-brand focus:ring-2 focus:ring-brand/20"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium">Contraseña</span>
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border px-3 py-2 outline-none focus:border-brand focus:ring-2 focus:ring-brand/20"
            />
          </label>
          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
          <button disabled={busy} className="w-full rounded-lg bg-brand px-4 py-2.5 font-medium text-white hover:opacity-95 disabled:opacity-60">
            {busy ? "Ingresando..." : "Ingresar"}
          </button>
        </form>
        <p className="mt-6 text-center text-xs leading-relaxed text-muted">
          Esta plataforma no es SENAPRED ni un sistema oficial de alertas. Para alertas oficiales consulte senapred.cl.
        </p>
      </div>
    </main>
  );
}
