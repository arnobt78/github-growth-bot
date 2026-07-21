import { QueryClient, dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { RecommendationsClient } from "@/components/recommendations/recommendations-client";

export const dynamic = "force-dynamic";

export default async function RecommendationsPage() {
  const queryClient = new QueryClient();

  const [recommendations, repos] = await Promise.all([api.listRecommendations(), api.listRepos()]);
  queryClient.setQueryData(queryKeys.recommendations.all, recommendations);
  queryClient.setQueryData(queryKeys.repos.all, repos);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <RecommendationsClient />
    </HydrationBoundary>
  );
}
