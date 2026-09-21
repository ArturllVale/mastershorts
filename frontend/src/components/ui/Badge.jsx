import React from 'react';
import { cn } from '../../lib/utils';

const variants = {
  default: 'text-muted bg-paper3 border-rule',
  brass: 'text-brass bg-brass/10 border-brass/30',
  success: 'text-ok bg-ok/10 border-ok/30',
  warning: 'text-warn bg-warn/10 border-warn/30',
  danger: 'text-danger bg-danger/10 border-danger/30',
  neutral: 'text-ink2 bg-paper3 border-rule2',
};

const dotColors = {
  default: 'bg-muted',
  brass: 'bg-brass',
  success: 'bg-ok',
  warning: 'bg-warn',
  danger: 'bg-danger',
  neutral: 'bg-ink2',
};

export default function Badge({
  children,
  variant = 'default',
  size = 'sm',
  dot = false,
  className,
  icon: Icon,
  ...props
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 font-mono uppercase font-medium tracking-wider border rounded-full select-none',
        size === 'xs' ? 'text-[10px] px-2 py-0.5 leading-none' : 'text-[11px] px-2.5 py-0.5 leading-none',
        variants[variant] || variants.default,
        className
      )}
      {...props}
    >
      {dot && (
        <span
          className={cn('w-1.5 h-1.5 rounded-full shrink-0', dotColors[variant] || dotColors.default)}
        />
      )}
      {Icon && <Icon size={12} className="shrink-0" />}
      <span>{children}</span>
    </span>
  );
}
