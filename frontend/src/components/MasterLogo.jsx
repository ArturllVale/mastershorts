import React from 'react';

export default function MasterLogo({ size = 32, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <defs>
        <linearGradient id="mlMasterGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#8b5cf6" />
          <stop offset="50%" stopColor="#6366f1" />
          <stop offset="100%" stopColor="#06b6d4" />
        </linearGradient>
        <linearGradient id="mlInnerGlow" x1="0%" y1="100%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#a855f7" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.9" />
        </linearGradient>
      </defs>

      <rect x="6" y="6" width="88" height="88" rx="22" fill="#0d1117" stroke="url(#mlMasterGrad)" strokeWidth="3" />

      <path d="M26 70V30C26 27.79 27.79 26 30 26C32.21 26 34 27.79 34 30V70C34 72.21 32.21 74 30 74C27.79 74 26 72.21 26 70Z" fill="url(#mlMasterGrad)" />
      <path d="M34 33L48 50C49.1 51.4 51.2 51.4 52.3 50L66 33" stroke="url(#mlInnerGlow)" strokeWidth="8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M66 70V30C66 27.79 67.79 26 70 26C72.21 26 74 27.79 74 30V70C74 72.21 72.21 74 70 74C67.79 74 66 72.21 66 70Z" fill="url(#mlMasterGrad)" />
      <polygon points="50,47 57,59 51,59 53,69 43,57 49,57" fill="#22d3ee" />
    </svg>
  );
}
