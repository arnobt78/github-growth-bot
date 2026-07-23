"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { Repo, RepoCreate } from "@/lib/api-types";

export function useRepos() {
  return useQuery({
    queryKey: queryKeys.repos.all,
    queryFn: () => fetchJson<Repo[]>("/api/repos"),
  });
}

export function useAddRepo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RepoCreate) =>
      fetchJson<Repo>("/api/repos", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: (repo) => {
      queryClient.setQueryData<Repo[]>(queryKeys.repos.all, (current) => [...(current ?? []), repo]);
    },
  });
}

export function useDeleteRepo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => fetchJson<void>(`/api/repos/${id}`, { method: "DELETE" }),
    onSuccess: (_data, id) => {
      queryClient.setQueryData<Repo[]>(queryKeys.repos.all, (current) => current?.filter((r) => r.id !== id) ?? []);
      // Backend cascades the delete (ON DELETE CASCADE) to that repo's recommendations
      // and drafts — without this, the inbox caches keep showing rows for a repo that
      // no longer exists.
      queryClient.invalidateQueries({ queryKey: queryKeys.recommendations.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.drafts.all });
    },
  });
}
