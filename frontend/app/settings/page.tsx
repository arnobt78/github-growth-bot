import { QueryClient, dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { SettingsClient } from "@/components/settings/settings-client";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const queryClient = new QueryClient();

  const [repos, providerStatus, me] = await Promise.all([
    api.listRepos(),
    api.providerStatus(),
    api.getMe(),
  ]);
  queryClient.setQueryData(queryKeys.repos.all, repos);
  queryClient.setQueryData(queryKeys.providers.status, providerStatus);
  queryClient.setQueryData(queryKeys.users.me, me);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <SettingsClient />
    </HydrationBoundary>
  );
}
