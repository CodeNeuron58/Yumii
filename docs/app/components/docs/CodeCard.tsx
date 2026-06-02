import React from 'react';
import { codeToHtml } from 'shiki';
import CopyButton from '../../CopyButton';

interface CodeCardProps {
  language?: string;
  code: string;
}

export default async function CodeCard({ language = 'bash', code = '' }: CodeCardProps) {
  console.log("CodeCard received code:", typeof code, code);
  const codeString = code ? code.trim() : '';
  
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
    <div className="code-card">
      <div className="code-card-body" dangerouslySetInnerHTML={{ __html: html }} />
      <div className="code-card-actions">
        <CopyButton code={codeString} />
      </div>
    </div>
  );
}
