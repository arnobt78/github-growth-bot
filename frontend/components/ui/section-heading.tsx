import type { LucideIcon } from "lucide-react";

export function SectionHeading({
  icon: Icon,
  title,
  subtitle,
  iconColor = "text-sky-500",
}: {
  icon: LucideIcon;
  title: string;
  subtitle?: string;
  iconColor?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <Icon className={`h-5 w-5 ${iconColor}`} aria-hidden="true" />
      <div>
        <h2 className="text-lg font-semibold leading-tight">{title}</h2>
        {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
      </div>
    </div>
  );
}
