"use client";

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import { useRepoSnapshots } from "@/hooks/use-repo-snapshots";

export function TrendChart({ repoId }: { repoId: number }) {
  const { data: snapshots, isPending } = useRepoSnapshots(repoId);

  if (isPending) {
    return <Skeleton className="h-64 w-full" />;
  }

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={snapshots}>
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip />
          <Line type="monotone" dataKey="stars" stroke="#f59e0b" strokeWidth={2} dot={false} name="Stars" />
          <Line type="monotone" dataKey="forks" stroke="#8b5cf6" strokeWidth={2} dot={false} name="Forks" />
          <Line type="monotone" dataKey="views_14d" stroke="#0ea5e9" strokeWidth={2} dot={false} name="Views (14d)" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
