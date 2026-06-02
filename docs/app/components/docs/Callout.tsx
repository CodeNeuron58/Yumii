import React from 'react';
import { Info, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';

interface CalloutProps {
  type?: 'info' | 'warning' | 'success' | 'error';
  title?: string;
  children: React.ReactNode;
}

export default function Callout({ type = 'info', title, children }: CalloutProps) {
  const IconMap = {
    info: Info,
    warning: AlertTriangle,
    success: CheckCircle,
    error: XCircle
  };
  
  const Icon = IconMap[type];

  return (
    <div className={`docs-callout docs-callout-${type}`}>
      <div className="docs-callout-icon">
        <Icon size={18} strokeWidth={2} />
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
