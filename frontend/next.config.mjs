const djangoApiUrl =
  process.env.DJANGO_API_URL || "http://127.0.0.1:8000";

const nextConfig = {
  output: "standalone",
  skipTrailingSlashRedirect: true,

  experimental: {
    proxyTimeout: 120000, // 2 minutes
  },
  
  async rewrites() {
    return [
      {
        source: "/triage/:path*",
        destination: `${djangoApiUrl}/triage/:path*/`,
      },
    ];
  },
};

export default nextConfig;