"use client";

import { FolderGit2, Settings as SettingsIcon, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionHeading } from "@/components/ui/section-heading";
import { AddRepoDialog } from "@/components/overview/add-repo-dialog";
import { ProviderStatusTable } from "@/components/settings/provider-status-table";
import { useDeleteRepo, useRepos } from "@/hooks/use-repos";

export function SettingsClient() {
  const { data: repos } = useRepos();
  const deleteRepo = useDeleteRepo();

  return (
    <div className="space-y-8">
      <SectionHeading icon={SettingsIcon} title="Settings" subtitle="Manage tracked repos and provider health" />

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <SectionHeading icon={FolderGit2} title="Tracked repos" iconColor="text-sky-500" />
          <AddRepoDialog />
        </div>
        {repos && repos.length === 0 ? (
          <EmptyState icon={FolderGit2} title="No repos tracked yet" description="Add a repo to get started." />
        ) : (
          <div className="space-y-2">
            {repos?.map((repo) => (
              <Card key={repo.id}>
                <CardContent className="flex items-center justify-between py-3">
                  <span>
                    {repo.owner}/{repo.name}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Stop tracking ${repo.owner}/${repo.name}`}
                    onClick={() =>
                      deleteRepo.mutate(repo.id, {
                        onError: () => toast.error(`Could not stop tracking ${repo.owner}/${repo.name} — try again.`),
                      })
                    }
                    disabled={deleteRepo.isPending}
                  >
                    <Trash2 className="h-4 w-4 text-red-500" aria-hidden="true" />
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      <ProviderStatusTable />
    </div>
  );
}
