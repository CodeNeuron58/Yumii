'use client';

import { useEffect, useMemo, useState } from 'react';
import { usePathname } from 'next/navigation';
import { List } from 'lucide-react';

type Heading = {
  id: string;
  text: string;
  nodeName: string;
};

export default function TableOfContents() {
  const [headings, setHeadings] = useState<Heading[]>([]);
  const [activeId, setActiveId] = useState('');
  const [progress, setProgress] = useState(0);
  const pathname = usePathname();

  useEffect(() => {
    const timer = setTimeout(() => {
      const elements = Array.from(document.querySelectorAll('.text-content h2, .text-content h3'));
      const newHeadings = elements.map((el, index) => {
        if (!el.id) {
          el.id =
            el.textContent
              ?.toLowerCase()
              .replace(/[^\w\s-]/g, '')
              .replace(/\s+/g, '-') || `heading-${index}`;
        }

        return {
          id: el.id,
          text: el.textContent || '',
          nodeName: el.nodeName,
        };
      });

      setHeadings(newHeadings);
    }, 100);

    return () => clearTimeout(timer);
  }, [pathname]);

  useEffect(() => {
    if (headings.length === 0) {
      setActiveId('');
      setProgress(0);
      return;
    }

    const getHeadingElements = () =>
      headings
        .map((heading) => document.getElementById(heading.id))
        .filter(Boolean) as HTMLElement[];

    let frame = 0;

    const handleScroll = () => {
      if (frame) {
        window.cancelAnimationFrame(frame);
      }

      frame = window.requestAnimationFrame(() => {
        frame = 0;
        const headingElements = getHeadingElements();
        if (headingElements.length === 0) {
          return;
        }

        const topOffset =
          Number.parseInt(getComputedStyle(document.documentElement).getPropertyValue('--header-offset'), 10) || 160;
        let currentId = headingElements[0].id;

        for (const heading of headingElements) {
          if (heading.getBoundingClientRect().top <= topOffset) {
            currentId = heading.id;
          }
        }

        setActiveId((previous) => (previous === currentId ? previous : currentId));

        const currentIndex = headingElements.findIndex((heading) => heading.id === currentId);
        const nextProgress =
          headingElements.length <= 1 ? 1 : Math.max(0, Math.min(1, currentIndex / (headingElements.length - 1)));

        setProgress(nextProgress);
      });
    };

    handleScroll();
    window.addEventListener('scroll', handleScroll, { passive: true });
    document.addEventListener('scroll', handleScroll, { passive: true });
    window.addEventListener('resize', handleScroll);

    return () => {
      if (frame) {
        window.cancelAnimationFrame(frame);
      }
      window.removeEventListener('scroll', handleScroll);
      document.removeEventListener('scroll', handleScroll);
      window.removeEventListener('resize', handleScroll);
    };
  }, [headings]);

  const progressPercent = useMemo(() => `${Math.round(progress * 100)}%`, [progress]);

  if (headings.length === 0) {
    return null;
  }

  return (
    <div className="toc-card">
      <div className="toc-progress-track" aria-hidden="true">
        <span className="toc-progress-fill" style={{ height: progressPercent }} />
      </div>

      <div className="toc">
        <h4>
          <List size={12} aria-hidden="true" />
          On this page
        </h4>
        <ul>
          {headings.map((heading, index) => {
            const isActive = activeId === heading.id;
            const depthClass = heading.nodeName === 'H3' ? 'toc-item--depth-3' : 'toc-item--depth-2';

            return (
              <li key={`${heading.id}-${index}`} className={`toc-item ${depthClass} ${isActive ? 'active' : ''}`}>
                <a href={`#${heading.id}`} aria-current={isActive ? 'location' : undefined}>
                  {heading.text}
                </a>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
