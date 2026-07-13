import React from 'react';
import {
  CodeIcon,
  CubeIcon,
  DownloadSimpleIcon,
  FolderIcon,
  PackageIcon,
  PlayIcon,
  RocketLaunchIcon,
  SmileyIcon,
  SquaresFourIcon,
  StarIcon,
  TerminalIcon,
  WaveformIcon,
  WindowsLogoIcon,
} from '@phosphor-icons/react/dist/ssr';
import type { Icon } from '@phosphor-icons/react';

const iconMap: Record<string, Icon> = {
  'rocket': RocketLaunchIcon,
  'waveform-lines': WaveformIcon,
  'face-smile': SmileyIcon,
  'cube': CubeIcon,
  'layout-dashboard': SquaresFourIcon,
  'terminal': TerminalIcon,
  'folder': FolderIcon,
  'star': StarIcon,
  'download': DownloadSimpleIcon,
  'code': CodeIcon,
  'play': PlayIcon,
  'package': PackageIcon,
  'windows': WindowsLogoIcon
};

export function Step({ icon, title, children }: { icon?: string; title?: React.ReactNode; children?: React.ReactNode }) {
  const IconComponent = icon ? iconMap[icon] : null;

  return (
    <div className="docs-step-item with-icon">
      <div className="docs-step-icon-wrapper">
        {IconComponent ? <IconComponent size={20} /> : <div className="docs-step-number"></div>}
      </div>
      <div className="docs-step-content">
        {title && <div className="docs-step-title">{title}</div>}
        {children}
      </div>
    </div>
  );
}

interface StepsListProps {
  children: React.ReactNode;
}

export default function StepsList({ children }: StepsListProps) {
  return (
    <div className="docs-steps-list">
      {React.Children.map(children, (child, index) => {
        if (React.isValidElement(child)) {
          // If it's our explicit Step component, just render it!
          if (child.type === Step) {
            return child;
          }

          // Otherwise fallback to old numbered style
          return (
            <div className="docs-step-item">
              <div className="docs-step-indicator">
                <div className="docs-step-number">{index + 1}</div>
                <div className="docs-step-connector"></div>
              </div>
              <div className="docs-step-content">
                {child}
              </div>
            </div>
          );
        }
        return child;
      })}
    </div>
  );
}
