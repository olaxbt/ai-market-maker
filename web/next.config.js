/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export for S3/CloudFront hosting.
  output: "export",
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
};
module.exports = nextConfig;
