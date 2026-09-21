import React from 'react';
import { cn } from '../../lib/utils';
import Button from './Button';

export default function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
  className,
  children,
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center p-8 text-center rounded-card border border-dashed border-rule2 bg-paper2/50',
        className
      )}
    >
      {Icon && (
        <div className="w-12 h-12 rounded-input bg-paper3 border border-rule flex items-center justify-center text-muted mb-3.5">
          <Icon size={22} className="text-muted" />
        </div>
      )}
      {title && <h4 className="text-base font-medium text-ink mb-1">{title}</h4>}
      {description && (
        <p className="text-xs text-muted max-w-sm mx-auto mb-4 leading-relaxed">
          {description}
        </p>
      )}
      {actionLabel && onAction && (
        <Button variant="secondary" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
      {children}
    </div>
  );
}
