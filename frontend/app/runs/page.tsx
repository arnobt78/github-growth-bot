import { QueryClient, dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { RunsClient } from "@/components/runs/runs-client";

export const dynamic = "force-dynamic";

export default async function RunsPage() {
  const queryClient = new QueryClient();

  await queryClient.prefetchQuery({ queryKey: queryKeys.runs.all, queryFn: () => api.listRuns() });

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <RunsClient />
    </HydrationBoundary>
  );
}
