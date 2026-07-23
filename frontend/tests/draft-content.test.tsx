import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DraftContent } from "@/components/drafts/draft-content";

describe("DraftContent", () => {
  it("renders current/suggested panels for readme_suggestion", () => {
    render(<DraftContent kind="readme_suggestion" content={{ current: "# Old", suggested: "# New", reason: "clearer" }} />);
    expect(screen.getByText("# Old")).toBeInTheDocument();
    expect(screen.getByText("# New")).toBeInTheDocument();
  });

  it("renders a chip per suggested topic for topic_suggestion", () => {
    render(<DraftContent kind="topic_suggestion" content={{ current: ["cli"], suggested: ["cli", "automation"], reason: "broader" }} />);
    expect(screen.getByText("cli")).toBeInTheDocument();
    expect(screen.getByText("automation")).toBeInTheDocument();
  });

  it("renders description and keyword chips for seo_suggestion", () => {
    render(<DraftContent kind="seo_suggestion" content={{ current: null, suggested_description: "A great tool.", keywords: ["cli", "automation"], reason: "sharper" }} />);
    expect(screen.getByText("A great tool.")).toBeInTheDocument();
    expect(screen.getByText("cli")).toBeInTheDocument();
  });

  it("renders suggested text for missing_doc_suggestion", () => {
    render(<DraftContent kind="missing_doc_suggestion" content={{ suggested: "# Security Policy", reason: "standard template" }} />);
    expect(screen.getByText("# Security Policy")).toBeInTheDocument();
  });

  it("falls back to JSON.stringify for an unrecognized kind", () => {
    render(<DraftContent kind="future_kind" content={{ anything: 1 }} />);
    expect(screen.getByText('{"anything":1}')).toBeInTheDocument();
  });
});
