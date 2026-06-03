import React from 'react';

interface MascotHeroProps {
  title: string;
  subtitle?: string;
}

export default function MascotHero({ title, subtitle }: MascotHeroProps) {
  return (
    <div className="mascot-hero">
      <div className="mascot-hero-bg"></div>
      
      <div className="mascot-hero-content">
        <h1 className="mascot-hero-title">{title}</h1>
        {subtitle && <p className="mascot-hero-subtitle">{subtitle}</p>}
      </div>

      <div className="mascot-container">
        <div className="mascot-hero-floor"></div>
        <img
          src="/docs/mascot.png"
          className="mascot-hero-img"
          alt="Yumii"
        />
        <div className="mascot-hero-fade"></div>
      </div>
    </div>
  );
}
