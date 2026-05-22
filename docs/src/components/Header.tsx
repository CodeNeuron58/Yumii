"use client";

import Link from "next/link";
import { Search, Sun } from "lucide-react";
import { motion } from "framer-motion";

export function Header() {
  return (
    <header
      className="sticky top-0 z-50 w-full border-b border-docs-border bg-docs-bg/80 backdrop-blur-md"
      data-purpose="site-header"
    >
      <div className="max-w-[1600px] mx-auto px-4 h-16 flex items-center justify-between">
        {/* Logo Section */}
        <Link href="/" className="flex items-center gap-2 group">
          <div className="w-8 h-8 bg-yumi-green/20 rounded flex items-center justify-center overflow-hidden border border-yumi-green/30 group-hover:border-yumi-green transition-colors">
            <img
              alt="Yumi Logo"
              className="w-8 h-8 object-cover"
              src="/yumi-hero.png"
            />
          </div>
          <span className="text-xl font-bold text-white tracking-tight group-hover:text-yumi-green transition-colors">Yumi</span>
        </Link>
        
        {/* Search and AI Section */}
        <div className="flex-1 max-w-2xl px-8 flex items-center gap-4">
          <div className="relative w-full group">
            <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none">
              <Search className="w-4 h-4 text-docs-text-muted group-hover:text-yumi-green transition-colors" />
            </div>
            <input
              className="w-full bg-[#161b22] border border-docs-border rounded-md py-1.5 pl-10 pr-16 text-sm focus:ring-1 focus:ring-yumi-green focus:border-yumi-green outline-none transition-all shadow-inner"
              placeholder="Search documentation..."
              type="text"
            />
            <div className="absolute inset-y-0 right-3 flex items-center">
              <kbd className="hidden sm:inline-block px-1.5 py-0.5 text-xs font-mono font-semibold text-docs-text-muted border border-docs-border rounded bg-docs-bg">
                Ctrl K
              </kbd>
            </div>
          </div>
          <motion.button 
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="flex items-center gap-2 px-4 py-1.5 bg-[#161b22] border border-docs-border rounded-md text-sm font-medium hover:bg-[#21262d] hover:border-yumi-green/50 hover:text-yumi-green transition-all whitespace-nowrap shadow-sm"
          >
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yumi-green opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-yumi-green"></span>
            </span>
            Ask AI
          </motion.button>
        </div>

        {/* Social and Theme Toggle */}
        <div className="flex items-center gap-5 text-docs-text-muted">
          <motion.a 
            whileHover={{ scale: 1.1, rotate: 5 }}
            className="hover:text-white transition-colors" 
            href="#" 
            title="GitHub"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"></path>
            </svg>
          </motion.a>
          <motion.a 
            whileHover={{ scale: 1.1, rotate: -5 }}
            className="hover:text-white transition-colors" 
            href="#" 
            title="Discord"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515a.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0a12.64 12.64 0 0 0-.617-1.25a.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057a19.9 19.9 0 0 0 5.993 3.03a.078.078 0 0 0 .084-.028a14.09 14.09 0 0 0 1.226-1.994a.076.076 0 0 0-.041-.106a13.107 13.107 0 0 1-1.872-.892a.077.077 0 0 1-.008-.128a10.2 10.2 0 0 0 .372-.292a.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127a12.299 12.299 0 0 1-1.873.892a.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028a19.839 19.839 0 0 0 6.002-3.03a.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z"></path>
            </svg>
          </motion.a>
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            className="hover:text-white transition-colors"
            title="Toggle Theme"
          >
            <Sun className="w-5 h-5" />
          </motion.button>
        </div>
      </div>
    </header>
  );
}
