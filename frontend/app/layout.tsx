import type { Metadata } from "next";
import { Toaster } from "@/components/ui/sonner";
import { NavSidebar } from "@/components/nav-sidebar";
import { ThemeToggle } from "@/components/theme-toggle";
import { QueryProvider } from "@/providers/query-provider";
import { LiveEventsProvider } from "@/providers/live-events-provider";
import { ThemeProvider } from "@/providers/theme-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "GitHub Growth Bot",
  description: "Personal GitHub repo health, benchmarking, and recommendations dashboard.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning data-scroll-behavior="smooth">
      <body>
        <ThemeProvider>
          <QueryProvider>
            <LiveEventsProvider>
              <div className="flex min-h-screen">
                <NavSidebar />
                <div className="flex-1">
                  <header className="flex items-center justify-between border-b px-6 py-3">
                    <h1 className="text-base font-semibold">GitHub Growth Bot</h1>
                    <ThemeToggle />
                  </header>
                  <main className="p-6">{children}</main>
                </div>
              </div>
              <Toaster />
            </LiveEventsProvider>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
