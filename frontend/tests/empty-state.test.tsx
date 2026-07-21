import { FolderGit2 } from "lucide-react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "@/components/ui/empty-state";

describe("EmptyState", () => {
  it("renders the title and description", () => {
    render(<EmptyState icon={FolderGit2} title="No repos tracked yet" description="Add a repo to get started." />);
    expect(screen.getByText("No repos tracked yet")).toBeInTheDocument();
    expect(screen.getByText("Add a repo to get started.")).toBeInTheDocument();
  });
});
