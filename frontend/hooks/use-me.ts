"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { UserOut } from "@/lib/api-types";

export function useMe() {
  return useQuery({
    queryKey: queryKeys.users.me,
    queryFn: () => fetchJson<UserOut>("/api/users/me"),
  });
}

export function useUpdateMe() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { notification_email: string | null }) =>
      fetchJson<UserOut>("/api/users/me", { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.users.me, updated);
    },
  });
}
