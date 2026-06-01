/** @type {import('next').NextConfig} */
const nextConfig = {
  // Separate directories to prevent 'npm run build' from wiping active dev server assets
  distDir: process.env.NODE_ENV === 'development' ? '.next-dev' : '.next',
};

export default nextConfig;
