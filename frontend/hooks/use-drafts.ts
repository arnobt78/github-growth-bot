"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { Draft } from "@/lib/api-types";

export function useDrafts() {
  return useQuery({
    queryKey: queryKeys.drafts.all,
    queryFn: () => fetchJson<Draft[]>("/api/drafts"),
  });
}

export function useReviewDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: "approved" | "rejected" }) =>
      fetchJson<Draft>(`/api/drafts/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData<Draft[]>(queryKeys.drafts.all, (current) =>
        current?.map((d) => (d.id === updated.id ? updated : d)) ?? [],
      );
    },
  });
}

export function useTriggerContentRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => fetchJson<{ status: string }>("/api/runs/content", { method: "POST" }),
    onSuccess: () => {
      // The triggered run itself (not its eventual drafts) is visible immediately;
      // the drafts_generated SSE event above invalidates queryKeys.drafts.all once
      // the background pipeline actually finishes and writes rows.
      queryClient.invalidateQueries({ queryKey: queryKeys.runs.all });
    },
  });
}
