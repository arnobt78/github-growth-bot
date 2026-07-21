import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { queryKeys } from "@/lib/query-keys";
import { useLiveEvents } from "@/hooks/use-live-events";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  listeners: Record<string, ((event: MessageEvent) => void)[]> = {};

  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, handler: (event: MessageEvent) => void) {
    this.listeners[type] = [...(this.listeners[type] ?? []), handler];
  }

  emit(type: string, data: unknown) {
    for (const handler of this.listeners[type] ?? []) {
      handler({ type, data: JSON.stringify(data) } as MessageEvent);
    }
  }

  close() {}
}

function Harness() {
  useLiveEvents();
  return null;
}

describe("useLiveEvents", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("invalidates the repos query when a repo_added event arrives", () => {
    const queryClient = new QueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    render(
      <QueryClientProvider client={queryClient}>
        <Harness />
      </QueryClientProvider>,
    );

    const source = FakeEventSource.instances[0];
    source.emit("repo_added", { id: 1 });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: queryKeys.repos.all });
  });
});
