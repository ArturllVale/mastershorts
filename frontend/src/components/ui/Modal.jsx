import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import { cn } from '../../lib/utils';

const SIZES = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-2xl',
  xl: 'max-w-5xl',
};

export default function Modal({
  isOpen,
  onClose,
  title,
  eyebrow,
  size = 'md',
  children,
  footer,
  hideClose = false,
  className,
}) {
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && onClose) onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center bg-black/75 p-0 sm:p-4 animate-fade"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && onClose) onClose();
      }}
      role="dialog"
      aria-modal="true"
    >
      <div
        className={cn(
          'relative w-full bg-paper2 border border-rule2 shadow-modal flex flex-col',
          'max-h-[92vh] sm:max-h-[90vh] rounded-b-none sm:rounded-modal animate-sheet-up sm:animate-none',
          SIZES[size] || SIZES.md,
          className
        )}
      >
        {/* Mobile bottom sheet grab handle */}
        <div className="sm:hidden pt-3 pb-1 flex justify-center shrink-0" aria-hidden="true">
          <span className="w-10 h-1 rounded-full bg-rule2" />
        </div>

        {!hideClose && onClose && (
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="absolute top-3.5 right-3.5 sm:top-4 sm:right-4 z-10 p-1.5 rounded-input text-muted hover:text-ink hover:bg-paper3 transition-colors select-none"
          >
            <X size={18} />
          </button>
        )}

        {(title || eyebrow) && (
          <div className="px-5 sm:px-6 pt-4 sm:pt-6 pb-4 border-b border-rule shrink-0">
            {eyebrow && <p className="eyebrow mb-1 text-brass">{eyebrow}</p>}
            {title && (
              <h2 className="text-lg sm:text-xl font-semibold text-ink leading-snug pr-8 tracking-tight">
                {title}
              </h2>
            )}
          </div>
        )}

        <div className="px-5 sm:px-6 py-5 overflow-y-auto overscroll-contain custom-scrollbar grow">
          {children}
        </div>

        {footer && (
          <div className="px-5 sm:px-6 py-4 border-t border-rule bg-paper2/80 shrink-0 safe-bottom sm:rounded-b-modal">
            {footer}
          </div>
        )}
        {!footer && <div className="sm:hidden safe-bottom" />}
      </div>
    </div>
  );
}
