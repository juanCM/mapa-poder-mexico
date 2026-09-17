import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@mapa/contracts", "@mapa/taxonomy"],
  experimental: {
    optimizePackageImports: ["lucide-react"]
  }
};

export default nextConfig;
