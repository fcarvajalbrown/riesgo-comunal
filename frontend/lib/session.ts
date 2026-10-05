"use client";

import { useSyncExternalStore } from "react";

const TOKEN_KEY = "riesgo.token";
const TENANT_KEY = "riesgo.tenant";
const listeners = new Set<() => void>();

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {}
  listeners.forEach((l) => l());
}

export function getToken(): string | null {
  return typeof window === "undefined" ? null : read(TOKEN_KEY);
}

export function setToken(token: string | null) {
  write(TOKEN_KEY, token);
  if (token === null) write(TENANT_KEY, null);
}

export function getTenantOverride(): string | null {
  return typeof window === "undefined" ? null : read(TENANT_KEY);
}

export function setTenantOverride(id: string | null) {
  write(TENANT_KEY, id);
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useSession() {
  const token = useSyncExternalStore(subscribe, getToken, () => null);
  const ready = useSyncExternalStore(subscribe, () => true, () => false);
  return { token, ready };
}
