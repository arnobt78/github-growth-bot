"use client";

import { useEffect } from "react";
import { useSession } from "next-auth/react";
import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-keys";

const EVENT_QUERY_MAP: Record<string, QueryKey[]> = {
  repo_added: [queryKeys.repos.all],
  // Backend cascades repo deletion to that repo's recommendations/drafts (ON DELETE
  // CASCADE) — other open tabs need those inboxes invalidated too, not just the repo list.
  repo_removed: [queryKeys.repos.all, queryKeys.recommendations.all, queryKeys.drafts.all],
  // Payload only carries {id, dismissed} (no repo_id — see backend app/api/recommendations.py),
  // so we can't target one repo's insights key; invalidate repos.all (prefix-matches
  // ["repos", id, "insights"] too) to refresh the recommendation_count badge everywhere.
  recommendation_updated: [queryKeys.recommendations.all, queryKeys.repos.all],
  run_completed: [queryKeys.runs.all, queryKeys.repos.all, queryKeys.recommendations.all],
  draft_updated: [queryKeys.drafts.all],
  drafts_generated: [queryKeys.drafts.all, queryKeys.runs.all],
  user_updated: [queryKeys.users.me],
};

export function useLiveEvents() {
  const queryClient = useQueryClient();
  const { status } = useSession();

  useEffect(() => {
    if (status !== "authenticated") {
      return;
    }

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
  }, [queryClient, status]);
}
