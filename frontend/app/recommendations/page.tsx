import { QueryClient, dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { RecommendationsClient } from "@/components/recommendations/recommendations-client";

export const dynamic = "force-dynamic";

export default async function RecommendationsPage() {
  const queryClient = new QueryClient();

  await Promise.all([
    queryClient.prefetchQuery({ queryKey: queryKeys.recommendations.all, queryFn: () => api.listRecommendations() }),
    queryClient.prefetchQuery({ queryKey: queryKeys.repos.all, queryFn: () => api.listRepos() }),
  ]);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <RecommendationsClient />
    </HydrationBoundary>
  );
}
