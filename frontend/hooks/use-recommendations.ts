"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { Recommendation } from "@/lib/api-types";

export function useRecommendations() {
  return useQuery({
    queryKey: queryKeys.recommendations.all,
    queryFn: () => fetchJson<Recommendation[]>("/api/recommendations"),
  });
}

export function useDismissRecommendation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, dismissed }: { id: number; dismissed: boolean }) =>
      fetchJson<Recommendation>(`/api/recommendations/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ dismissed }),
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData<Recommendation[]>(queryKeys.recommendations.all, (current) =>
        current?.map((r) => (r.id === updated.id ? updated : r)) ?? [],
      );
    },
  });
}
