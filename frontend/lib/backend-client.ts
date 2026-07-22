import "server-only";
import { auth } from "@/auth";
import { mintInternalUserToken } from "@/lib/internal-auth";

const BASE_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const API_KEY = process.env.BACKEND_API_KEY ?? "";

export class BackendError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new BackendError(res.status, text || res.statusText);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

// The authenticated fetcher — used by every existing api.ts method except
// upsertUser. Automatically derives the signed internal user token from the
// current Auth.js session, so every one of the 13 Route Handlers and every
// page.tsx SSR prefetch call needs zero changes to become per-user scoped.
export async function backendFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const session = await auth();
  const githubId = session?.user?.id;
  if (!githubId) {
    throw new BackendError(401, "Not authenticated");
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${API_KEY}`,
      "X-Internal-User-Token": mintInternalUserToken(githubId),
      ...init?.headers,
    },
    cache: "no-store",
  });

  return handleResponse<T>(res);
}

// API-key only, no session required — for server-to-server calls that don't
// have a user session yet (matching api.upsertUser's intended use case).
// Note: auth.ts's own jwt callback does NOT use this — it inlines a separate
// raw fetch() to avoid a circular import (this module imports auth() from
// @/auth for backendFetch below, so auth.ts importing back into lib/ would
// cycle). This function remains here for any future API-key-only caller
// (e.g. an admin script) needing the same pattern.
export async function backendFetchSystem<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${API_KEY}`,
      ...init?.headers,
    },
    cache: "no-store",
  });

  return handleResponse<T>(res);
}
