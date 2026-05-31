'use client';

import Link from "next/link";
import { usePathname } from "next/navigation";

const SECTION_MAP: Record<string, { group: string; pages: string[] }[]> = {
  "introduction": [
    {
      group: "Overview",
      pages: ["introduction", "quickstart"],
    },
  ],
  "quickstart": [
    {
      group: "Overview",
      pages: ["introduction", "quickstart"],
    },
  ],
  "core-concepts": [
    {
      group: "Core Concepts",
      pages: ["core-concepts/architecture", "core-concepts/key-features", "core-concepts/what-is-yumi"],
    },
  ],
  "guides": [
    {
      group: "Guides",
      pages: ["guides/installation", "guides/configuration", "guides/personalities", "guides/voice-setup", "guides/troubleshooting"],
    },
  ],
  "reference": [
    {
      group: "Reference",
      pages: ["reference/cli", "reference/api", "reference/events", "reference/environments"],
    },
  ],
};

function formatLabel(page: string) {
  return page
    .split("/")
    .pop()!
    .replace(/-/g, " ")
    .replace(/\b\w/g, (l) => l.toUpperCase());
}

export default function Sidebar({ groups }: { groups: any[] }) {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);
  const sectionKey = segments[0] || "introduction";

  const sectionGroups = SECTION_MAP[sectionKey] || groups;

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
