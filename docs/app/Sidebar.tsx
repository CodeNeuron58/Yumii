'use client';

import Link from "next/link";
import { usePathname } from "next/navigation";

const SEGMENT_TO_SECTION_ID: Record<string, string> = {
  "introduction": "get-started",
  "quickstart": "get-started",
  "get-started": "get-started",
  "installation": "installation",
  "senses": "core-senses",
  "customization": "customization",
  "capabilities": "capabilities",
  "integration": "integration",
  "ops": "ops-reference"
};

function formatLabel(page: string) {
  // Extract the page filename and format as a title
  const base = page.split("/").pop()!;
  
  // Custom manual mappings for acronyms and specific formatting
  const customMap: Record<string, string> = {
    "vad": "VAD (Silero)",
    "cli": "CLI Reference",
    "api": "API Reference",
    "mcp-server": "MCP Server",
    "wsl2": "Windows (WSL2)",
    "macos": "macOS",
    "linux": "Linux",
    "windows": "Windows",
  };

  if (customMap[base.toLowerCase()]) {
    return customMap[base.toLowerCase()];
  }

  return base
    .replace(/-/g, " ")
    .replace(/\b\w/g, (l) => l.toUpperCase());
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
  const activeSection = sections.find((s) => s.id === sectionId);
  const sectionGroups = activeSection ? activeSection.groups : [];

  return (
    <aside className="left-sidebar">
      <nav>
        {sectionGroups.map((group: any, i: number) => (
          <div key={i} className="nav-section">
            <h4 className="nav-section-title">{group.group}</h4>
            <ul>
              {group.pages.map((page: string, j: number) => {
                const href = `/${page}`;
                const isActive =
                  pathname === href ||
                  (pathname === "/" && page === "introduction");

                return (
                  <li key={j} className={isActive ? "active" : ""}>
                    <Link
                      href={href}
                      style={{
                        textDecoration: "none",
                        color: "inherit",
                        display: "block",
                        width: "100%",
                      }}
                    >
                      {formatLabel(page)}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  );
}
