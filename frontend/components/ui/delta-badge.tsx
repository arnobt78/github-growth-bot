import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

export function DeltaBadge({ value, label }: { value: number; label: string }) {
  if (value === 0) {
    return (
      <span className="flex items-center gap-1 text-sm text-muted-foreground" aria-label={`${label}: no change`}>
        <Minus className="h-4 w-4" aria-hidden="true" />0
      </span>
    );
  }

  const trending = value > 0;

  return (
    <span
      className={`flex items-center gap-1 text-sm ${trending ? "text-emerald-500" : "text-red-500"}`}
      aria-label={`${label}: ${trending ? "up" : "down"} ${Math.abs(value)}`}
    >
      {trending ? <ArrowUpRight className="h-4 w-4" aria-hidden="true" /> : <ArrowDownRight className="h-4 w-4" aria-hidden="true" />}
      {trending ? "+" : ""}
      {value}
    </span>
  );
}
