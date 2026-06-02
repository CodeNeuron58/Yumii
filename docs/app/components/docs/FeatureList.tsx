import React from 'react';

interface FeatureListProps {
  children: React.ReactNode;
  cols?: 1 | 2 | 3 | 4;
}

export default function FeatureList({ children, cols = 2 }: FeatureListProps) {
  return (
    <div className={`docs-feature-list cols-${cols}`}>
      {children}
    </div>
  );
}
