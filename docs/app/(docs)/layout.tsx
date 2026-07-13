import fs from "fs";
import path from "path";
import Sidebar from "../Sidebar";
import TableOfContents from "../TableOfContents";
import type { NavSection } from "../nav";

function getNavigation(): NavSection[] {
  try {
    const filePath = path.join(process.cwd(), "content", "docs.json");
    const fileContents = fs.readFileSync(filePath, "utf8");
    const data = JSON.parse(fileContents);
    return data.navigation.sections || [];
  } catch (e) {
    console.error("Error reading docs.json", e);
    return [];
  }
}

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  const sections = getNavigation();

  return (
    <div className="docs-layout">
      <Sidebar sections={sections} />

      <main id="main-content" className="docs-main">
        <div className="docs-content">{children}</div>
      </main>

      <div className="toc-rail">
        <TableOfContents />
      </div>
    </div>
  );
}
