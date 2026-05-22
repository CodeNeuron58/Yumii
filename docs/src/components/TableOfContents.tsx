"use client";

import { useEffect, useState } from "react";
import { List } from "lucide-react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface Heading {
  id: string;
  text: string;
  level: number;
}

export function TableOfContents() {
  const [headings, setHeadings] = useState<Heading[]>([]);
  const [activeId, setActiveId] = useState<string>("");

  useEffect(() => {
    // Small delay to ensure MDX content has mounted and rendered
    const timer = setTimeout(() => {
      const elements = Array.from(document.querySelectorAll("main h2, main h3"));
      
      const parsedHeadings = elements.map((elem) => ({
        id: elem.id,
        text: elem.textContent || "",
        level: elem.tagName === "H2" ? 2 : 3,
      })).filter(h => h.id); // Only include headings with IDs
      
      setHeadings(parsedHeadings);

      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              setActiveId(entry.target.id);
            }
          });
        },
        { rootMargin: "0px 0px -60% 0px" }
      );

      elements.forEach((elem) => observer.observe(elem));

      return () => {
        elements.forEach((elem) => observer.unobserve(elem));
        observer.disconnect();
      };
    }, 100);

    return () => clearTimeout(timer);
  }, []); // Run once on mount

  if (headings.length === 0) {
    return (
      <aside className="w-64 shrink-0 hidden xl:block" />
    );
  }

  return (
    <aside
      className="w-64 shrink-0 hidden xl:block"
      data-purpose="on-this-page-sidebar"
    >
      <div className="sticky top-16 h-[calc(100vh-4rem)] overflow-y-auto custom-scrollbar">
        <nav className="p-8 pb-24">
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-xs font-bold text-white uppercase tracking-widest">
              <List className="w-4 h-4" />
              On this page
            </div>
            <ul className="space-y-3 text-sm relative border-l border-[#30363d] ml-2">
              {headings.map((heading) => {
                const isActive = activeId === heading.id;
                
                return (
                  <li
                    key={heading.id}
                    className={cn(
                      "relative pl-4 transition-colors",
                      heading.level === 3 && "ml-3"
                    )}
                  >
                    {isActive && (
                      <motion.div
                        layoutId="active-toc"
                        className="absolute left-[-1px] top-0 bottom-0 w-[2px] bg-yumi-green"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ type: "spring", stiffness: 300, damping: 30 }}
                      />
                    )}
                    <a
                      href={`#${heading.id}`}
                      className={cn(
                        "block hover:text-white transition-colors",
                        isActive
                          ? "text-yumi-green font-medium"
                          : "text-docs-text-muted"
                      )}
                    >
                      {heading.text}
                    </a>
                  </li>
                );
              })}
            </ul>
          </div>
        </nav>
      </div>
    </aside>
  );
}
