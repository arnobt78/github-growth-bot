"use client";

import { History, Play } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionHeading } from "@/components/ui/section-heading";
import { useRuns, useTriggerRun } from "@/hooks/use-runs";
import { RunRow } from "@/components/runs/run-row";

export function RunsClient() {
  const { data: runs } = useRuns();
  const triggerRun = useTriggerRun();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <SectionHeading icon={History} title="Pipeline runs" subtitle="Execution history, per-stage status" iconColor="text-violet-500" />
        <Button
          onClick={() =>
            triggerRun.mutate(undefined, {
              onSuccess: () => toast.success("Pipeline run triggered"),
              onError: () => toast.error("Could not trigger a run"),
            })
          }
          disabled={triggerRun.isPending}
        >
          <Play className="h-4 w-4" aria-hidden="true" />
          {triggerRun.isPending ? "Running..." : "Run now"}
        </Button>
      </div>
      {runs && runs.length === 0 ? (
        <EmptyState icon={History} title="No runs yet" description="Trigger one manually or wait for the daily schedule." />
      ) : (
        <div className="space-y-2">{runs?.map((run) => <RunRow key={run.id} run={run} />)}</div>
      )}
    </div>
  );
}
