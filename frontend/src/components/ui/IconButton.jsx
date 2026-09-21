import React from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';

const variants = {
  primary: 'bg-brass hover:bg-brass/90 text-brassink shadow-sm active:translate-y-px',
  secondary: 'bg-paper3 hover:bg-paper4 text-ink border border-rule2 hover:border-rule-strong active:translate-y-px',
  outline: 'bg-transparent hover:bg-paper3 text-muted hover:text-ink border border-rule2 hover:border-rule-strong active:translate-y-px',
  ghost: 'bg-transparent hover:bg-paper3 text-muted hover:text-ink active:translate-y-px',
  danger: 'bg-danger/10 hover:bg-danger/20 text-danger border border-danger/30 hover:border-danger active:translate-y-px',
};

const sizes = {
  xs: 'w-7 h-7 rounded-sm',
  sm: 'w-8 h-8 rounded-input',
  md: 'w-9 h-9 rounded-input',
  lg: 'w-11 h-11 rounded-input',
};

const iconSizes = {
  xs: 12,
  sm: 14,
  md: 16,
  lg: 18,
};

export default function IconButton({
  icon: Icon,
  variant = 'ghost',
  size = 'md',
  className,
  disabled = false,
  loading = false,
  type = 'button',
  label,
  onClick,
  ...props
}) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      disabled={disabled || loading}
      onClick={onClick}
      className={cn(
        'inline-flex items-center justify-center select-none cursor-pointer transition-all duration-150 shrink-0',
        'disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none',
        variants[variant] || variants.ghost,
        sizes[size] || sizes.md,
        className
      )}
      {...props}
    >
      {loading ? (
        <Loader2 size={iconSizes[size] || 16} className="animate-spin" />
      ) : Icon ? (
        <Icon size={iconSizes[size] || 16} />
      ) : null}
    </button>
  );
}
