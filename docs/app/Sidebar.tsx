'use client';

import Link from "next/link";
import { usePathname } from "next/navigation";

const SEGMENT_TO_SECTION_ID: Record<string, string> = {
  introduction: "get-started",
  quickstart: "get-started",
  "get-started": "get-started",
  installation: "installation",
  senses: "core-senses",
  customization: "customization",
  capabilities: "capabilities",
  integration: "integration",
  ops: "ops-reference",
};

function formatLabel(page: string) {
  const base = page.split("/").pop() || page;

  const customMap: Record<string, string> = {
    vad: "VAD (Silero)",
    cli: "CLI Reference",
    api: "API Reference",
    "mcp-server": "MCP Server",
    wsl2: "Windows (WSL2)",
    macos: "macOS",
    linux: "Linux",
    windows: "Windows",
  };

  if (customMap[base.toLowerCase()]) {
    return customMap[base.toLowerCase()];
  }

  return base
    .replace(/-/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

interface SidebarProps {
  sections: {
    id: string;
    title: string;
    groups: {
      group: string;
      pages: string[];
    }[];
  }[];
}

export default function Sidebar({ sections }: SidebarProps) {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);
  const activeSegment = segments[0] || "introduction";

  const sectionId = SEGMENT_TO_SECTION_ID[activeSegment] || "get-started";
  const activeSection = sections.find((section) => section.id === sectionId);
  const sectionGroups = activeSection ? activeSection.groups : [];

  return (
    <aside className="left-sidebar">
      <div className="left-sidebar-panel">
        <nav className="sidebar-nav" aria-label="Documentation navigation">
          {sectionGroups.map((group, index) => (
            <div key={`${group.group}-${index}`} className="nav-section">
              <h4 className="nav-section-title">{group.group}</h4>
              <ul>
                {group.pages.map((page, itemIndex) => {
                  const href = `/${page}`;
                  const isActive = pathname === href || (pathname === "/" && page === "introduction");

                  return (
                    <li key={`${page}-${itemIndex}`} className={`sidebar-item ${isActive ? "active" : ""}`}>
                      <span className="sidebar-item-rail" aria-hidden="true" />
                      <Link href={href} className="sidebar-link">
                        <span className="sidebar-item-icon" aria-hidden="true" />
                        <span className="sidebar-item-label">{formatLabel(page)}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
      </div>
    </aside>
  );
}
