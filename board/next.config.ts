import type { NextConfig } from "next";

const apiBase = process.env.SANKET_API ?? "http://127.0.0.1:5000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${apiBase}/api/:path*` },
      { source: "/alertcards/:path*", destination: `${apiBase}/alertcards/:path*` },
      { source: "/data/:path*", destination: `${apiBase}/data/:path*` },
    ];
  },
};

export default nextConfig;
