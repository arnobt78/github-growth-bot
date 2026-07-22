import "server-only";
import { createHmac } from "node:crypto";

const SECRET = process.env.INTERNAL_AUTH_SECRET ?? "";
const TOKEN_TTL_SECONDS = 60;

// Signed, short-lived proof of "this request's user id was verified by our
// own Auth.js session check, not supplied by the browser." Verified by the
// backend's app/internal_auth.py::verify_internal_user_token — the payload
// and signature format must match exactly (see that file's docstring).
export function mintInternalUserToken(githubId: string): string {
  const payload = JSON.stringify({
    sub: githubId,
    exp: Math.floor(Date.now() / 1000) + TOKEN_TTL_SECONDS,
  });
  const payloadB64 = Buffer.from(payload, "utf-8").toString("base64url");
  const signature = createHmac("sha256", SECRET).update(payloadB64).digest("hex");
  return `${payloadB64}.${signature}`;
}
