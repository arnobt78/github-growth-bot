"use client";

import { Bell, History, LayoutDashboard, LogOut, Settings } from "lucide-react";
import { signOut } from "next-auth/react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { SafeImage } from "@/components/safe-image";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutDashboard, color: "text-sky-500" },
  { href: "/recommendations", label: "Recommendations", icon: Bell, color: "text-amber-500" },
  { href: "/runs", label: "Pipeline Runs", icon: History, color: "text-violet-500" },
  { href: "/settings", label: "Settings", icon: Settings, color: "text-slate-500" },
];

export function NavSidebar() {
  const pathname = usePathname();
  const { data: session } = useSession();

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

      {session?.user && (
        <div className="mt-auto flex items-center gap-2 border-t pt-4">
          <SafeImage
            src={session.user.image ?? ""}
            alt={session.user.name ?? "Account"}
            width={28}
            height={28}
            className="rounded-full"
          />
          <span className="flex-1 truncate text-sm font-medium">{session.user.name}</span>
          <button
            type="button"
            onClick={() => signOut({ callbackUrl: "/sign-in" })}
            aria-label="Sign out"
            className="rounded-md p-1.5 hover:bg-muted/50"
          >
            <LogOut className="h-4 w-4 text-rose-500" aria-hidden="true" />
          </button>
        </div>
      )}
    </nav>
  );
}
