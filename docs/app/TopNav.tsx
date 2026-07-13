'use client';

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpenText,
  Bot,
  Code2,
  Command,
  Github,
  PlugZap,
  Search,
  Server,
  type LucideIcon,
} from "lucide-react";
import ThemeToggle from "./ThemeToggle";
import DiscordLink from "./DiscordLink";

type NavSection = {
  label: string;
  href: string;
  match: string[];
  icon: LucideIcon;
};

const NAV_SECTIONS: NavSection[] = [
  { label: "Get Started", href: "/introduction", match: ["introduction", "quickstart", "get-started"], icon: BookOpenText },
  { label: "Using Yumii", href: "/guide/talking", match: ["guide"], icon: Bot },
  { label: "Providers", href: "/providers/llm", match: ["providers"], icon: PlugZap },
  { label: "Reference", href: "/reference/files", match: ["reference"], icon: Server },
  { label: "Development", href: "/development/architecture", match: ["development"], icon: Code2 },
];

export default function TopNav() {
  const pathname = usePathname();

  const isActive = (section: NavSection) => {
    const segments = pathname.split("/").filter(Boolean);
    if (segments.length === 0) return section.match.includes("introduction");
    return section.match.some((m) => segments[0] === m);
  };

  return (
    <header className="top-nav">
      <div className="top-nav-shell">
        <div className="top-nav-row top-nav-row--primary">
          <a href="/" className="logo">
            <img src="/docs/images/orb-logo.png" alt="Yumii" width={28} height={28} />
            <span>Yumii</span>
          </a>

          <div className="search-bar">
            <button className="search-input" aria-label="Search documentation">
              <Search size={14} className="search-icon" aria-hidden="true" />
              <span className="search-placeholder">Search docs, commands, or topics...</span>
              <span className="shortcut">
                <Command size={12} aria-hidden="true" />
                K
              </span>
            </button>
          </div>

          <div className="nav-links">
            <a
              href="https://github.com/CodeNeuron58/Yumii"
              target="_blank"
              rel="noopener noreferrer"
              className="nav-utility"
            >
              <Github size={14} aria-hidden="true" />
              GitHub
            </a>
            <DiscordLink />
            <ThemeToggle />
          </div>
        </div>

        <div className="top-nav-row top-nav-row--tabs">
          <nav className="section-tabs" aria-label="Documentation sections">
            {NAV_SECTIONS.map((section) => {
              const Icon = section.icon;
              return (
                <Link
                  key={section.href}
                  href={section.href}
                  className={`section-tab ${isActive(section) ? "section-tab--active" : ""}`}
                >
                  <Icon size={13} className="section-tab-icon" aria-hidden="true" />
                  <span>{section.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </div>
    </header>
  );
}
