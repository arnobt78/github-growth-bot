"use client";

import { Cpu } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionHeading } from "@/components/ui/section-heading";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useProviderStatus } from "@/hooks/use-provider-status";

export function ProviderStatusTable() {
  const { data: statuses, isPending } = useProviderStatus();

  return (
    <div className="space-y-3">
      <SectionHeading icon={Cpu} title="LLM provider usage" subtitle="Calls made today, per free-tier provider" iconColor="text-sky-500" />
      {isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : statuses && statuses.length === 0 ? (
        <EmptyState icon={Cpu} title="No usage yet today" description="Provider usage resets daily." />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Provider</TableHead>
              <TableHead>Calls today</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {statuses?.map((s) => (
              <TableRow key={s.provider}>
                <TableCell>{s.provider}</TableCell>
                <TableCell>{s.calls_today}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
