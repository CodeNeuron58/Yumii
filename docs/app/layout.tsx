import type { Metadata } from "next";
import "./globals.css";
import TopNav from "./TopNav";
import { Toaster } from "sonner";

export const metadata: Metadata = {
  title: "Yumii Documentation",
  description:
    "Docs for Yumii — the open-source AI companion that lives on your desktop. Voice-first, private by design, remembers you.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        <meta name="theme-color" content="#07100c" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400..600;1,9..144,400..600&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <div className="app-container">
          <a href="#main-content" className="skip-link">
            Skip to content
          </a>
          <TopNav />
          {children}
          <Toaster theme="dark" position="bottom-right" />
        </div>
      </body>
    </html>
  );
}
