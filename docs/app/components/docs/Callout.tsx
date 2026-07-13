import React from 'react';
import {
  CheckCircleIcon,
  InfoIcon,
  WarningIcon,
  XCircleIcon,
} from '@phosphor-icons/react/dist/ssr';

interface CalloutProps {
  type?: 'info' | 'warning' | 'success' | 'error';
  title?: string;
  children: React.ReactNode;
}

export default function Callout({ type = 'info', title, children }: CalloutProps) {
  const IconMap = {
    info: InfoIcon,
    warning: WarningIcon,
    success: CheckCircleIcon,
    error: XCircleIcon
  };

  const Icon = IconMap[type];

  return (
    <div className={`docs-callout docs-callout-${type}`}>
      <div className="docs-callout-icon">
        <Icon size={18} />
      </div>
      <div className="docs-callout-content">
        {title && <h5 className="docs-callout-title">{title}</h5>}
        <div className="docs-callout-body">
          {children}
        </div>
      </div>
    </div>
  );
}
