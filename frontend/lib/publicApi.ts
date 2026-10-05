import { ApiError } from "@/lib/api";

export async function publicGet<T>(path: string): Promise<T> {
  const response = await fetch(`/api/public${path}`);
  if (!response.ok) {
    let message = `Error ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {}
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<T>;
}
