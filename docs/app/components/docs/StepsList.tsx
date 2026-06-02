import React from 'react';

interface StepsListProps {
  children: React.ReactNode;
}

export default function StepsList({ children }: StepsListProps) {
  return (
    <div className="docs-steps-list">
      {React.Children.map(children, (child, index) => {
        if (React.isValidElement(child)) {
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
