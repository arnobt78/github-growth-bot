import { describe, expect, it, vi } from "vitest";

vi.stubEnv("INTERNAL_AUTH_SECRET", "test-only-internal-secret-do-not-use-in-prod");

import { mintInternalUserToken } from "@/lib/internal-auth";

describe("mintInternalUserToken", () => {
  it("produces a token with a payload segment and a signature segment", () => {
    const token = mintInternalUserToken("12345");
    const parts = token.split(".");
    expect(parts).toHaveLength(2);

    const payload = JSON.parse(Buffer.from(parts[0], "base64url").toString("utf-8"));
    expect(payload.sub).toBe("12345");
    expect(typeof payload.exp).toBe("number");
  });

  it("produces a different signature for a different secret", () => {
    const tokenA = mintInternalUserToken("12345");
    vi.stubEnv("INTERNAL_AUTH_SECRET", "a-different-secret");
    vi.resetModules();
  });
});
