import React from 'react';
import { codeToHtml } from 'shiki';
import CopyButton from '../../CopyButton';

interface CodeCardProps {
  language?: string;
  code: string;
}

const LANG_LABELS: Record<string, string> = {
  bash: 'bash',
  sh: 'bash',
  shell: 'bash',
  powershell: 'powershell',
  ps1: 'powershell',
  python: 'python',
  py: 'python',
  typescript: 'typescript',
  ts: 'typescript',
  javascript: 'javascript',
  js: 'javascript',
  json: 'json',
  toml: 'toml',
  yaml: 'yaml',
  yml: 'yaml',
  txt: 'text',
  text: 'text',
};

export default async function CodeCard({ language = 'bash', code = '' }: CodeCardProps) {
  const codeString = code ? code.trim() : '';

  const normLang = language.toLowerCase();
  const displayLang = LANG_LABELS[normLang] || normLang;

  // Plain text / ASCII diagrams — no syntax highlighting
  const isPlain = normLang === '' || normLang === 'txt' || normLang === 'text';

  let html = '';
  try {
    if (isPlain) {
      // Escape HTML and wrap plainly
      const escaped = codeString
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      html = `<pre><code>${escaped}</code></pre>`;
    } else {
      html = await codeToHtml(codeString, {
        lang: displayLang,
        theme: 'github-dark',
      });
    }
  } catch (e) {
    const escaped = codeString
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    html = `<pre><code>${escaped}</code></pre>`;
  }

  return (
    <div className={`code-card ${isPlain ? 'code-card--diagram' : ''}`}>
      {/* Header bar */}
      <div className="code-card-header">
        <span className="code-card-lang">{isPlain ? 'diagram' : displayLang}</span>
        <CopyButton code={codeString} />
      </div>

      {/* Code body */}
      <div className="code-card-body" dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  );
}
