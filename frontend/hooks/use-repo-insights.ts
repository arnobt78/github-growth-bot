"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { Insights } from "@/lib/api-types";

export function useRepoInsights(repoId: number) {
  return useQuery({
    queryKey: queryKeys.repos.insights(repoId),
    queryFn: () => fetchJson<Insights>(`/api/repos/${repoId}/insights`),
  });
}
