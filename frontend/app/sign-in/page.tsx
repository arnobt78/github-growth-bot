import { Rocket } from "lucide-react";
import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { GithubIcon } from "@/components/icons/github-icon";
import { SignInButton } from "@/components/sign-in/sign-in-button";

export const dynamic = "force-dynamic";

export default async function SignInPage() {
  const session = await auth();
  if (session?.user) {
    redirect("/");
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="flex w-full max-w-sm flex-col items-center gap-6 rounded-lg border p-8 text-center">
        <Rocket className="h-10 w-10 text-sky-500" aria-hidden="true" />
        <div className="space-y-1">
          <h1 className="text-lg font-semibold">GitHub Growth Bot</h1>
          <p className="text-sm text-muted-foreground">
            Sign in with GitHub to track your repos and get AI-synthesized growth recommendations.
          </p>
        </div>
        <SignInButton />
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <GithubIcon className="h-3.5 w-3.5" aria-hidden="true" />
          Public-repo read access only — we never touch private repos or write to GitHub.
        </p>
      </div>
    </div>
  );
}
