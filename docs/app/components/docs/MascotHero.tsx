import React from 'react';

interface MascotHeroProps {
  title: string;
  subtitle?: string;
}

/**
 * Docs front-page hero — the orb, Yumii's post-pivot form.
 * (Kept the MascotHero name so existing MDX keeps working.)
 */
export default function MascotHero({ title, subtitle }: MascotHeroProps) {
  return (
    <div className="orb-hero-docs">
      <div className="orb-hero-glow" aria-hidden="true"></div>
      <div className="orb-hero-ball" aria-hidden="true"></div>
      <h1 className="orb-hero-title">{title}</h1>
      {subtitle && <p className="orb-hero-subtitle">{subtitle}</p>}
    </div>
  );
}
