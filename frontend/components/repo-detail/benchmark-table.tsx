"use client";

import { Trophy } from "lucide-react";
import { SectionHeading } from "@/components/ui/section-heading";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useRepoBenchmarks } from "@/hooks/use-repo-benchmarks";

export function BenchmarkTable({ repoId }: { repoId: number }) {
  const { data: benchmarks, isPending } = useRepoBenchmarks(repoId);

  return (
    <div className="space-y-3">
      <SectionHeading icon={Trophy} title="Benchmark repos" subtitle="Similar public repos, for comparison" iconColor="text-amber-500" />
      {isPending ? (
        <Skeleton className="h-32 w-full" />
      ) : benchmarks && benchmarks.length === 0 ? (
        <EmptyState icon={Trophy} title="No benchmarks yet" description="These populate on the next pipeline run." />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Repo</TableHead>
              <TableHead>Stars</TableHead>
              <TableHead>Forks</TableHead>
              <TableHead>Topics</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {benchmarks?.map((b) => (
              <TableRow key={b.full_name}>
                <TableCell>{b.full_name}</TableCell>
                <TableCell>{b.stars}</TableCell>
                <TableCell>{b.forks}</TableCell>
                <TableCell>{b.topics.join(", ")}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
