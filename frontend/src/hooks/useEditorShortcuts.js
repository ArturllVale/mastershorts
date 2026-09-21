import { useEffect } from 'react';

/**
 * Hook to manage keyboard shortcuts for the ClipEditor.
 */
export function useEditorShortcuts({
  onClose,
  rendering,
  dirty,
  setConfirmClose,
  dispatch,
  videoRef,
  deleteSegment,
  selected,
  splitSegment,
  sourceOpen,
  markHere,
  sendToClip
}) {
  useEffect(() => {
    const onKey = (e) => {
      const tag = (e.target?.tagName || '').toLowerCase();
      const typing = tag === 'input' || tag === 'textarea' || tag === 'select';

      if (e.key === 'Escape') {
        e.preventDefault();
        // Leaving mid-render abandons nothing: the request keeps
        // running and onRerendered updates the card when it lands.
        if (rendering) onClose();
        else if (dirty) setConfirmClose(true);
        else onClose();
        return;
      }

      if (typing) return;

      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z') {
        e.preventDefault();
        dispatch({ type: e.shiftKey ? 'redo' : 'undo' });
      } else if (e.key === ' ') {
        e.preventDefault();
        const v = videoRef.current;
        if (v) { if (v.paused) v.play().catch(() => {}); else v.pause(); }
      } else if (e.key === 'Backspace' || e.key === 'Delete') {
        e.preventDefault();
        deleteSegment(selected);
      } else if (e.key.toLowerCase() === 's') {
        e.preventDefault();
        splitSegment(selected);
      } else if (sourceOpen && e.key.toLowerCase() === 'i') {
        e.preventDefault();
        markHere('in');
      } else if (sourceOpen && e.key.toLowerCase() === 'o') {
        e.preventDefault();
        markHere('out');
      } else if (sourceOpen && e.key === ',') {
        e.preventDefault();
        sendToClip('insert');
      } else if (sourceOpen && e.key === '.') {
        e.preventDefault();
        sendToClip('replace');
      }
    };

    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }); // Omitted dependency array matches original behavior (runs every render)
}
