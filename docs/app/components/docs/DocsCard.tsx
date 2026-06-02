'use client';

import React, { useRef, useState, useEffect } from 'react';
import Link from 'next/link';

interface DocsCardProps {
  title: string;
  href?: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}

export default function DocsCard({ title, href, icon, children }: DocsCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (cardRef.current) {
        const rect = cardRef.current.getBoundingClientRect();
        setMousePosition({
          x: e.clientX - rect.left,
          y: e.clientY - rect.top,
        });
      }
    };

    if (isHovered) {
      window.addEventListener('mousemove', handleMouseMove);
    } else {
      window.removeEventListener('mousemove', handleMouseMove);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
    };
  }, [isHovered]);

  const CardContent = (
    <div
      ref={cardRef}
      className="docs-card"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        '--mouse-x': `${mousePosition.x}px`,
        '--mouse-y': `${mousePosition.y}px`,
      } as React.CSSProperties}
    >
      <div className="docs-card-border-glow"></div>
      <div className="docs-card-inner">
        {icon && <div className="docs-card-icon">{icon}</div>}
        <h4 className="docs-card-title">{title}</h4>
        <div className="docs-card-content">{children}</div>
      </div>
    </div>
  );

  if (href) {
    return (
      <Link href={href} className="docs-card-link">
        {CardContent}
      </Link>
    );
  }

  return CardContent;
}
