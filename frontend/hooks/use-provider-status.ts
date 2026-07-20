"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";

type ProviderStatus = { provider: string; calls_today: number };

export function useProviderStatus() {
  return useQuery({
    queryKey: queryKeys.providers.status,
    queryFn: () => fetchJson<ProviderStatus[]>("/api/providers/status"),
  });
}
