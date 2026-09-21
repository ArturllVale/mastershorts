import React, { forwardRef } from 'react';
import { cn } from '../../lib/utils';

const Input = forwardRef(function Input(
  {
    label,
    error,
    hint,
    icon: Icon,
    rightElement,
    className,
    disabled = false,
    id,
    ...props
  },
  ref
) {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div className="w-full space-y-1.5 text-left">
      {label && (
        <label htmlFor={inputId} className="block text-xs font-medium text-ink2">
          {label}
        </label>
      )}
      <div className="relative flex items-center">
        {Icon && (
          <div className="absolute left-3 text-muted pointer-events-none flex items-center justify-center">
            <Icon size={16} />
          </div>
        )}
        <input
          ref={ref}
          id={inputId}
          disabled={disabled}
          className={cn(
            'w-full text-sm text-ink bg-paper border rounded-input px-3 py-2 outline-none transition-all duration-150',
            'placeholder:text-muted-dim placeholder:text-sm',
            'focus:border-brass focus:ring-1 focus:ring-brass',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            Icon ? 'pl-9' : 'pl-3',
            rightElement ? 'pr-10' : 'pr-3',
            error ? 'border-danger focus:border-danger focus:ring-danger' : 'border-rule2',
            className
          )}
          {...props}
        />
        {rightElement && (
          <div className="absolute right-3 flex items-center text-muted">
            {rightElement}
          </div>
        )}
      </div>
      {error && <p className="text-xs text-danger leading-tight">{error}</p>}
      {!error && hint && <p className="text-xs text-muted leading-tight">{hint}</p>}
    </div>
  );
});

export default Input;
