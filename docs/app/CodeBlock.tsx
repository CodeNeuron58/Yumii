import React from 'react';
import { codeToHtml } from 'shiki';
import CopyButton from './CopyButton';

interface CodeBlockProps {
  language?: string;
  children: string;
}

export default async function CodeBlock({ language = 'bash', children }: CodeBlockProps) {
  const codeString = typeof children === 'string' ? children.trim() : String(children).trim();
  
  const displayLang = language === 'bash' || language === 'sh' 
    ? 'bash' 
    : language === 'powershell' || language === 'ps1' 
    ? 'powershell' 
    : language;

  let html = '';
  try {
    html = await codeToHtml(codeString, {
      lang: displayLang,
      theme: 'github-dark' 
    });
  } catch (e) {
    html = `<pre><code>${codeString}</code></pre>`;
  }

  return (
    <div className="command-block">
      <div className="command-block-header">
        <div className="command-block-lang">{displayLang}</div>
        <CopyButton code={codeString} />
      </div>
      <div className="command-block-body" dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  );
}
