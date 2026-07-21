import { QueryClient, dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { SettingsClient } from "@/components/settings/settings-client";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const queryClient = new QueryClient();

  const [repos, providerStatus] = await Promise.all([api.listRepos(), api.providerStatus()]);
  queryClient.setQueryData(queryKeys.repos.all, repos);
  queryClient.setQueryData(queryKeys.providers.status, providerStatus);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <SettingsClient />
    </HydrationBoundary>
  );
}
