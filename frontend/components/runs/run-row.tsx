"use client";

import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useRunStages } from "@/hooks/use-run-stages";
import type { PipelineRun } from "@/lib/api-types";

const STATUS_META = {
  ok: { icon: CheckCircle2, color: "text-emerald-500", label: "OK" },
  degraded: { icon: AlertTriangle, color: "text-amber-500", label: "Degraded" },
  running: { icon: Loader2, color: "text-sky-500", label: "Running" },
} as const;

export function RunRow({ run }: { run: PipelineRun }) {
  const [expanded, setExpanded] = useState(false);
  const { data: stages, isPending } = useRunStages(run.id, expanded);
  const meta = STATUS_META[run.status as keyof typeof STATUS_META] ?? STATUS_META.running;
  const StatusIcon = meta.icon;

  return (
    <Card>
      <CardContent className="py-3">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex w-full items-center justify-between text-left"
          aria-expanded={expanded}
        >
          <span className="flex items-center gap-2 text-sm font-medium">
            {expanded ? <ChevronDown className="h-4 w-4" aria-hidden="true" /> : <ChevronRight className="h-4 w-4" aria-hidden="true" />}
            Run #{run.id}
          </span>
          <span className={`flex items-center gap-1 text-sm ${meta.color}`}>
            <StatusIcon className="h-4 w-4" aria-hidden="true" />
            {meta.label}
          </span>
        </button>
        {expanded && (
          <div className="mt-3 space-y-1 border-t pt-3">
            {isPending ? (
              <Skeleton className="h-20 w-full" />
            ) : (
              stages?.map((stage) => (
                <div key={stage.id} className="text-sm">
                  <div className="flex items-center justify-between">
                    <span>{stage.stage_name}</span>
                    <span className="flex items-center gap-2 text-muted-foreground">
                      {stage.duration_ms}ms
                      <span className={stage.status === "ok" ? "text-emerald-500" : "text-red-500"}>{stage.status}</span>
                    </span>
                  </div>
                  {stage.error && <p className="mt-0.5 text-xs text-red-500">{stage.error}</p>}
                </div>
              ))
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
