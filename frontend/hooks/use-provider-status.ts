"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { ProviderStatus } from "@/lib/api-types";

export function useProviderStatus() {
  return useQuery({
    queryKey: queryKeys.providers.status,
    queryFn: () => fetchJson<ProviderStatus[]>("/api/providers/status"),
  });
}
