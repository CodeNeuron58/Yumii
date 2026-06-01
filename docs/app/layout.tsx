import type { Metadata } from "next";
import "./globals.css";
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
        <meta name="theme-color" content="#050505" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Geist+Mono:wght@100..900&family=Sora:wght@400;500;600&display=swap" rel="stylesheet" />
      </head>
      <body>
        <div className="app-container">
          <a href="#main-content" className="skip-link">
            Skip to content
          </a>
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
