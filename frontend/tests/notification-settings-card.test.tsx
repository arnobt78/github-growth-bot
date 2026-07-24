import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NotificationSettingsCard } from "@/components/settings/notification-settings-card";
import * as useMeModule from "@/hooks/use-me";

describe("NotificationSettingsCard", () => {
  it("shows the GitHub email as the effective recipient when no fallback is set", () => {
    vi.spyOn(useMeModule, "useMe").mockReturnValue({
      data: { id: 1, github_id: "1", username: "octocat", avatar_url: "", email: "gh@example.com", notification_email: null, plan: "free", max_tracked_repos: 5 },
    } as ReturnType<typeof useMeModule.useMe>);
    vi.spyOn(useMeModule, "useUpdateMe").mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useMeModule.useUpdateMe>);

    render(<NotificationSettingsCard />);

    expect(screen.getByText("gh@example.com")).toBeInTheDocument();
  });

  it("shows a fallback-not-set message when neither email exists", () => {
    vi.spyOn(useMeModule, "useMe").mockReturnValue({
      data: { id: 1, github_id: "1", username: "octocat", avatar_url: "", email: null, notification_email: null, plan: "free", max_tracked_repos: 5 },
    } as ReturnType<typeof useMeModule.useMe>);
    vi.spyOn(useMeModule, "useUpdateMe").mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useMeModule.useUpdateMe>);

    render(<NotificationSettingsCard />);

    expect(screen.getByText("No email on file")).toBeInTheDocument();
  });

  it("calls updateMe with the trimmed input value on save", () => {
    const mutate = vi.fn();
    vi.spyOn(useMeModule, "useMe").mockReturnValue({
      data: { id: 1, github_id: "1", username: "octocat", avatar_url: "", email: "gh@example.com", notification_email: null, plan: "free", max_tracked_repos: 5 },
    } as ReturnType<typeof useMeModule.useMe>);
    vi.spyOn(useMeModule, "useUpdateMe").mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof useMeModule.useUpdateMe>);

    render(<NotificationSettingsCard />);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "  fallback@example.com  " } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(mutate).toHaveBeenCalledWith(
      { notification_email: "fallback@example.com" },
      expect.objectContaining({ onError: expect.any(Function) }),
    );
  });
});
