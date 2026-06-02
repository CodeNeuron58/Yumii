import React from 'react';

interface ContentCardProps {
  children: React.ReactNode;
}

export default function ContentCard({ children }: ContentCardProps) {
  return (
    <div className="content-card">
      {children}
    </div>
  );
}
