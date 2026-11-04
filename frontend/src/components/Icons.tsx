/** Small inline SVG icons, so the app needs no icon font or image requests. */
type P = { className?: string };
const base = { width: 24, height: 24, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
  strokeWidth: 1.6, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };

export const BookIcon = ({ className = "brand-icon" }: P) => (
  <svg {...base} className={className}>
    <path d="M3 5.5C6 4.5 9 4.8 12 7v12.5c-3-2.2-6-2.5-9-1.5z" />
    <path d="M21 5.5c-3-1-6-.7-9 1.5v12.5c3-2.2 6-2.5 9-1.5z" />
  </svg>
);
export const ShieldIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M12 3l7 3v5c0 4.5-3 8.2-7 10-4-1.8-7-5.5-7-10V6z" />
    <path d="M9 12l2 2 4-4" />
  </svg>
);
export const DragonIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M4 19c2-5 5-8 9-9l-2-4 5 3 4-2-2 5c0 5-4 8-9 8z" />
    <circle cx="15" cy="11" r=".8" fill="currentColor" />
  </svg>
);
export const SparkleIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />
    <path d="M19 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z" />
  </svg>
);
export const SwordIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M14.5 4H20v5.5L9 20.5 3.5 15z" />
    <path d="M6 12l6 6M3 21l3-3" />
  </svg>
);
export const MapIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2z" />
    <path d="M9 4v14M15 6v14" />
  </svg>
);
export const ScrollIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M7 4h11a2 2 0 012 2v1h-4" />
    <path d="M16 7v11a2 2 0 01-2 2H6a2 2 0 01-2-2v-1h10" />
    <path d="M7 4a2 2 0 00-2 2v11M9 9h4M9 13h4" />
  </svg>
);
export const UsersIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2.5 20c.8-3.5 3.3-5.5 6.5-5.5s5.7 2 6.5 5.5" />
    <circle cx="17" cy="9" r="2.5" />
    <path d="M17 14.5c2.3.2 4 1.8 4.5 4.5" />
  </svg>
);
