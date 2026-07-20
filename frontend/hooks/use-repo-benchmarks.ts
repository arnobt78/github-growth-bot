"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { Benchmark } from "@/lib/api-types";

export function useRepoBenchmarks(repoId: number) {
  return useQuery({
    queryKey: queryKeys.repos.benchmarks(repoId),
    queryFn: () => fetchJson<Benchmark[]>(`/api/repos/${repoId}/benchmarks`),
  });
}
