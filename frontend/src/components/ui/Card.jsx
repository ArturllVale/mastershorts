import React from 'react';
import { cn } from '../../lib/utils';

export function Card({ children, className, hover = false, elevated = false, ...props }) {
  return (
    <div
      className={cn(
        'rounded-card border transition-all duration-200',
        elevated ? 'bg-paper3 border-rule2 shadow-elevated' : 'bg-paper2 border-rule shadow-card',
        hover && 'hover:-translate-y-0.5 hover:border-rule-strong hover:shadow-elevated',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className, ...props }) {
  return (
    <div className={cn('p-5 pb-3 flex flex-col space-y-1.5', className)} {...props}>
      {children}
    </div>
  );
}

export function CardTitle({ children, className, ...props }) {
  return (
    <h3 className={cn('font-semibold text-base text-ink tracking-tight', className)} {...props}>
      {children}
    </h3>
  );
}

export function CardDescription({ children, className, ...props }) {
  return (
    <p className={cn('text-xs text-muted leading-relaxed', className)} {...props}>
      {children}
    </p>
  );
}

export function CardContent({ children, className, ...props }) {
  return (
    <div className={cn('p-5 pt-0', className)} {...props}>
      {children}
    </div>
  );
}

export function CardFooter({ children, className, ...props }) {
  return (
    <div className={cn('p-5 pt-3 border-t border-rule flex items-center', className)} {...props}>
      {children}
    </div>
  );
}

export default Card;
