'use client';

import React, { useState } from 'react';
import { Check, Copy } from 'lucide-react';

interface CodeBlockProps {
  language?: string;
  children: string;
}

export default function CodeBlock({ language = 'bash', children }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const codeString = typeof children === 'string' 
    ? children.trim() 
    : children;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(codeString);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy code: ', err);
    }
  };

  // Nice capitalized language display
  const displayLang = language === 'bash' || language === 'sh' 
    ? 'BASH' 
    : language === 'powershell' || language === 'ps1' 
    ? 'POWERSHELL' 
    : language.toUpperCase();

  return (
    <div className="custom-code-block">
      <div className="code-block-header">
        <span className="code-block-lang">{displayLang}</span>
        <button 
          onClick={handleCopy} 
          className="code-block-copy-btn"
          aria-label="Copy code to clipboard"
        >
          {copied ? (
            <span className="copy-btn-inner text-success">
              <Check size={13} />
              <span>Copied!</span>
            </span>
          ) : (
            <span className="copy-btn-inner">
              <Copy size={13} />
              <span>Copy</span>
            </span>
          )}
        </button>
      </div>
      <div className="code-block-content">
        <pre>
          <code>{codeString}</code>
        </pre>
      </div>
    </div>
  );
}
