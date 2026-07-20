"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { StageRun } from "@/lib/api-types";

export function useRunStages(runId: number, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.runs.stages(runId),
    queryFn: () => fetchJson<StageRun[]>(`/api/runs/${runId}/stages`),
    enabled,
  });
}
