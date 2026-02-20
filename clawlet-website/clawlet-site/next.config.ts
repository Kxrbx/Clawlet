import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow Tailscale network and localhost in dev
  allowedDevOrigins: [
    "100.64.0.0/10",       // Tailscale IPv4 range
    "100.111.162.48/32",   // Specific VPS Tailscale IP
    "fd7a:115c:a1e0:/64",  // Tailscale IPv6 range
    "localhost",
    "0.0.0.0",
  ],
};

export default nextConfig;
