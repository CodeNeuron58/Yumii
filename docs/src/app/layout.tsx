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
      <body className={`${geistSans.variable} ${geistMono.variable} font-sans min-h-screen flex flex-col antialiased bg-docs-bg text-[#C9D1D9]`}>
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
      </body>
    </html>
  );
}