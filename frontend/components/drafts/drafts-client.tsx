"use client";

import { CheckCircle2, Inbox, Sparkles, X } from "lucide-react";
import { useMemo } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionHeading } from "@/components/ui/section-heading";
import { DraftContent } from "@/components/drafts/draft-content";
import { useDrafts, useReviewDraft, useTriggerContentRun } from "@/hooks/use-drafts";
import { useRepos } from "@/hooks/use-repos";

export function DraftsClient() {
  const { data: drafts } = useDrafts();
  const { data: repos } = useRepos();
  const review = useReviewDraft();
  const triggerContentRun = useTriggerContentRun();

  const repoNameById = useMemo(() => {
    const map = new Map<number, string>();
    repos?.forEach((r) => map.set(r.id, `${r.owner}/${r.name}`));
    return map;
  }, [repos]);

  const pending = drafts?.filter((d) => d.status === "pending");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <SectionHeading icon={Inbox} title="Drafts" subtitle="Review before anything goes out" iconColor="text-emerald-500" />
        <Button
          onClick={() =>
            triggerContentRun.mutate(undefined, {
              onSuccess: () => toast.success("Content generation started"),
              onError: () => toast.error("Could not start content generation"),
            })
          }
          disabled={triggerContentRun.isPending}
        >
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          {triggerContentRun.isPending ? "Generating..." : "Generate drafts"}
        </Button>
      </div>

      {pending && pending.length === 0 ? (
        <EmptyState icon={Inbox} title="No drafts yet" description="Click 'Generate drafts' or wait for the daily schedule." />
      ) : (
        <div className="space-y-2">
          {pending?.map((draft) => (
            <Card key={draft.id}>
              <CardContent className="flex items-start justify-between gap-4 py-4">
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-muted-foreground">
                    {draft.repo_id !== null ? repoNameById.get(draft.repo_id) ?? `repo #${draft.repo_id}` : "Account-level"}
                    {" · "}
                    {draft.kind}
                  </p>
                  <div className="mt-1">
                    <DraftContent kind={draft.kind} content={draft.content} />
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Approve draft"
                    onClick={() =>
                      review.mutate(
                        { id: draft.id, status: "approved" },
                        { onError: () => toast.error("Could not approve — try again.") },
                      )
                    }
                    disabled={review.isPending}
                  >
                    <CheckCircle2 className="h-4 w-4 text-emerald-500" aria-hidden="true" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Reject draft"
                    onClick={() =>
                      review.mutate(
                        { id: draft.id, status: "rejected" },
                        { onError: () => toast.error("Could not reject — try again.") },
                      )
                    }
                    disabled={review.isPending}
                  >
                    <X className="h-4 w-4 text-red-500" aria-hidden="true" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
