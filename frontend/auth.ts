import NextAuth from "next-auth";
import GitHub from "next-auth/providers/github";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const BACKEND_API_KEY = process.env.BACKEND_API_KEY ?? "";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    GitHub({
      // Public-repo scope only (spec §2) — no `repo` scope, no private-repo access.
      authorization: { params: { scope: "read:user public_repo" } },
    }),
  ],
  pages: {
    signIn: "/sign-in",
  },
  callbacks: {
    // Required for `auth` to actually gate routes when re-exported as
    // `proxy` (frontend/proxy.ts, Task 14). Without this, next-auth's
    // internal `authorized` defaults to `true` unconditionally (see
    // node_modules/next-auth/lib/index.js) and the proxy becomes a silent
    // passthrough — no redirect ever fires for unauthenticated requests.
    authorized({ auth }) {
      return !!auth?.user;
    },
    async jwt({ token, account, profile }) {
      // account/profile are only present on the initial sign-in, not on
      // every subsequent token refresh — this is where we bootstrap the
      // backend's User row, deliberately via a raw fetch (not lib/api.ts)
      // to avoid a circular import: lib/backend-client.ts imports auth()
      // from this file for its own per-request session check, so this file
      // must not import back into lib/ at module scope.
      if (account?.provider === "github" && profile) {
        const githubId = String(profile.id);
        token.githubId = githubId;

        await fetch(`${BACKEND_URL}/users/upsert`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${BACKEND_API_KEY}`,
          },
          body: JSON.stringify({
            github_id: githubId,
            username: (profile as { login?: string }).login ?? "unknown",
            avatar_url: (profile as { avatar_url?: string }).avatar_url ?? "",
            email: profile.email ?? null,
            access_token: account.access_token,
          }),
        });
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.githubId as string;
      }
      return session;
    },
  },
});
