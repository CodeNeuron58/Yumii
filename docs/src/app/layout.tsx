import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Header } from "@/components/Header";
import { NavigationSidebar } from "@/components/NavigationSidebar";
import { TableOfContents } from "@/components/TableOfContents";
import { PageTransition } from "@/components/PageTransition";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Yumi Documentation",
  description: "Real-time AI companion for terminal-native interaction.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${geistSans.variable} ${geistMono.variable} font-sans min-h-screen antialiased bg-docs-bg text-[#C9D1D9]`}>
        {/* Global Atmospheric Background */}
        <div className="fixed inset-0 z-0 pointer-events-none flex justify-center overflow-hidden">
          {/* Subtle Grid Overlay */}
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff08_1px,transparent_1px),linear-gradient(to_bottom,#ffffff08_1px,transparent_1px)] bg-[size:32px_32px] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_10%,#000_40%,transparent_100%)]"></div>
          
          {/* Grain/Noise Texture for Depth */}
          <div 
            className="absolute inset-0 opacity-[0.03] mix-blend-overlay" 
            style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=%220 0 200 200%22 xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cfilter id=%22noiseFilter%22%3E%3CfeTurbulence type=%22fractalNoise%22 baseFrequency=%220.85%22 numOctaves=%223%22 stitchTiles=%22stitch%22/%3E%3C/filter%3E%3Crect width=%22100%25%22 height=%22100%25%22 filter=%22url(%23noiseFilter)%22/%3E%3C/svg%3E")' }}
          ></div>

          {/* Radial Green Glow */}
          <div className="absolute top-0 w-full max-w-3xl h-[600px] bg-yumi-green/5 blur-[120px] rounded-full translate-y-[-20%]"></div>
        </div>

        {/* Application Content */}
        <div className="relative z-10 flex flex-col min-h-screen">
          <Header />

          <div className="flex-1 flex max-w-[1600px] mx-auto w-full relative">
            <NavigationSidebar />

            <main className="flex-1 min-w-0 p-8 lg:p-12" data-purpose="documentation-content">
              <PageTransition>
                {children}
              </PageTransition>
            </main>

            <TableOfContents />
          </div>
        </div>
      </body>
    </html>
  );
}