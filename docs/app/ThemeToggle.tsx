'use client';

import { MoonStar } from "lucide-react";
import { toast } from "sonner";

export default function ThemeToggle() {
  return (
    <button
      className="theme-toggle nav-utility nav-utility--icon"
      onClick={() => toast("Terminal aesthetics currently support dark mode only.")}
      aria-label="Toggle theme"
      title="Only dark mode is supported"
      type="button"
    >
      <MoonStar size={14} aria-hidden="true" />
    </button>
  );
}
