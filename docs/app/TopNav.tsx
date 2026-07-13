'use client';

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  GithubLogoIcon,
  ListIcon,
  MagnifyingGlassIcon,
} from "@phosphor-icons/react";
import { flattenPages, type NavSection } from "./nav";

export default function TopNav({ sections }: { sections: NavSection[] }) {
  const router = useRouter();
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  const allPages = useMemo(() => flattenPages(sections), [sections]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return allPages
      .filter(
        (page) =>
          page.label.toLowerCase().includes(q) ||
          page.slug.toLowerCase().includes(q) ||
          page.section.toLowerCase().includes(q)
      )
      .slice(0, 8);
  }, [allPages, query]);

  // ⌘K / Ctrl+K opens search, Escape closes it
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen(true);
      }
      if (e.key === "Escape") setSearchOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    if (searchOpen && searchRef.current) searchRef.current.focus();
  }, [searchOpen]);

  const closeSearch = () => {
    setSearchOpen(false);
    setQuery("");
  };

  const goTo = (slug: string) => {
    closeSearch();
    router.push(`/${slug}`);
  };

  return (
    <>
      <header className="docs-header">
        <div className="docs-header-inner">
          <div className="docs-header-left">
            <button
              className="mobile-nav-toggle"
              onClick={() =>
                window.dispatchEvent(new CustomEvent("yumii:toggle-sidebar"))
              }
              aria-label="Toggle navigation"
            >
              <ListIcon size={20} aria-hidden="true" />
            </button>
            <Link href="/introduction" className="docs-logo" aria-label="Yumii docs home">
              <img
                src="/docs/images/orb-logo.png"
                alt=""
                width={24}
                height={24}
                className="docs-logo-img"
              />
              <span className="docs-logo-text">Yumii</span>
              <span className="docs-logo-divider" />
              <span className="docs-logo-label">Docs</span>
            </Link>
          </div>

          <button className="search-trigger" onClick={() => setSearchOpen(true)}>
            <MagnifyingGlassIcon size={15} aria-hidden="true" />
            <span>Search docs…</span>
            <kbd>Ctrl K</kbd>
          </button>

          <nav className="docs-header-links">
            <a href="/" className="docs-header-link">
              Home
            </a>
            <a
              href="https://github.com/CodeNeuron58/Yumii"
              target="_blank"
              rel="noreferrer noopener"
              className="docs-header-link"
              aria-label="GitHub repository"
            >
              <GithubLogoIcon size={16} aria-hidden="true" />
            </a>
          </nav>
        </div>
      </header>

      {searchOpen && (
        <div className="search-overlay" onClick={closeSearch}>
          <div className="search-modal" onClick={(e) => e.stopPropagation()}>
            <div className="search-input-wrap">
              <MagnifyingGlassIcon size={18} aria-hidden="true" />
              <input
                ref={searchRef}
                type="text"
                placeholder="Search documentation…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && results.length > 0) {
                    goTo(results[0].slug);
                  }
                }}
                className="search-input"
              />
              <kbd className="search-esc">esc</kbd>
            </div>
            <div className="search-results">
              {query.trim().length === 0 ? (
                <p className="search-hint">Type to search across all documentation…</p>
              ) : results.length === 0 ? (
                <p className="search-empty">No results for &ldquo;{query}&rdquo;</p>
              ) : (
                results.map((page) => (
                  <button
                    key={page.slug}
                    type="button"
                    className="search-result"
                    onClick={() => goTo(page.slug)}
                  >
                    <span className="search-result-label">{page.label}</span>
                    <span className="search-result-section">{page.section}</span>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
