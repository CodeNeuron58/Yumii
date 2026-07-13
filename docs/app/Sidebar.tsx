'use client';

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { CaretRightIcon } from "@phosphor-icons/react";
import { formatLabel, type NavSection } from "./nav";

export default function Sidebar({ sections }: { sections: NavSection[] }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    sections.forEach((section) => (initial[section.id] = true));
    return initial;
  });

  const toggle = (id: string) =>
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));

  // The header hamburger lives in TopNav (a different tree); it signals us.
  useEffect(() => {
    const handler = () => setMobileOpen((open) => !open);
    window.addEventListener("yumii:toggle-sidebar", handler);
    return () => window.removeEventListener("yumii:toggle-sidebar", handler);
  }, []);

  // Close the drawer on navigation
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const isActive = (page: string) =>
    pathname === `/${page}` || (pathname === "/" && page === "introduction");

  return (
    <>
      {mobileOpen && (
        <div className="sidebar-overlay" onClick={() => setMobileOpen(false)} />
      )}
      <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
        <div className="sidebar-inner">
          <nav aria-label="Documentation navigation">
            {sections.map((section) => (
              <div key={section.id} className="sidebar-group">
                <button
                  className="sidebar-group-label"
                  onClick={() => toggle(section.id)}
                  aria-expanded={expanded[section.id]}
                >
                  <CaretRightIcon
                    size={12}
                    weight="bold"
                    className={`sidebar-chevron ${
                      expanded[section.id] ? "sidebar-chevron-open" : ""
                    }`}
                    aria-hidden="true"
                  />
                  {section.title}
                </button>
                {expanded[section.id] &&
                  section.groups.map((group) => (
                    <div key={group.group}>
                      {section.groups.length > 1 && (
                        <div className="sidebar-subgroup">{group.group}</div>
                      )}
                      <ul className="sidebar-links">
                        {group.pages.map((page) => (
                          <li key={page}>
                            <Link
                              href={`/${page}`}
                              className={`sidebar-link ${
                                isActive(page) ? "sidebar-link-active" : ""
                              }`}
                            >
                              {formatLabel(page)}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
              </div>
            ))}
          </nav>
        </div>
      </aside>
    </>
  );
}
