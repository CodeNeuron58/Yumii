"use client";

import { MessageSquareText } from "lucide-react";
import { toast } from "sonner";

export default function DiscordLink() {
  return (
    <a
      href="#"
      className="nav-utility"
      onClick={(event) => {
        event.preventDefault();
        toast("Discord is coming soon. Stay tuned.");
      }}
    >
      <MessageSquareText size={14} />
      Discord
    </a>
  );
}
