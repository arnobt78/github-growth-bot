import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DraftsClient } from "@/components/drafts/drafts-client";
import * as useDraftsModule from "@/hooks/use-drafts";
import * as useReposModule from "@/hooks/use-repos";

const baseDraft = {
  id: 1,
  repo_id: 10,
  status: "pending" as const,
  created_at: "2026-07-24T00:00:00Z",
  reviewed_at: null,
};

function mockHooks(drafts: unknown[]) {
  vi.spyOn(useDraftsModule, "useDrafts").mockReturnValue({ data: drafts } as ReturnType<typeof useDraftsModule.useDrafts>);
  vi.spyOn(useDraftsModule, "useReviewDraft").mockReturnValue({ mutate: vi.fn(), isPending: false } as unknown as ReturnType<typeof useDraftsModule.useReviewDraft>);
  vi.spyOn(useDraftsModule, "useTriggerContentRun").mockReturnValue({ mutate: vi.fn(), isPending: false } as unknown as ReturnType<typeof useDraftsModule.useTriggerContentRun>);
  vi.spyOn(useReposModule, "useRepos").mockReturnValue({ data: [{ id: 10, owner: "octocat", name: "hello-world" }] } as unknown as ReturnType<typeof useReposModule.useRepos>);
}

describe("DraftsClient release_notes header", () => {
  it("shows the release tag in the header for a release_notes draft", () => {
    mockHooks([{ ...baseDraft, kind: "release_notes", target: "v1.2.0", content: { suggested: "## Features", reason: "clear" } }]);
    render(<DraftsClient />);
    expect(screen.getByText(/Release notes/)).toBeInTheDocument();
    expect(screen.getByText(/\(v1\.2\.0\)/)).toBeInTheDocument();
  });

  it("does not append a target suffix for other kinds", () => {
    mockHooks([{ ...baseDraft, kind: "readme_suggestion", target: "readme", content: { current: "# Old", suggested: "# New", reason: null } }]);
    render(<DraftsClient />);
    expect(screen.getByText(/README suggestion/)).toBeInTheDocument();
    expect(screen.queryByText(/\(readme\)/)).not.toBeInTheDocument();
  });
});
