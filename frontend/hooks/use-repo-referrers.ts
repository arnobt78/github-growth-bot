"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { Referrer } from "@/lib/api-types";

export function useRepoReferrers(repoId: number) {
  return useQuery({
    queryKey: queryKeys.repos.referrers(repoId),
    queryFn: () => fetchJson<Referrer[]>(`/api/repos/${repoId}/referrers`),
  });
}
