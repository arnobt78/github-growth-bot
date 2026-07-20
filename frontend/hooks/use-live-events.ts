"use client";

import { useEffect } from "react";
import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-keys";

const EVENT_QUERY_MAP: Record<string, QueryKey[]> = {
  repo_added: [queryKeys.repos.all],
  repo_removed: [queryKeys.repos.all],
  recommendation_updated: [queryKeys.recommendations.all],
  run_completed: [queryKeys.runs.all, queryKeys.repos.all],
};

export function useLiveEvents() {
  const queryClient = useQueryClient();

  useEffect(() => {
    const source = new EventSource("/api/events");

    const handler = (event: MessageEvent) => {
      const keysToInvalidate = EVENT_QUERY_MAP[event.type] ?? [];
      for (const key of keysToInvalidate) {
        queryClient.invalidateQueries({ queryKey: key });
      }
    };

    for (const eventType of Object.keys(EVENT_QUERY_MAP)) {
      source.addEventListener(eventType, handler);
    }

    return () => {
      source.close();
    };
  }, [queryClient]);
}
