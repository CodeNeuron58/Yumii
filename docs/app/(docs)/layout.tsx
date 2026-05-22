import fs from "fs";
import path from "path";
import Link from "next/link";
import TableOfContents from "../TableOfContents";

function getNavigation() {
  try {
    const filePath = path.join(process.cwd(), 'content', 'docs.json');
    const fileContents = fs.readFileSync(filePath, 'utf8');
    const data = JSON.parse(fileContents);
    return data.navigation.groups;
  } catch (e) {
    return [];
  }
}

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  const groups = getNavigation();

  return (
    <div className="main-layout">
      <aside className="left-sidebar">
        <nav>
          {groups.map((group: any, i: number) => (
            <div key={i} className="nav-section">
              <h4>{group.group.toUpperCase()}</h4>
              <ul>
                {group.pages.map((page: string, j: number) => {
                  const label = page.split('/').pop()?.replace(/-/g, ' ');
                  const capitalized = label ? label.charAt(0).toUpperCase() + label.slice(1) : '';
                  return (
                    <li key={j}>
                      <Link href={`/${page}`} style={{textDecoration: 'none', color: 'inherit'}}>
                        {capitalized}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
      </aside>

      <main className="content-area">
        <div className="content-inner">
          {children}
        </div>
      </main>

      <aside className="right-sidebar">
         <TableOfContents />
      </aside>
    </div>
  );
}
