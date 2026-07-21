"use client";

import { ExternalLink, Eye, GitFork, Lightbulb, Star, Trash2 } from "lucide-react";
import { Line, LineChart, ResponsiveContainer } from "recharts";
import Link from "next/link";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { DeltaBadge } from "@/components/ui/delta-badge";
import { StatBadge } from "@/components/ui/stat-badge";
import { SafeImage } from "@/components/safe-image";
import { useRepoSnapshots } from "@/hooks/use-repo-snapshots";
import { useRepoInsights } from "@/hooks/use-repo-insights";
import { useDeleteRepo } from "@/hooks/use-repos";
import type { Repo } from "@/lib/api-types";

export function RepoCard({ repo }: { repo: Repo }) {
  const { data: snapshots, isPending } = useRepoSnapshots(repo.id);
  const { data: insights } = useRepoInsights(repo.id);
  const deleteRepo = useDeleteRepo();

  const latest = snapshots?.at(-1);
  const previous = snapshots?.at(-2);
  const starDelta = latest && previous ? latest.stars - previous.stars : 0;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <Link href={`/repos/${repo.id}`} className="flex items-center gap-2 font-medium hover:underline">
          <SafeImage
            src={`https://avatars.githubusercontent.com/${repo.owner}`}
            alt={`${repo.owner} avatar`}
            width={20}
            height={20}
            className="rounded-full"
          />
          {repo.owner}/{repo.name}
          <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
        </Link>
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
      </CardHeader>
      <CardContent className="space-y-3">
        {isPending ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <div className="h-16">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={snapshots}>
                <Line type="monotone" dataKey="stars" stroke="#0ea5e9" strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
        <div className="flex items-center justify-between">
          <StatBadge icon={Star} label="Stars" value={latest?.stars ?? 0} color="text-amber-500" />
          <StatBadge icon={GitFork} label="Forks" value={latest?.forks ?? 0} color="text-violet-500" />
          <StatBadge icon={Eye} label="Watchers" value={latest?.watchers ?? 0} color="text-emerald-500" />
          <DeltaBadge value={starDelta} label="Stars change since last snapshot" />
        </div>
        {insights && insights.recommendation_count > 0 && (
          <StatBadge
            icon={Lightbulb}
            label="Open recommendations"
            value={`${insights.recommendation_count} open recommendation${insights.recommendation_count === 1 ? "" : "s"}`}
            color="text-amber-500"
          />
        )}
      </CardContent>
    </Card>
  );
}
