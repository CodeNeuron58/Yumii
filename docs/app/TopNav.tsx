'use client';

import Link from "next/link";
import { usePathname } from "next/navigation";
import ThemeToggle from "./ThemeToggle";
import DiscordLink from "./DiscordLink";

const NAV_SECTIONS = [
  { label: "Get Started", href: "/introduction", match: ["introduction", "quickstart", "get-started"] },
  { label: "Installation", href: "/installation/windows", match: ["installation"] },
  { label: "Core Senses", href: "/senses/vad", match: ["senses"] },
  { label: "Customization", href: "/customization/adding-avatars", match: ["customization"] },
  { label: "Capabilities", href: "/capabilities/system-tools", match: ["capabilities"] },
  { label: "Integration", href: "/integration/websocket-protocol", match: ["integration"] },
  { label: "Ops & Reference", href: "/ops/troubleshooting", match: ["ops"] },
];

export default function TopNav() {
  const pathname = usePathname();

  const isActive = (section: typeof NAV_SECTIONS[0]) => {
    const segments = pathname.split("/").filter(Boolean);
    if (segments.length === 0) return section.match.includes("introduction");
    return section.match.some((m) => segments[0] === m);
  };

  return (
    <header className="top-nav">
      {/* Row 1: Logo + Search + Links */}
      <div className="top-nav-row top-nav-row--primary">
        <Link href="/" className="logo" style={{ textDecoration: "none" }}>
          <img src="/images/yumi-nav.png" alt="Yumi" style={{ height: "28px", width: "auto" }} />
          <span>Yumi</span>
        </Link>

        <div className="search-bar">
          <button className="search-input" aria-label="Search documentation">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="search-icon">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            Search...
            <span className="shortcut">⌘K</span>
          </button>
        </div>

        <div className="nav-links">
          <a href="https://github.com/CodeNeuron58/Yumi" target="_blank" rel="noopener noreferrer" className="nav-link">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path>
            </svg>
            GitHub
          </a>
          <DiscordLink />
          <ThemeToggle />
        </div>
      </div>

      {/* Row 2: Section tabs */}
      <div className="top-nav-row top-nav-row--tabs">
        <nav className="section-tabs" aria-label="Documentation sections">
          {NAV_SECTIONS.map((section) => (
            <Link
              key={section.href}
              href={section.href}
              className={`section-tab ${isActive(section) ? "section-tab--active" : ""}`}
            >
              {section.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
