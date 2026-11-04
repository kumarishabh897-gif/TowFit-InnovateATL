import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Opt out of Next 16.3's immutable static uploads: on Vercel they conflict with preview comments for this
  // repo's build setup. The only cost is that browsers re-download unchanged assets after each deploy.
  supportsImmutableAssets: false,
};

export default nextConfig;
