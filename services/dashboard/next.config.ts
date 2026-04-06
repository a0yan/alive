import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output produces a self-contained server.js that doesn't need
  // node_modules at runtime — much smaller Docker image.
  output: 'standalone',
};

export default nextConfig;
