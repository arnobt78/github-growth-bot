import { QueryClient, dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { RunsClient } from "@/components/runs/runs-client";

export const dynamic = "force-dynamic";

export default async function RunsPage() {
  const queryClient = new QueryClient();

  const runs = await api.listRuns();
  queryClient.setQueryData(queryKeys.runs.all, runs);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <RunsClient />
    </HydrationBoundary>
  );
}
