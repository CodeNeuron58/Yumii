import fs from 'fs';
import path from 'path';
import { MDXRemote } from 'next-mdx-remote/rsc';
import matter from 'gray-matter';
import { Rocket, AudioLines, Smile, Box } from 'lucide-react';

const IconMap: Record<string, React.FC<any>> = {
  rocket: Rocket,
  'waveform-lines': AudioLines,
  'face-smile': Smile,
  cube: Box
};

// Custom components mapping
const components = {
  CardGroup: ({ children, cols }: any) => <div className="cards-grid">{children}</div>,
  Card: ({ title, icon, href, children }: any) => {
    const IconComponent = IconMap[icon] || Box;
    return (
      <a href={href} className="card" style={{ textDecoration: 'none' }}>
        <div className="card-icon">
          <IconComponent size={20} color="#4ade80" strokeWidth={1.5} />
        </div>
        <h3>{title}</h3>
        {children}
        <div className="card-arrow">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#4ade80" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="5" y1="12" x2="19" y2="12"></line>
            <polyline points="12 5 19 12 12 19"></polyline>
          </svg>
        </div>
      </a>
    );
  },
  HeroSection: () => (
    <div className="hero-section">
       <div className="hero-bg-effects">
         <div className="center-glow"></div>
         <div className="center-line"></div>
         <div className="grid-lines"></div>
         <div className="bottom-glow"></div>
         <div className="bottom-line"></div>
       </div>
       <div className="mascot-container">
         <img src="/mascot.png" alt="Yumii Mascot" className="mascot-img" />
       </div>
    </div>
  ),
  Info: ({ children }: any) => (
    <div className="info-callout">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: '2px', color: '#4ade80' }}>
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="16" x2="12" y2="12"></line>
        <line x1="12" y1="8" x2="12.01" y2="8"></line>
      </svg>
      <div>{children}</div>
    </div>
  ),
  AccordionGroup: ({ children }: any) => <div className="accordion-group">{children}</div>,
  Accordion: ({ title, children }: any) => (
    <details className="accordion">
      <summary>{title}</summary>
      <div className="accordion-content">{children}</div>
    </details>
  ),
  h1: (props: any) => <h1 {...props} />,
  h2: (props: any) => <h2 {...props} />,
  p: (props: any) => <p {...props} />,
  img: (props: any) => <img {...props} style={{ borderRadius: '12px', marginBottom: '32px', maxWidth: '100%' }} />
};

export default function Page({ params }: { params: { slug?: string[] } }) {
  const slugArray = params.slug || ['introduction'];
  const slugPath = slugArray.join('/');
  
  const contentDir = path.join(process.cwd(), 'content');
  let filePath = path.join(contentDir, `${slugPath}.mdx`);
  
  if (!fs.existsSync(filePath)) {
    filePath = path.join(contentDir, slugPath, `index.mdx`);
  }
  
  if (!fs.existsSync(filePath)) {
    // If we're at root and there's no introduction.mdx, try just returning a 404
    return (
      <div className="text-content">
        <h1>404 - Not Found</h1>
        <p>The documentation page you are looking for does not exist.</p>
      </div>
    );
  }
  
  const fileContent = fs.readFileSync(filePath, 'utf8');
  const { content, data } = matter(fileContent);
  
  return (
    <>
      {data.sidebarTitle && (
        <div className="breadcrumb">
          <span className="badge">{data.sidebarTitle.toUpperCase()}</span>
        </div>
      )}
      {data.title && <h1>{data.title}</h1>}
      <div className="text-content">
        <MDXRemote source={content} components={components} />
      </div>
    </>
  );
}
