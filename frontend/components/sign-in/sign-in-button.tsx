"use client";

import { signIn } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { GithubIcon } from "@/components/icons/github-icon";

export function SignInButton() {
  return (
    <Button onClick={() => signIn("github", { callbackUrl: "/" })} className="w-full gap-2">
      <GithubIcon className="h-4 w-4" aria-hidden="true" />
      Continue with GitHub
    </Button>
  );
}
