import { QueryClient, dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { OverviewClient } from "@/components/overview/overview-client";

export const dynamic = "force-dynamic";

export default async function OverviewPage() {
  const queryClient = new QueryClient();

  const repos = await api.listRepos();
  queryClient.setQueryData(queryKeys.repos.all, repos);

  await Promise.all(
    repos.flatMap((repo) => [
      queryClient.prefetchQuery({
        queryKey: queryKeys.repos.snapshots(repo.id),
        queryFn: () => api.listSnapshots(repo.id),
      }),
      queryClient.prefetchQuery({
        queryKey: queryKeys.repos.insights(repo.id),
        queryFn: () => api.getInsights(repo.id),
      }),
    ]),
  );

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <OverviewClient />
    </HydrationBoundary>
  );
}
