export type NavGroup = {
  group: string;
  pages: string[];
};

export type NavSection = {
  id: string;
  title: string;
  groups: NavGroup[];
};

const CUSTOM_LABELS: Record<string, string> = {
  "what-is-yumii": "What is Yumii?",
  "first-conversation": "First Conversation",
  llm: "Language Models",
  stt: "Speech-to-Text",
  tts: "Text-to-Speech",
  files: "File Locations",
  settings: "Settings Reference",
  cli: "CLI Reference",
  api: "HTTP API & WebSocket",
  "from-source": "Running from Source",
  packaging: "Building the Installer",
};

export function formatLabel(page: string) {
  const base = page.split("/").pop() || page;
  const custom = CUSTOM_LABELS[base.toLowerCase()];
  if (custom) return custom;
  return base.replace(/-/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

/** Flat list of every page for the search modal. */
export function flattenPages(sections: NavSection[]) {
  return sections.flatMap((section) =>
    section.groups.flatMap((group) =>
      group.pages.map((page) => ({
        slug: page,
        label: formatLabel(page),
        section: section.title,
      }))
    )
  );
}
