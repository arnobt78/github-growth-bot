import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DeltaBadge } from "@/components/ui/delta-badge";

describe("DeltaBadge", () => {
  it("shows a positive delta with a plus sign", () => {
    render(<DeltaBadge value={5} label="Stars change" />);
    expect(screen.getByText("+5")).toBeInTheDocument();
  });

  it("shows a negative delta without a plus sign", () => {
    render(<DeltaBadge value={-3} label="Stars change" />);
    expect(screen.getByText("-3")).toBeInTheDocument();
  });

  it("shows zero with no change", () => {
    render(<DeltaBadge value={0} label="Stars change" />);
    expect(screen.getByLabelText("Stars change: no change")).toBeInTheDocument();
  });
});
