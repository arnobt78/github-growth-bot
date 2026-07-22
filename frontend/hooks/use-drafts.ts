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
