"use client";

import { Link2 } from "lucide-react";
import { SectionHeading } from "@/components/ui/section-heading";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useRepoReferrers } from "@/hooks/use-repo-referrers";

export function ReferrersTable({ repoId }: { repoId: number }) {
  const { data: referrers, isPending } = useRepoReferrers(repoId);

  return (
    <div className="space-y-3">
      <SectionHeading icon={Link2} title="Referrers" subtitle="Where traffic is coming from" iconColor="text-emerald-500" />
      {isPending ? (
        <Skeleton className="h-32 w-full" />
      ) : referrers && referrers.length === 0 ? (
        <EmptyState icon={Link2} title="No referrer data yet" description="GitHub's traffic API is a rolling 14-day window." />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Source</TableHead>
              <TableHead>Views</TableHead>
              <TableHead>Uniques</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {referrers?.map((r) => (
              <TableRow key={r.id}>
                <TableCell>{r.referrer}</TableCell>
                <TableCell>{r.count}</TableCell>
                <TableCell>{r.uniques}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
