"use client";

import { CheckCircle2, Filter, Lightbulb, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionHeading } from "@/components/ui/section-heading";
import { useDismissRecommendation, useRecommendations } from "@/hooks/use-recommendations";
import { useRepos } from "@/hooks/use-repos";

export function RecommendationsClient() {
  const { data: recommendations } = useRecommendations();
  const { data: repos } = useRepos();
  const dismiss = useDismissRecommendation();
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);

  const repoNameById = useMemo(() => {
    const map = new Map<number, string>();
    repos?.forEach((r) => map.set(r.id, `${r.owner}/${r.name}`));
    return map;
  }, [repos]);

  const categories = useMemo(
    () => Array.from(new Set(recommendations?.map((r) => r.category) ?? [])),
    [recommendations],
  );

  const visible = recommendations?.filter(
    (r) => !r.dismissed && (categoryFilter === null || r.category === categoryFilter),
  );

  return (
    <div className="space-y-6">
      <SectionHeading icon={Lightbulb} title="Recommendations inbox" subtitle="Fact-checked suggestions across every tracked repo" iconColor="text-amber-500" />

      {categories.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          <Button variant={categoryFilter === null ? "default" : "outline"} size="sm" onClick={() => setCategoryFilter(null)}>
            All
          </Button>
          {categories.map((category) => (
            <Button
              key={category}
              variant={categoryFilter === category ? "default" : "outline"}
              size="sm"
              onClick={() => setCategoryFilter(category)}
            >
              {category}
            </Button>
          ))}
        </div>
      )}

      {visible && visible.length === 0 ? (
        <EmptyState icon={CheckCircle2} title="Inbox zero" description="No open recommendations right now." />
      ) : (
        <div className="space-y-2">
          {visible?.map((rec) => (
            <Card key={rec.id}>
              <CardContent className="flex items-start justify-between gap-4 py-4">
                <div>
                  <p className="text-xs font-medium text-muted-foreground">{repoNameById.get(rec.repo_id) ?? `repo #${rec.repo_id}`}</p>
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
