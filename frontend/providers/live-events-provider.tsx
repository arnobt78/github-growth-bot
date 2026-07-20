"use client";

import type { ReactNode } from "react";
import { useLiveEvents } from "@/hooks/use-live-events";

export function LiveEventsProvider({ children }: { children: ReactNode }) {
  useLiveEvents();
  return <>{children}</>;
}
