import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DraftContent } from "@/components/drafts/draft-content";

describe("DraftContent", () => {
  it("renders current/suggested panels and reason for readme_suggestion", () => {
    render(<DraftContent kind="readme_suggestion" content={{ current: "# Old", suggested: "# New", reason: "clearer" }} />);
    expect(screen.getByText("# Old")).toBeInTheDocument();
    expect(screen.getByText("# New")).toBeInTheDocument();
    expect(screen.getByText("clearer")).toBeInTheDocument();
  });

  it("renders current and suggested chips plus reason for topic_suggestion", () => {
    render(<DraftContent kind="topic_suggestion" content={{ current: ["cli"], suggested: ["cli", "automation"], reason: "broader" }} />);
    expect(screen.getAllByText("cli")).toHaveLength(2);
    expect(screen.getByText("automation")).toBeInTheDocument();
    expect(screen.getByText("broader")).toBeInTheDocument();
  });

  it("renders current/suggested description, keyword chips, and reason for seo_suggestion", () => {
    render(
      <DraftContent
        kind="seo_suggestion"
        content={{ current: "An old tool.", suggested_description: "A great tool.", keywords: ["cli", "automation"], reason: "sharper" }}
      />,
    );
    expect(screen.getByText("An old tool.")).toBeInTheDocument();
    expect(screen.getByText("A great tool.")).toBeInTheDocument();
    expect(screen.getByText("cli")).toBeInTheDocument();
    expect(screen.getByText("sharper")).toBeInTheDocument();
  });

  it("renders suggested text and reason for missing_doc_suggestion", () => {
    render(<DraftContent kind="missing_doc_suggestion" content={{ suggested: "# Security Policy", reason: "standard template" }} />);
    expect(screen.getByText("# Security Policy")).toBeInTheDocument();
    expect(screen.getByText("standard template")).toBeInTheDocument();
  });

  it("renders suggested text and reason for release_notes", () => {
    render(<DraftContent kind="release_notes" content={{ suggested: "## Features\n- Dark mode", reason: "based on the raw release body" }} />);
    expect(screen.getByText(/Dark mode/)).toBeInTheDocument();
    expect(screen.getByText("based on the raw release body")).toBeInTheDocument();
  });

  it("omits the reason line when reason is null", () => {
    render(<DraftContent kind="missing_doc_suggestion" content={{ suggested: "# Security Policy", reason: null }} />);
    expect(screen.getByText("# Security Policy")).toBeInTheDocument();
  });

  it("falls back to JSON.stringify for an unrecognized kind", () => {
    render(<DraftContent kind="future_kind" content={{ anything: 1 }} />);
    expect(screen.getByText('{"anything":1}')).toBeInTheDocument();
  });
});
