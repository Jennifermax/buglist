export default function BuglistLogo({ size = 32, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Hexagon background with gradient */}
      <defs>
        <linearGradient id="hexGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#8B5CF6" />
          <stop offset="50%" stopColor="#6366F1" />
          <stop offset="100%" stopColor="#3B82F6" />
        </linearGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
          <feMerge>
            <feMergeNode in="coloredBlur"/>
            <feMergeNode in="SourceGraphic"/>
          </feMerge>
        </filter>
      </defs>

      {/* Hexagon */}
      <path
        d="M50 5 L85 27.5 L85 72.5 L50 95 L15 72.5 L15 27.5 Z"
        fill="url(#hexGradient)"
        stroke="rgba(255,255,255,0.3)"
        strokeWidth="2"
        filter="url(#glow)"
      />

      {/* Bug body */}
      <ellipse cx="50" cy="50" rx="12" ry="18" fill="white" opacity="0.95"/>

      {/* Bug head */}
      <circle cx="50" cy="38" r="8" fill="white" opacity="0.95"/>

      {/* Bug eyes */}
      <circle cx="47" cy="36" r="2" fill="#1e293b"/>
      <circle cx="53" cy="36" r="2" fill="#1e293b"/>

      {/* Bug antennae */}
      <path
        d="M 47 32 Q 43 28 40 25"
        stroke="white"
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
        opacity="0.9"
      />
      <path
        d="M 53 32 Q 57 28 60 25"
        stroke="white"
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
        opacity="0.9"
      />

      {/* Bug legs - left side */}
      <path d="M 42 45 L 30 42" stroke="white" strokeWidth="2" strokeLinecap="round" opacity="0.9"/>
      <path d="M 42 50 L 28 52" stroke="white" strokeWidth="2" strokeLinecap="round" opacity="0.9"/>
      <path d="M 42 55 L 30 58" stroke="white" strokeWidth="2" strokeLinecap="round" opacity="0.9"/>

      {/* Bug legs - right side */}
      <path d="M 58 45 L 70 42" stroke="white" strokeWidth="2" strokeLinecap="round" opacity="0.9"/>
      <path d="M 58 50 L 72 52" stroke="white" strokeWidth="2" strokeLinecap="round" opacity="0.9"/>
      <path d="M 58 55 L 70 58" stroke="white" strokeWidth="2" strokeLinecap="round" opacity="0.9"/>

      {/* Bug stripes */}
      <line x1="42" y1="48" x2="58" y2="48" stroke="#8B5CF6" strokeWidth="1.5" opacity="0.4"/>
      <line x1="42" y1="54" x2="58" y2="54" stroke="#8B5CF6" strokeWidth="1.5" opacity="0.4"/>
    </svg>
  );
}
