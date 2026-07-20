"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { Snapshot } from "@/lib/api-types";

export function useRepoSnapshots(repoId: number) {
  return useQuery({
    queryKey: queryKeys.repos.snapshots(repoId),
    queryFn: () => fetchJson<Snapshot[]>(`/api/repos/${repoId}/snapshots`),
  });
}
