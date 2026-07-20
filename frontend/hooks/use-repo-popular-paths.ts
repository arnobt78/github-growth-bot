"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { PopularPath } from "@/lib/api-types";

export function useRepoPopularPaths(repoId: number) {
  return useQuery({
    queryKey: queryKeys.repos.popularPaths(repoId),
    queryFn: () => fetchJson<PopularPath[]>(`/api/repos/${repoId}/popular-paths`),
  });
}
