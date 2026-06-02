import React from 'react';
import { Rocket, Activity, Smile, Box, LayoutDashboard, Terminal, Folder, Star, Download, Code2, Play, Package } from 'lucide-react';

const WindowsIcon = ({ size = 24 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
    <path d="M2.5 11.5V3.5L10 2.5V11.5H2.5ZM11.5 2.5L21.5 1V11.5H11.5V2.5ZM2.5 12.5H10V21.5L2.5 20.5V12.5ZM11.5 12.5H21.5V23L11.5 21.5V12.5Z" />
  </svg>
);

const iconMap: Record<string, any> = {
  'rocket': Rocket,
  'waveform-lines': Activity,
  'face-smile': Smile,
  'cube': Box,
  'layout-dashboard': LayoutDashboard,
  'terminal': Terminal,
  'folder': Folder,
  'star': Star,
  'download': Download,
  'code': Code2,
  'play': Play,
  'package': Package,
  'windows': WindowsIcon
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
