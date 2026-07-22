import type { NextConfig } from "next";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-XSS-Protection", value: "1; mode=block" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [{ protocol: "https", hostname: "avatars.githubusercontent.com", pathname: "/**" }],
  },
  async headers() {
    // Static-asset Cache-Control is set at the Vercel edge (vercel.json) instead of
    // here — overriding it via next.config.ts's headers() triggers a Next.js build
    // warning ("can break Next.js development behavior") for no benefit in prod.
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
};

export default nextConfig;
