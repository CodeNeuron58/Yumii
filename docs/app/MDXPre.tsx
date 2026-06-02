import React from 'react';
import { codeToHtml } from 'shiki';
import CopyButton from './CopyButton';

const LANG_LABELS: Record<string, string> = {
  bash:       'bash',
  sh:         'bash',
  shell:      'bash',
  powershell: 'powershell',
  ps1:        'powershell',
  python:     'python',
  py:         'python',
  typescript: 'typescript',
  ts:         'typescript',
  javascript: 'javascript',
  js:         'javascript',
  json:       'json',
  toml:       'toml',
  yaml:       'yaml',
  yml:        'yaml',
  txt:        'text',
  text:       'text',
};

// Shiki language IDs that are valid — everything else falls back to plain text
const SHIKI_LANGS = new Set([
  'bash','sh','shell','powershell','ps1',
  'python','py','typescript','ts','javascript','js',
  'json','toml','yaml','yml','txt','text',
  'html','css','scss','sql','rust','go','java','c','cpp','dockerfile',
]);

function extractCode(children: any): string {
  if (typeof children === 'string') return children;
  if (Array.isArray(children)) {
    return children
      .map((c: any) => (typeof c === 'string' ? c : c?.props?.children ?? ''))
      .join('');
  }
  if (typeof children === 'object' && children !== null) {
    return children?.props?.children ?? '';
  }
  return '';
}

/**
 * Async RSC that handles all markdown code fences.
 * Mapped as `pre` in the MDX components object so every
 * ``` code block ``` goes through this renderer.
 */
export default async function MDXPre({ children, ...rest }: any) {
  // MDX wraps fenced code as <pre><code className="language-X">...</code></pre>
  // For no-language fences (``` without a tag), className is empty/missing.
  // We detect a fenced block by the presence of a child element with props
  // (React elements have props; plain text children do not).
  const codeEl = children;

  // If children has no props (it's a string or null), render as plain <pre>
  if (!codeEl || typeof codeEl !== 'object' || !('props' in codeEl)) {
    return <pre {...rest}>{children}</pre>;
  }

  const languageClass: string = codeEl.props?.className ?? '';
  const rawLang = languageClass.replace(/^language-/, '').toLowerCase().trim();
  const displayLang = LANG_LABELS[rawLang] ?? rawLang;

  // Empty language = no-language fence → treat as diagram / plain text
  const isDiagram = rawLang === '';
  const shikiLang = !isDiagram && SHIKI_LANGS.has(rawLang) ? displayLang : null;

  const codeString = extractCode(codeEl.props?.children).trimEnd();

  // Run Shiki (or plain escape for diagram blocks)
  let html = '';
  try {
    if (shikiLang) {
      html = await codeToHtml(codeString, {
        lang: shikiLang,
        theme: 'github-dark',
      });
    } else {
      // Diagram / unknown language — plain monospace, no syntax colours
      const escaped = codeString
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      html = `<pre><code>${escaped}</code></pre>`;
    }
  } catch {
    const escaped = codeString
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    html = `<pre><code>${escaped}</code></pre>`;
  }

  const badgeLabel = isDiagram ? 'diagram' : (displayLang || 'code');

  return (
    <div className={`code-card${isDiagram ? ' code-card--diagram' : ''}`}>
      {/* ── Header bar: language badge + copy button ── */}
      <div className="code-card-header">
        <span className="code-card-lang">{badgeLabel}</span>
        <CopyButton code={codeString} />
      </div>

      {/* ── Highlighted code body ── */}
      <div
        className="code-card-body"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
