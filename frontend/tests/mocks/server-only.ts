// Test-only stub for the `server-only` marker package. Its real implementation
// throws unconditionally unless resolved under the "react-server" export
// condition, which Vitest's jsdom environment never sets — so any module
// under test that imports "server-only" (lib/internal-auth.ts,
// lib/backend-client.ts) needs this alias (see vitest.config.ts) to avoid a
// spurious "cannot be imported from a Client Component" failure in tests.
export {};
