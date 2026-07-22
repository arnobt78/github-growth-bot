import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    globals: true,
  },
  resolve: {
    alias: {
      // Server-only-marked modules (lib/internal-auth.ts, lib/backend-client.ts)
      // import "server-only", which throws unless resolved under the
      // "react-server" export condition — jsdom tests never set that
      // condition, so alias to a no-op stub. See tests/mocks/server-only.ts.
      "server-only": new URL("./tests/mocks/server-only.ts", import.meta.url).pathname,
      "@": new URL(".", import.meta.url).pathname,
    },
  },
});
