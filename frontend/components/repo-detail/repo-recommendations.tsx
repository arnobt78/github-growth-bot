"use client";

import { CheckCircle2, Lightbulb, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionHeading } from "@/components/ui/section-heading";
import { Skeleton } from "@/components/ui/skeleton";
import { useDismissRecommendation, useRecommendations } from "@/hooks/use-recommendations";

export function RepoRecommendations({ repoId }: { repoId: number }) {
  const { data: recommendations, isPending } = useRecommendations();
  const dismiss = useDismissRecommendation();

  const scoped = recommendations?.filter((r) => r.repo_id === repoId && !r.dismissed);

  return (
    <div className="space-y-3">
      <SectionHeading icon={Lightbulb} title="Recommendations" subtitle="Fact-checked suggestions for this repo" iconColor="text-amber-500" />
      {isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : scoped && scoped.length === 0 ? (
        <EmptyState icon={CheckCircle2} title="All caught up" description="No open recommendations for this repo." />
      ) : (
        <div className="space-y-2">
          {scoped?.map((rec) => (
            <Card key={rec.id}>
              <CardContent className="flex items-start justify-between gap-4 py-4">
                <div>
                  <p className="font-medium">{rec.title}</p>
                  <p className="text-sm text-muted-foreground">{rec.body}</p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Dismiss recommendation"
                  onClick={() => dismiss.mutate({ id: rec.id, dismissed: true })}
                >
                  <X className="h-4 w-4 text-red-500" aria-hidden="true" />
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
