"use client";

import { Bell, History, LayoutDashboard, Settings } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutDashboard, color: "text-sky-500" },
  { href: "/recommendations", label: "Recommendations", icon: Bell, color: "text-amber-500" },
  { href: "/runs", label: "Pipeline Runs", icon: History, color: "text-violet-500" },
  { href: "/settings", label: "Settings", icon: Settings, color: "text-slate-500" },
];

export function NavSidebar() {
  const pathname = usePathname();

  return (
    <nav className="flex w-56 shrink-0 flex-col gap-1 border-r p-4">
      {NAV_ITEMS.map(({ href, label, icon: Icon, color }) => {
        const active = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium",
              active ? "bg-muted" : "hover:bg-muted/50",
            )}
          >
            <Icon className={`h-4 w-4 ${color}`} aria-hidden="true" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
