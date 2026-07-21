import { QueryClient, dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import { BackendError } from "@/lib/backend-client";
import { queryKeys } from "@/lib/query-keys";
import { RepoDetailClient } from "@/components/repo-detail/repo-detail-client";

export const dynamic = "force-dynamic";

export default async function RepoDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const repoId = Number(id);
  const queryClient = new QueryClient();

  let repo;
  try {
    repo = await api.getRepo(repoId);
  } catch (error) {
    if (error instanceof BackendError && error.status === 404) {
      notFound();
    }
    throw error;
  }

  await Promise.all([
    queryClient.prefetchQuery({ queryKey: queryKeys.repos.snapshots(repoId), queryFn: () => api.listSnapshots(repoId) }),
    queryClient.prefetchQuery({ queryKey: queryKeys.repos.benchmarks(repoId), queryFn: () => api.listBenchmarks(repoId) }),
    queryClient.prefetchQuery({ queryKey: queryKeys.repos.referrers(repoId), queryFn: () => api.listReferrers(repoId) }),
    queryClient.prefetchQuery({ queryKey: queryKeys.repos.popularPaths(repoId), queryFn: () => api.listPopularPaths(repoId) }),
    queryClient.prefetchQuery({ queryKey: queryKeys.recommendations.all, queryFn: () => api.listRecommendations() }),
  ]);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <RepoDetailClient repo={repo} />
    </HydrationBoundary>
  );
}
