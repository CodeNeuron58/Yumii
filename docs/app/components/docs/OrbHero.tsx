import React from 'react';

interface OrbHeroProps {
  title: string;
  subtitle?: string;
}

/**
 * Docs front-page hero: the orb, rendered live in CSS with the same
 * recipe as the landing page. She is the brand mark.
 */
export default function OrbHero({ title, subtitle }: OrbHeroProps) {
  return (
    <div className="orb-hero-docs">
      <div className="orb-hero-glow" aria-hidden="true"></div>
      <div className="orb-hero-ball" aria-hidden="true"></div>
      <h1 className="orb-hero-title">{title}</h1>
      {subtitle && <p className="orb-hero-subtitle">{subtitle}</p>}
    </div>
  );
}
