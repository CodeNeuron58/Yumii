import fs from "fs";
import path from "path";
import Sidebar from "../Sidebar";
import TableOfContents from "../TableOfContents";

function getNavigation() {
  try {
    const filePath = path.join(process.cwd(), 'content', 'docs.json');
    const fileContents = fs.readFileSync(filePath, 'utf8');
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
    <div className="main-layout">
      <Sidebar sections={sections} />

      <div className="main-scroll-container">
        <main className="content-area">
          <div className="content-inner">
            {children}
          </div>
        </main>

        <aside className="right-sidebar">
           <TableOfContents />
        </aside>
      </div>
    </div>
  );
}
