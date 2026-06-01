import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import ThemeToggle from "./ThemeToggle";
import DiscordLink from "./DiscordLink";
import TopNav from "./TopNav";
import { Toaster } from 'sonner';

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
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Black+Ops+One&family=Inter:wght@300;400;500;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:ital,wght@0,100..800;1,100..800&display=swap" rel="stylesheet" />
      </head>
      <body>
        <div className="app-container">
          <TopNav />
          {children}
          <Toaster theme="dark" position="bottom-right" />
          <script dangerouslySetInnerHTML={{
            __html: `
              if (typeof window !== 'undefined') {
                document.addEventListener('mousemove', function(e) {
                  const cards = document.querySelectorAll('.card');
                  cards.forEach(card => {
                    const rect = card.getBoundingClientRect();
                    const x = e.clientX - rect.left;
                    const y = e.clientY - rect.top;
                    card.style.setProperty('--mouse-x', \`\${x}px\`);
                    card.style.setProperty('--mouse-y', \`\${y}px\`);
                  });
                });
              }
            `
          }} />
        </div>
      </body>
    </html>
  );
}
