import { QueryClient, dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { DraftsClient } from "@/components/drafts/drafts-client";

export const dynamic = "force-dynamic";

export default async function DraftsPage() {
  const queryClient = new QueryClient();

  const [drafts, repos] = await Promise.all([api.listDrafts(), api.listRepos()]);
  queryClient.setQueryData(queryKeys.drafts.all, drafts);
  queryClient.setQueryData(queryKeys.repos.all, repos);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <DraftsClient />
    </HydrationBoundary>
  );
}
