// frontend/proxy.ts
// NOTE: this Next.js version renamed the `middleware.ts` file convention to
// `proxy.ts` (confirmed via node_modules/next/dist/docs/.../proxy.md — v16.0.0
// change). The exported function/re-export must be named `proxy`, not
// `middleware`, or Next.js won't pick this file up at all.
export { auth as proxy } from "@/auth";

export const config = {
  // Runs on every page except: API routes (they self-check via backendFetch),
  // the sign-in page itself (would otherwise redirect-loop), Next's own
  // static/image assets, and the root-level metadata files.
  matcher: [
    "/((?!api|sign-in|_next/static|_next/image|favicon.ico|robots.txt).*)",
  ],
};
