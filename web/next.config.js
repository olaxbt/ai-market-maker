/** @type {import('next').NextConfig} */
const nextConfig = {
  // We use Next route handlers (`app/api/*`) as lightweight proxies to the Python backend,
  // so we cannot use `output: "export"` (static export forbids dynamic routes).
  output: "standalone",
  trailingSlash: false,
};
module.exports = nextConfig;
