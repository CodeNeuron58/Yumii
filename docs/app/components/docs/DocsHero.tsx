import React from 'react';

interface DocsHeroProps {
  title: string;
  subtitle?: string;
}

export default function DocsHero({ title, subtitle }: DocsHeroProps) {
  return (
    <div className="docs-hero">
      <div className="docs-hero-bg"></div>
      <div className="docs-hero-content">
        <h1 className="docs-hero-title">{title}</h1>
        {subtitle && <p className="docs-hero-subtitle">{subtitle}</p>}
      </div>
    </div>
  );
}
