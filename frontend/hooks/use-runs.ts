"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { PipelineRun } from "@/lib/api-types";

export function useRuns() {
  return useQuery({
    queryKey: queryKeys.runs.all,
    queryFn: () => fetchJson<PipelineRun[]>("/api/runs"),
  });
}

export function useTriggerRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => fetchJson<PipelineRun[]>("/api/runs", { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.runs.all });
    },
  });
}
