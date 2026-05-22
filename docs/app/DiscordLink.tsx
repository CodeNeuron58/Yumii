"use client";

import { toast } from "sonner";

export default function DiscordLink() {
  return (
    <a 
      href="#" 
      className="nav-link" 
      onClick={(e) => {
        e.preventDefault();
        toast("Discord is coming soon! Stay tuned. 🌸");
      }}
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 8c-1-1-3-1-3-1l-1 2c3 1 4 3 4 3s-1-1-3-2-4-1-8-1-6 1-6 1 1-2 4-3l-1-2s-2 0-3 1-3 5-3 5 1 5 3 6c2 1 4 1 4 1s1-2 1-2c-1 0-3-1-3-1s1-1 1-1c3 1 6 1 8 0 0 0 1 1 1 1s-2 1-3 1c0 0 2 0 4-1 2-1 3-6 3-6s0-4-3-5z"></path></svg>
      Discord
    </a>
  );
}
