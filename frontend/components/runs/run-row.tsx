"use client";

import { AlertTriangle, BarChart3, CheckCircle2, ChevronDown, ChevronRight, Loader2, Sparkles } from "lucide-react";
import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useRunStages } from "@/hooks/use-run-stages";
import type { PipelineRun } from "@/lib/api-types";

const STATUS_META = {
  ok: { icon: CheckCircle2, color: "text-emerald-500", label: "OK" },
  degraded: { icon: AlertTriangle, color: "text-amber-500", label: "Degraded" },
  running: { icon: Loader2, color: "text-sky-500", label: "Running" },
} as const;

const KIND_META = {
  analytics: { icon: BarChart3, color: "text-sky-500", label: "Analytics" },
  content: { icon: Sparkles, color: "text-fuchsia-500", label: "Content" },
} as const;

export function RunRow({ run }: { run: PipelineRun }) {
  const [expanded, setExpanded] = useState(false);
  const { data: stages, isPending } = useRunStages(run.id, expanded);
  const meta = STATUS_META[run.status as keyof typeof STATUS_META] ?? STATUS_META.running;
  const StatusIcon = meta.icon;
  const kindMeta = KIND_META[run.pipeline_kind as keyof typeof KIND_META] ?? KIND_META.analytics;
  const KindIcon = kindMeta.icon;

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
            <span className={`flex items-center gap-1 text-xs ${kindMeta.color}`}>
              <KindIcon className="h-3.5 w-3.5" aria-hidden="true" />
              {kindMeta.label}
            </span>
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
