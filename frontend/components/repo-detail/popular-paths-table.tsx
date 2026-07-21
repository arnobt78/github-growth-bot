"use client";

import { Route } from "lucide-react";
import { SectionHeading } from "@/components/ui/section-heading";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useRepoPopularPaths } from "@/hooks/use-repo-popular-paths";

export function PopularPathsTable({ repoId }: { repoId: number }) {
  const { data: paths, isPending } = useRepoPopularPaths(repoId);

  return (
    <div className="space-y-3">
      <SectionHeading icon={Route} title="Popular content" subtitle="Most-viewed paths in this repo" iconColor="text-sky-500" />
      {isPending ? (
        <Skeleton className="h-32 w-full" />
      ) : paths && paths.length === 0 ? (
        <EmptyState icon={Route} title="No path data yet" description="GitHub's traffic API is a rolling 14-day window." />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Path</TableHead>
              <TableHead>Views</TableHead>
              <TableHead>Uniques</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paths?.map((p) => (
              <TableRow key={p.id}>
                <TableCell className="font-mono text-xs">{p.path}</TableCell>
                <TableCell>{p.count}</TableCell>
                <TableCell>{p.uniques}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
