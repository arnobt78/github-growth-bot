"use client";

import { GitBranch } from "lucide-react";
import { SectionHeading } from "@/components/ui/section-heading";
import { TrendChart } from "@/components/repo-detail/trend-chart";
import { BenchmarkTable } from "@/components/repo-detail/benchmark-table";
import { ReferrersTable } from "@/components/repo-detail/referrers-table";
import { PopularPathsTable } from "@/components/repo-detail/popular-paths-table";
import { RepoRecommendations } from "@/components/repo-detail/repo-recommendations";
import type { Repo } from "@/lib/api-types";

export function RepoDetailClient({ repo }: { repo: Repo }) {
  return (
    <div className="space-y-8">
      <SectionHeading icon={GitBranch} title={`${repo.owner}/${repo.name}`} subtitle="Trends, benchmarks, and recommendations" />
      <TrendChart repoId={repo.id} />
      <BenchmarkTable repoId={repo.id} />
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <ReferrersTable repoId={repo.id} />
        <PopularPathsTable repoId={repo.id} />
      </div>
      <RepoRecommendations repoId={repo.id} />
    </div>
  );
}
