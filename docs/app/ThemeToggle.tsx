'use client';

import { toast } from "sonner";

export default function ThemeToggle() {
  return (
    <button 
      className="theme-toggle" 
      onClick={() => toast("Terminal aesthetics require Dark Mode! 🌙")}
      title="Only dark mode is supported"
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
      </svg>
    </button>
  );
}
