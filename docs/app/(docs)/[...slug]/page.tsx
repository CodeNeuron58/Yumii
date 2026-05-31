import fs from 'fs';
import path from 'path';
import { MDXRemote } from 'next-mdx-remote/rsc';
import matter from 'gray-matter';
import { Rocket, AudioLines, Smile, Box, LayoutDashboard } from 'lucide-react';

const IconMap: Record<string, React.FC<any>> = {
  rocket: Rocket,
  'waveform-lines': AudioLines,
  'face-smile': Smile,
  cube: Box,
  'layout-dashboard': LayoutDashboard,
};

// Helper to generate clean IDs for headings
const slugify = (text: any) => {
  if (!text) return '';
  const content = typeof text === 'string' ? text : text.toString();
  return content
    .toLowerCase()
    .trim()
    .replace(/\s+/g, '-')
    .replace(/[^\w-]+/g, '')
    .replace(/--+/g, '-');
};

// Custom components mapping
const components = {
  CardGroup: ({ children, cols }: any) => (
    <div className={`cards-grid ${cols === 4 ? 'cols-4' : ''}`}>
      {children}
    </div>
  ),
  Card: ({ title, icon, href, children }: any) => {
    const IconComponent = IconMap[icon] || Box;
    return (
      <a href={href} className="card" style={{ textDecoration: 'none' }}>
        <div className="card-icon">
          <IconComponent size={22} strokeWidth={1.5} />
        </div>
        <h3>{title}</h3>
        <div className="text-content" style={{ margin: 0 }}>
          {children}
        </div>
        <div className="card-arrow">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="5" y1="12" x2="19" y2="12"></line>
            <polyline points="12 5 19 12 12 19"></polyline>
          </svg>
        </div>
      </a>
    );
  },
  HeroSection: () => (
    <section className="hero-section">
      <div className="hero-bottom-fade"></div>
      <div className="hero-floor"></div>
      <img
        src="/mascot.png"
        className="hero-mascot"
        alt="Yumi"
      />
    </section>
  ),
  Info: ({ children }: any) => (
    <div className="info-callout">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: '2px', color: '#4ade80' }}>
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
  h1: (props: any) => <h1 id={slugify(props.children)} {...props} />,
  h2: (props: any) => <h2 id={slugify(props.children)} {...props} />,
  h3: (props: any) => <h3 id={slugify(props.children)} {...props} />,
  p: (props: any) => <p {...props} />,
  img: (props: any) => <img {...props} style={{ borderRadius: '10px', marginBottom: '28px', maxWidth: '100%' }} />,
  code: (props: any) => {
    // Inline code
    if (!props.className) {
      return <code style={{ fontFamily: 'var(--font-mono)', fontSize: '0.825rem', backgroundColor: 'rgba(74, 222, 128, 0.08)', color: 'var(--text-accent)', padding: '2px 6px', borderRadius: '4px', border: '1px solid rgba(74, 222, 128, 0.18)', whiteSpace: 'nowrap' }} {...props} />;
    }
    return <code {...props} />;
  }
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
    return (
      <div className="text-content">
        <h1>404 — Not Found</h1>
        <p>The documentation page you are looking for does not exist yet.</p>
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
      {data.title && <h1 id={slugify(data.title)}>{data.title}</h1>}
      <div className="text-content">
        <MDXRemote source={content} components={components} />
      </div>
    </>
  );
}
