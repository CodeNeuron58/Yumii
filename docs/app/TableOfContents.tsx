'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';

type Heading = {
  id: string;
  text: string;
  nodeName: string;
};

const ORB_SIZE = 12;

/**
 * "Thread of light" TOC: a faint vertical track along the headings with a
 * small glowing orb (the brand mark) that glides to the section you are
 * reading. The thread above the orb is lit, showing progress through the
 * page.
 */
export default function TableOfContents() {
  const [headings, setHeadings] = useState<Heading[]>([]);
  const [activeId, setActiveId] = useState('');
  const [markerTop, setMarkerTop] = useState(4);
  const bodyRef = useRef<HTMLDivElement>(null);
  const linkRefs = useRef<Record<string, HTMLAnchorElement | null>>({});
  const pathname = usePathname();

  // Collect h2/h3 from the rendered MDX after navigation
  useEffect(() => {
    const timer = setTimeout(() => {
      const elements = Array.from(
        document.querySelectorAll('.text-content h2, .text-content h3')
      );
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
      setActiveId(newHeadings[0]?.id ?? '');
    }, 100);

    return () => clearTimeout(timer);
  }, [pathname]);

  // Track the section in view
  useEffect(() => {
    if (headings.length === 0) return;

    const observers: IntersectionObserver[] = [];

    headings.forEach((heading) => {
      const el = document.getElementById(heading.id);
      if (!el) return;
      const observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            setActiveId(heading.id);
          }
        },
        { rootMargin: '-80px 0px -60% 0px', threshold: 0.1 }
      );
      observer.observe(el);
      observers.push(observer);
    });

    return () => observers.forEach((o) => o.disconnect());
  }, [headings]);

  // Glide the orb to the active link
  const placeMarker = useCallback(() => {
    const link = activeId ? linkRefs.current[activeId] : null;
    if (!link || !bodyRef.current) return;
    setMarkerTop(link.offsetTop + link.offsetHeight / 2 - ORB_SIZE / 2);
  }, [activeId]);

  useEffect(() => {
    placeMarker();
    window.addEventListener('resize', placeMarker);
    return () => window.removeEventListener('resize', placeMarker);
  }, [placeMarker]);

  if (headings.length === 0) {
    return null;
  }

  return (
    <nav className="toc" aria-label="On this page">
      <p className="toc-heading">On this page</p>
      <div className="toc-body" ref={bodyRef}>
        <span className="toc-thread" aria-hidden="true" />
        <span
          className="toc-thread-fill"
          style={{ height: markerTop + ORB_SIZE / 2 }}
          aria-hidden="true"
        />
        <span className="toc-orb" style={{ top: markerTop }} aria-hidden="true" />
        <ul className="toc-list">
          {headings.map((heading, index) => (
            <li key={`${heading.id}-${index}`}>
              <a
                href={`#${heading.id}`}
                ref={(el) => {
                  linkRefs.current[heading.id] = el;
                }}
                className={`toc-link ${
                  heading.nodeName === 'H3' ? 'toc-link-depth' : ''
                } ${activeId === heading.id ? 'toc-link-active' : ''}`}
                aria-current={activeId === heading.id ? 'location' : undefined}
              >
                {heading.text}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}
