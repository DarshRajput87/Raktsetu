/**
 * One small icon set, drawn on a 20 px grid with a 1.75 stroke so every icon
 * has the same weight. Decorative by default (aria-hidden); give the parent
 * control its accessible name.
 */

type IconProps = { className?: string; size?: number };

function Svg({ className = "", size = 20, children }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`shrink-0 ${className}`}
    >
      {children}
    </svg>
  );
}

export const IconDrop = (p: IconProps) => (
  <Svg {...p}>
    <path d="M10 2.5c2.9 3.4 5 6.3 5 8.9a5 5 0 0 1-10 0c0-2.6 2.1-5.5 5-8.9Z" />
  </Svg>
);

export const IconPhone = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4.5 3h2.6l1.3 3.3-1.7 1.1a8.6 8.6 0 0 0 3.9 3.9l1.1-1.7 3.3 1.3v2.6A1.5 1.5 0 0 1 13.5 15 10.5 10.5 0 0 1 3 4.5 1.5 1.5 0 0 1 4.5 3Z" />
  </Svg>
);

export const IconRoute = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="5" cy="15" r="2" />
    <circle cx="15" cy="5" r="2" />
    <path d="M7 15h5.5a2.5 2.5 0 0 0 0-5h-5a2.5 2.5 0 0 1 0-5H13" />
  </Svg>
);

export const IconLocate = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="10" cy="10" r="3.2" />
    <path d="M10 2v2.5M10 15.5V18M2 10h2.5M15.5 10H18" />
  </Svg>
);

export const IconPin = (p: IconProps) => (
  <Svg {...p}>
    <path d="M10 17.5s5.5-5 5.5-9.2a5.5 5.5 0 0 0-11 0c0 4.2 5.5 9.2 5.5 9.2Z" />
    <circle cx="10" cy="8.3" r="2" />
  </Svg>
);

export const IconSearch = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="9" cy="9" r="5.5" />
    <path d="m13.2 13.2 3.8 3.8" />
  </Svg>
);

export const IconClock = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="10" cy="10" r="7" />
    <path d="M10 6v4.2l2.6 1.6" />
  </Svg>
);

export const IconCheck = (p: IconProps) => (
  <Svg {...p}>
    <path d="m4.5 10.5 3.5 3.5 7.5-8" />
  </Svg>
);

export const IconAlert = (p: IconProps) => (
  <Svg {...p}>
    <path d="M10 3 2.8 16h14.4L10 3Z" />
    <path d="M10 8.2v3.6M10 14.1v.1" />
  </Svg>
);

export const IconUndo = (p: IconProps) => (
  <Svg {...p}>
    <path d="M7.5 5 4 8.5 7.5 12" />
    <path d="M4 8.5h7.5a4.5 4.5 0 0 1 0 9H9" />
  </Svg>
);

export const IconPlus = (p: IconProps) => (
  <Svg {...p}>
    <path d="M10 4.5v11M4.5 10h11" />
  </Svg>
);

export const IconArrowOut = (p: IconProps) => (
  <Svg {...p}>
    <path d="M7 13 13 7M8 7h5v5" />
  </Svg>
);

export const IconUser = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="10" cy="7" r="3.2" />
    <path d="M3.8 17a6.2 6.2 0 0 1 12.4 0" />
  </Svg>
);

export const IconHospital = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3.5" y="4" width="13" height="13" rx="2" />
    <path d="M10 7.5v6M7 10.5h6" />
  </Svg>
);

export const IconPlay = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6.5 4.5v11l9-5.5-9-5.5Z" />
  </Svg>
);

export const IconChevron = (p: IconProps) => (
  <Svg {...p}>
    <path d="m7.5 5 5 5-5 5" />
  </Svg>
);

export const IconWhatsApp = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4.2 15.8 5 13a6.6 6.6 0 1 1 2.3 2.2l-3.1.6Z" />
    <path d="M8 8.3c.3 1.6 1.6 2.9 3.4 3.5l.9-.9 1.3.6-.3 1.1c-2.6.2-5.6-2.6-5.7-5.2l1-.4.6 1.3-.9.6" />
  </Svg>
);

export const IconBank = (p: IconProps) => (
  <Svg {...p}>
    <rect x="4" y="3" width="12" height="14" rx="2" />
    <path d="M4 8.5h12M8 6h4M10 11v3.5M8.25 12.75h3.5" />
  </Svg>
);

export const IconShield = (p: IconProps) => (
  <Svg {...p}>
    <path d="M10 2.8 4 5v4.6c0 3.7 2.6 6.4 6 7.6 3.4-1.2 6-3.9 6-7.6V5l-6-2.2Z" />
    <path d="m7.3 10 1.9 1.9 3.6-3.8" />
  </Svg>
);

export const IconLogout = (p: IconProps) => (
  <Svg {...p}>
    <path d="M8 3.5H5A1.5 1.5 0 0 0 3.5 5v10A1.5 1.5 0 0 0 5 16.5h3" />
    <path d="M12.5 6.5 16 10l-3.5 3.5M16 10H8" />
  </Svg>
);
