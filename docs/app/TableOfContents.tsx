'use client';

import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';

export default function TableOfContents() {
  const [headings, setHeadings] = useState<{ id: string; text: string; nodeName: string }[]>([]);
  const pathname = usePathname();

  useEffect(() => {
    // We need to wait for MDXRemote to finish rendering
    const timer = setTimeout(() => {
      const elements = Array.from(document.querySelectorAll('.text-content h2, .text-content h3'));
      const newHeadings = elements.map((el, index) => {
        if (!el.id) {
          // Generate a clean ID from the text content if possible
          el.id = el.textContent
            ?.toLowerCase()
            .replace(/[^\w\s-]/g, '')
            .replace(/\s+/g, '-') || `heading-${index}`;
        }
        return {
          id: el.id,
          text: el.textContent || '',
          nodeName: el.nodeName
        };
      });
      setHeadings(newHeadings);
    }, 100); // Small delay to ensure content is in DOM

    return () => clearTimeout(timer);
  }, [pathname]); // Re-run on page change

  if (headings.length === 0) {
    return null;
  }

  return (
    <div className="toc">
      <h4>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '6px', color: 'var(--text-tertiary)'}}>
          <line x1="3" y1="6" x2="21" y2="6"></line>
          <line x1="3" y1="12" x2="21" y2="12"></line>
          <line x1="3" y1="18" x2="15" y2="18"></line>
        </svg>
        On this page
      </h4>
      <ul>
        {headings.map((h, i) => (
          <li key={i} style={{ paddingLeft: h.nodeName === 'H3' ? '1.5rem' : '0' }}>
            <a href={`#${h.id}`} style={{textDecoration: 'none', color: 'inherit', display: 'block', width: '100%'}}>
              {h.text}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
