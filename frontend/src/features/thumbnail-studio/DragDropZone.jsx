import React, { useState, useRef, useCallback } from 'react';
import { X } from 'lucide-react';

export default function DragDropZone({ label, accept, onFile, file, onClear, icon }) {
  const Icon = icon;
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef(null);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) onFile(f);
  }, [onFile]);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  if (file) {
    return (
      <div className="relative border border-border rounded-lg p-3 bg-surface-2/60">
        <div className="flex items-center gap-3">
          {file.type?.startsWith('image/') ? (
            <img src={URL.createObjectURL(file)} className="w-12 h-12 rounded-md object-cover border border-border" alt="" />
          ) : (
            <div className="w-12 h-12 rounded-md bg-surface-1 border border-border flex items-center justify-center">
              <Icon size={18} className="text-text-tertiary" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="text-sm text-text-primary font-medium truncate">{file.name}</p>
            <p className="font-mono text-xs text-text-tertiary mt-0.5">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
          </div>
          <button onClick={onClear} className="text-text-tertiary hover:text-text-primary transition-colors p-1">
            <X size={16} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={() => setIsDragging(false)}
      className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all duration-200 ${isDragging ? 'border-accent bg-accent/5' : 'border-border hover:border-accent/50 hover:bg-surface-2/30'
        }`}
    >
      <Icon size={20} className="mx-auto text-text-tertiary mb-2" />
      <p className="text-sm text-text-primary font-medium">{label}</p>
      <p className="text-xs text-text-tertiary mt-1">Drop file here or click to browse</p>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => e.target.files[0] && onFile(e.target.files[0])}
      />
    </div>
  );
}
