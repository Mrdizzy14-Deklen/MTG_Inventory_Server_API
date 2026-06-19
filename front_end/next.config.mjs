/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'vm.deklenn.dev', // Whitelist your own server!
      },
      // Keep localhost here if you test locally
      {
        protocol: 'http',
        hostname: 'localhost', 
      }
    ],
  },
}

export default nextConfig
