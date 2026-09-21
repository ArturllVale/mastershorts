import React from 'react';
import { cn } from '../../lib/utils';

/**
 * Segmented option-toggle group for position/size/style pickers and mode switches.
 */
export default function SegmentedControl({
  options,
  value,
  onChange,
  multi = false,
  columns,
  size = 'md',
  className,
}) {
  const cols = columns || Math.min(options.length, 4);
  const isActive = (v) => (multi ? Array.isArray(value) && value.includes(v) : value === v);

  const toggle = (v) => {
    if (!multi) return onChange(v);
    const arr = Array.isArray(value) ? value : [];
    onChange(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);
  };

  const pad = size === 'sm' ? 'px-2.5 py-1.5' : 'px-3 py-2';
  const minCol = size === 'sm' ? 48 : 84;
  const gridTemplateColumns = `repeat(auto-fill, minmax(max(${minCol}px, calc((100% - ${(cols - 1) * 6}px) / ${cols})), 1fr))`;

  return (
    <div
      className={cn('grid gap-1.5', className)}
      style={{ gridTemplateColumns }}
      role={multi ? 'group' : 'radiogroup'}
    >
      {options.map((opt) => {
        const active = isActive(opt.value);
        return (
          <button
            key={opt.value}
            type="button"
            role={multi ? 'checkbox' : 'radio'}
            aria-checked={active}
            disabled={opt.disabled}
            onClick={() => toggle(opt.value)}
            className={cn(
              pad,
              'rounded-input border text-xs flex flex-col items-center justify-center gap-1 transition-all duration-150 select-none cursor-pointer',
              active
                ? 'border-brass bg-paper3 text-ink shadow-sm'
                : 'border-rule bg-paper text-muted hover:text-ink hover:border-rule2 hover:bg-paper2',
              opt.disabled && 'opacity-40 cursor-not-allowed hover:bg-paper hover:text-muted hover:border-rule'
            )}
          >
            {opt.icon && (
              <span className={active ? 'text-brass' : 'text-muted'}>{opt.icon}</span>
            )}
            <span className="font-medium text-center">{opt.label}</span>
            {opt.hint && <span className="readout text-[10px] normal-case">{opt.hint}</span>}
          </button>
        );
      })}
    </div>
  );
}
