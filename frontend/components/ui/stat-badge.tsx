import type { LucideIcon } from "lucide-react";

export function StatBadge({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: LucideIcon;
  label: string;
  value: string | number;
  color: string;
}) {
  return (
    <span className="flex items-center gap-1 text-sm" aria-label={label}>
      <Icon className={`h-4 w-4 ${color}`} aria-hidden="true" />
      {value}
    </span>
  );
}
