import React from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';

const variants = {
  primary: 'bg-brass hover:bg-brass/90 text-brassink font-medium shadow-sm active:translate-y-px',
  secondary: 'bg-paper3 hover:bg-paper4 text-ink border border-rule2 hover:border-rule-strong active:translate-y-px',
  outline: 'bg-transparent hover:bg-paper3 text-ink2 hover:text-ink border border-rule2 hover:border-rule-strong active:translate-y-px',
  ghost: 'bg-transparent hover:bg-paper3 text-muted hover:text-ink active:translate-y-px',
  danger: 'bg-danger/10 hover:bg-danger/20 text-danger border border-danger/30 hover:border-danger active:translate-y-px',
  quiet: 'bg-paper3/80 hover:bg-paper3 text-ink2 hover:text-ink active:translate-y-px',
};

const sizes = {
  xs: 'text-xs px-2.5 py-1 rounded-sm gap-1.5 min-h-[28px]',
  sm: 'text-xs px-3.5 py-1.5 rounded-input gap-2 min-h-[32px]',
  md: 'text-sm px-4 py-2 rounded-input gap-2 min-h-[38px]',
  lg: 'text-base px-6 py-2.5 rounded-input gap-2.5 min-h-[44px]',
};

export default function Button({
  children,
  variant = 'secondary',
  size = 'md',
  className,
  disabled = false,
  loading = false,
  icon: Icon,
  iconRight: IconRight,
  type = 'button',
  onClick,
  ...props
}) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      className={cn(
        'inline-flex items-center justify-center select-none cursor-pointer transition-all duration-150',
        'disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none',
        variants[variant] || variants.secondary,
        sizes[size] || sizes.md,
        className
      )}
      {...props}
    >
      {loading ? (
        <Loader2 size={size === 'xs' ? 12 : size === 'sm' ? 14 : 16} className="animate-spin shrink-0" />
      ) : Icon ? (
        <Icon size={size === 'xs' ? 12 : size === 'sm' ? 14 : 16} className="shrink-0" />
      ) : null}
      
      {children && <span>{children}</span>}

      {!loading && IconRight && (
        <IconRight size={size === 'xs' ? 12 : size === 'sm' ? 14 : 16} className="shrink-0" />
      )}
    </button>
  );
}
