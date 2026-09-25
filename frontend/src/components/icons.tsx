type IconProps = { size?: number; className?: string };

function base(size: number, className?: string) {
  return {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    className,
  };
}

export const IconDashboard = ({ size = 18, className }: IconProps) => (
  <svg {...base(size, className)}>
    <rect x="3" y="3" width="7.5" height="7.5" rx="1.8" />
    <rect x="13.5" y="3" width="7.5" height="7.5" rx="1.8" />
    <rect x="3" y="13.5" width="7.5" height="7.5" rx="1.8" />
    <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.8" />
  </svg>
);

export const IconFile = ({ size = 18, className }: IconProps) => (
  <svg {...base(size, className)}>
    <path d="M6 2.5h8l4 4v15H6z" />
    <path d="M14 2.5v4h4" />
    <path d="M9 12h6M9 16h6" />
  </svg>
);

export const IconPrompt = ({ size = 18, className }: IconProps) => (
  <svg {...base(size, className)}>
    <path d="M4 5.5h6M4 9.5h6" />
    <path d="M4 5.5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h11l4 3v-3a2 2 0 0 0 2-2v-2" />
    <path d="M13 8l2.2 2L17.5 6.5" />
  </svg>
);

export const IconChat = ({ size = 18, className }: IconProps) => (
  <svg {...base(size, className)}>
    <path d="M4 4.5h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9l-5 4v-4a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2z" transform="translate(1 0)" />
    <path d="M8 10h8M8 13h5" />
  </svg>
);

export const IconEval = ({ size = 18, className }: IconProps) => (
  <svg {...base(size, className)}>
    <circle cx="12" cy="12" r="9.2" />
    <path d="m8 12.4 2.6 2.6L16.5 9" />
  </svg>
);

export const IconCost = ({ size = 18, className }: IconProps) => (
  <svg {...base(size, className)}>
    <circle cx="12" cy="12" r="9.2" />
    <path d="M12 6.8v10.4M15 8.6c-.7-.9-1.8-1.3-3-1.3-2 0-3.4 1-3.4 2.5 0 3.4 6.8 1.5 6.8 4.9 0 1.5-1.4 2.5-3.4 2.5-1.2 0-2.3-.4-3-1.3" />
  </svg>
);

export const IconSettings = ({ size = 18, className }: IconProps) => (
  <svg {...base(size, className)}>
    <circle cx="12" cy="12" r="2.8" />
    <path d="M19.4 13.6a7.8 7.8 0 0 0 0-3.2l2-1.5-2-3.4-2.4 1a8 8 0 0 0-2.8-1.6L13.8 2h-3.6l-.4 2.9a8 8 0 0 0-2.8 1.6l-2.4-1-2 3.4 2 1.5a7.8 7.8 0 0 0 0 3.2l-2 1.5 2 3.4 2.4-1a8 8 0 0 0 2.8 1.6l.4 2.9h3.6l.4-2.9a8 8 0 0 0 2.8-1.6l2.4 1 2-3.4z" />
  </svg>
);

export const IconLogout = ({ size = 18, className }: IconProps) => (
  <svg {...base(size, className)}>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <path d="m16 17 5-5-5-5M21 12H9" />
  </svg>
);

export const IconLock = ({ size = 22, className }: IconProps) => (
  <svg {...base(size, className)}>
    <rect x="4.5" y="10.5" width="15" height="10" rx="2.5" />
    <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
    <circle cx="12" cy="15.5" r="1.4" />
  </svg>
);

export const IconSpark = ({ size = 18, className }: IconProps) => (
  <svg {...base(size, className)}>
    <path d="M12 3l1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9z" />
    <path d="M19 15l.8 1.9 1.9.8-1.9.8L19 20.5l-.8-2-1.9-.8 1.9-.8z" />
  </svg>
);

export const IconUsers = ({ size = 18, className }: IconProps) => (
  <svg {...base(size, className)}>
    <circle cx="9" cy="8.5" r="3.5" />
    <path d="M3.5 19.5c.6-3 2.8-4.6 5.5-4.6s4.9 1.6 5.5 4.6" />
    <path d="M16 5.6a3.2 3.2 0 0 1 0 5.8M17.5 15.4c1.7.7 2.8 2 3.2 3.9" />
  </svg>
);