import type { Metadata } from "next";
import fs from "fs";
import path from "path";
import { Bricolage_Grotesque, DM_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import TopNav from "./TopNav";
import type { NavSection } from "./nav";

const bricolage = Bricolage_Grotesque({
  variable: "--font-bricolage",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Yumii Documentation",
  description:
    "Docs for Yumii, the open-source AI companion that lives on your desktop. Voice-first, private by design, remembers you.",
};

function getNavigation(): NavSection[] {
  try {
    const filePath = path.join(process.cwd(), "content", "docs.json");
    const fileContents = fs.readFileSync(filePath, "utf8");
    const data = JSON.parse(fileContents);
    return data.navigation.sections || [];
  } catch (e) {
    console.error("Error reading docs.json", e);
    return [];
  }
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const sections = getNavigation();

  return (
    <html
      lang="en"
      className={`dark ${bricolage.variable} ${dmSans.variable} ${jetbrainsMono.variable}`}
    >
      <head>
        <meta name="theme-color" content="#050f0a" />
      </head>
      <body>
        <div className="app-container">
          <a href="#main-content" className="skip-link">
            Skip to content
          </a>
          <TopNav sections={sections} />
          {children}
        </div>
      </body>
    </html>
  );
}
