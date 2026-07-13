'use client';

import React, { useState } from 'react';
import { CheckIcon, CopySimpleIcon } from '@phosphor-icons/react';

export default function CopyButton({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy code: ', err);
    }
  };

  return (
    <button
      className={`command-copy-btn ${copied ? 'copied' : ''}`}
      onClick={handleCopy}
      aria-label="Copy code"
    >
      {copied ? <CheckIcon size={14} /> : <CopySimpleIcon size={14} />}
    </button>
  );
}
