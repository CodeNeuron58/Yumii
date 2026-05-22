'use client';

import { useEffect, useState } from 'react';

export default function TableOfContents() {
  const [headings, setHeadings] = useState<{ id: string; text: string; nodeName: string }[]>([]);

  useEffect(() => {
    const elements = Array.from(document.querySelectorAll('.text-content h1, .text-content h2, .text-content h3'));
    const newHeadings = elements.map((el, index) => {
      if (!el.id) {
        el.id = `heading-${index}`;
      }
      return {
        id: el.id,
        text: el.textContent || '',
        nodeName: el.nodeName
      };
    });
    setHeadings(newHeadings);
  }, []);

  if (headings.length === 0) {
    return null;
  }

  return (
    <div className="toc">
      <h4>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '6px'}}>
          <line x1="21" y1="10" x2="3" y2="10"></line>
          <line x1="21" y1="6" x2="3" y2="6"></line>
          <line x1="21" y1="14" x2="3" y2="14"></line>
          <line x1="21" y1="18" x2="3" y2="18"></line>
        </svg>
        On this page
      </h4>
      <ul>
        {headings.map((h, i) => (
          <li key={i} className={i === 0 ? 'active' : ''} style={{ paddingLeft: h.nodeName === 'H3' ? '1rem' : '0' }}>
            <a href={`#${h.id}`} style={{textDecoration: 'none', color: 'inherit'}}>{h.text}</a>
          </li>
        ))}
      </ul>
    </div>
  );
}
