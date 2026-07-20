import "server-only";

const BASE_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const API_KEY = process.env.BACKEND_API_KEY ?? "";

export class BackendError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function backendFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${API_KEY}`,
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const text = await res.text();
    throw new BackendError(res.status, text || res.statusText);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}
