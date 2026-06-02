import fs from 'fs';
import path from 'path';
import { MDXRemote } from 'next-mdx-remote/rsc';
import matter from 'gray-matter';
import { Rocket, AudioLines, Smile, Box, LayoutDashboard } from 'lucide-react';

import CodeBlock from '../../CodeBlock';
import SectionContainer from '../../components/docs/SectionContainer';
import DocsHero from '../../components/docs/DocsHero';
import DocsCard from '../../components/docs/DocsCard';
import FeatureList from '../../components/docs/FeatureList';
import Callout from '../../components/docs/Callout';
import StepsList, { Step } from '../../components/docs/StepsList';
import MascotHero from '../../components/docs/MascotHero';
import ContentCard from '../../components/docs/ContentCard';
import CodeCard from '../../components/docs/CodeCard';
import MDXPre from '../../MDXPre';

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
  SectionContainer,
  DocsHero,
  MascotHero,
  ContentCard,
  DocsCard,
  FeatureList,
  Callout,
  StepsList,
  Step,
  CodeCard,
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
  img: (props: any) => {
    let src = props.src;
    if (typeof src === 'string' && src.startsWith('/') && !src.startsWith('/docs/')) {
      src = '/docs' + src;
    }
    return <img {...props} src={src} style={{ borderRadius: '10px', marginBottom: '28px', maxWidth: '100%' }} />;
  },
  // Async RSC — handles ALL markdown code fences with terminal-style card
  pre: MDXPre,
  code: (props: any) => {
    // Inline code only (no className means it's not a fenced block)
    if (!props.className) {
      return <code className="inline-code" {...props} />;
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
    <SectionContainer className={data.layout === 'cards' ? 'layout-cards' : ''}>
      {data.sidebarTitle && (
        <div className="breadcrumb">
          <span className="badge">{data.sidebarTitle.toUpperCase()}</span>
        </div>
      )}
      {data.title && !data.hideHero && <DocsHero title={data.title} subtitle={data.description} icon={data.icon} />}
      <div className="text-content">
        <MDXRemote source={content} components={components} />
      </div>
    </SectionContainer>
  );
}
