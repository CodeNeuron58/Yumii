"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

const NAVIGATION = [
  {
    title: "Getting Started",
    links: [
      { title: "Overview", href: "/docs" },
      { title: "Quickstart", href: "/docs/quickstart" },
    ],
  },
  {
    title: "Core Concepts",
    links: [
      { title: "What is Yumi?", href: "/docs/core-concepts/what-is-yumi" },
      { title: "Key Features", href: "/docs/core-concepts/key-features" },
      { title: "The Architecture", href: "/docs/core-concepts/architecture" },
    ],
  },
  {
    title: "Guides",
    links: [
      { title: "Installation", href: "/docs/guides/installation" },
      { title: "Configuration", href: "/docs/guides/configuration" },
      { title: "Personalities", href: "/docs/guides/personalities" },
      { title: "Voice Setup", href: "/docs/guides/voice-setup" },
    ],
  },
  {
    title: "Reference",
    links: [
      { title: "CLI Reference", href: "/docs/reference/cli" },
      { title: "API Reference", href: "/docs/reference/api" },
      { title: "Events", href: "/docs/reference/events" },
      { title: "Environments", href: "/docs/reference/environments" },
    ],
  },
];

export function NavigationSidebar() {
  const pathname = usePathname();

  return (
    <aside
      className="w-64 shrink-0 border-r border-docs-border hidden lg:block"
      data-purpose="navigation-sidebar"
    >
      <div className="sticky top-16 h-[calc(100vh-4rem)] overflow-y-auto custom-scrollbar">
        <nav className="p-6 space-y-8 pb-24">
          {NAVIGATION.map((section) => (
            <div key={section.title} className="space-y-3">
              <h5 className="text-xs font-bold text-yumi-green uppercase tracking-widest">
                {section.title}
              </h5>
              <ul className="space-y-1 relative">
                {section.links.map((link) => {
                  const isActive = pathname === link.href;
                  return (
                    <li key={link.href} className="relative">
                      {isActive && (
                        <motion.div
                          layoutId="active-nav"
                          className="absolute inset-0 bg-[#1C2128] border-l-2 border-yumi-green rounded-r-md z-0"
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ type: "spring", stiffness: 300, damping: 30 }}
                        />
                      )}
                      <Link
                        href={link.href}
                        className={cn(
                          "relative z-10 flex items-center px-3 py-2 text-sm font-medium transition-colors",
                          isActive
                            ? "text-white"
                            : "text-docs-text-muted hover:text-white hover:bg-white/5 rounded-r-md"
                        )}
                      >
                        {link.title}
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
