import React from 'react';

interface SectionContainerProps {
  children: React.ReactNode;
  className?: string;
}

export default function SectionContainer({ children, className = '' }: SectionContainerProps) {
  return (
    <section className={`docs-section-container ${className}`.trim()}>
      {children}
    </section>
  );
}
