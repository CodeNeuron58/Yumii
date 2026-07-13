import React from 'react';
import Link from 'next/link';
import {
  CubeIcon,
  RocketLaunchIcon,
  SmileyIcon,
  SquaresFourIcon,
  WaveformIcon,
} from '@phosphor-icons/react/dist/ssr';
import type { Icon } from '@phosphor-icons/react';

const iconMap: Record<string, Icon> = {
  'rocket': RocketLaunchIcon,
  'waveform-lines': WaveformIcon,
  'face-smile': SmileyIcon,
  'cube': CubeIcon,
  'layout-dashboard': SquaresFourIcon,
};

interface DocsCardProps {
  title: string;
  href?: string;
  icon?: React.ReactNode | string;
  children: React.ReactNode;
}

export default function DocsCard({ title, href, icon, children }: DocsCardProps) {
  const IconComponent = typeof icon === 'string' ? iconMap[icon] : null;

  const CardContent = (
    <div className="docs-card">
      <div className="docs-card-inner">
        {icon && (
          <div className="docs-card-icon">
            {IconComponent ? <IconComponent size={24} /> : icon}
          </div>
        )}
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
