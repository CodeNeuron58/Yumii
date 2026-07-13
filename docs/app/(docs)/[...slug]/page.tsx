import fs from 'fs';
import path from 'path';
import Link from 'next/link';
import { MDXRemote } from 'next-mdx-remote/rsc';
import matter from 'gray-matter';
import remarkGfm from 'remark-gfm';
import {
  CubeIcon,
  RocketLaunchIcon,
  SmileyIcon,
  SquaresFourIcon,
  WaveformIcon,
} from '@phosphor-icons/react/dist/ssr';

import CodeBlock from '../../CodeBlock';
import SectionContainer from '../../components/docs/SectionContainer';
import DocsHero from '../../components/docs/DocsHero';
import DocsCard from '../../components/docs/DocsCard';
import FeatureList from '../../components/docs/FeatureList';
import Callout from '../../components/docs/Callout';
import StepsList, { Step } from '../../components/docs/StepsList';
import OrbHero from '../../components/docs/OrbHero';
import ContentCard from '../../components/docs/ContentCard';
import CodeCard from '../../components/docs/CodeCard';
import MDXPre from '../../MDXPre';

const IconMap: Record<string, React.FC<any>> = {
  rocket: RocketLaunchIcon,
  'waveform-lines': WaveformIcon,
  'face-smile': SmileyIcon,
  cube: CubeIcon,
  'layout-dashboard': SquaresFourIcon,
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
  OrbHero,
  // Back-compat alias: older MDX may still use <MascotHero>.
  MascotHero: OrbHero,
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
  // Internal links go through next/link so the /docs basePath is applied;
  // a plain <a href="/guide/tools"> would escape the basePath and 404.
  a: ({ href, children, ...rest }: any) => {
    if (typeof href === 'string' && href.startsWith('/') && !href.startsWith('//')) {
      return <Link href={href} {...rest}>{children}</Link>;
    }
    const external = typeof href === 'string' && /^https?:\/\//.test(href);
    return (
      <a
        href={href}
        {...(external ? { target: '_blank', rel: 'noreferrer noopener' } : {})}
        {...rest}
      >
        {children}
      </a>
    );
  },
  // Wide reference tables scroll inside their own container on small screens
  table: (props: any) => (
    <div className="table-wrap">
      <table {...props} />
    </div>
  ),
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
        <MDXRemote
          source={content}
          components={components}
          options={{ mdxOptions: { remarkPlugins: [remarkGfm] } }}
        />
      </div>
    </SectionContainer>
  );
}
