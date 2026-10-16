/* eslint-disable react-refresh/only-export-components -- `Icon` groups tiny stateless icons; fast refresh is irrelevant here */
// A small, consistent line-icon set (24px grid, 1.75 stroke). Decorative: hidden from
// screen readers; every use sits next to a text label.
import type { ReactNode } from "react";
import type { Specialty } from "../specialties";

function Svg({ children, size = 18 }: { children: ReactNode; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

export const Icon = {
  // Aegle, daughter of Asclepius: a shield (care, protection) carrying a cross and a pulse.
  Logo: () => (
    <svg width={30} height={30} viewBox="0 0 32 32" aria-hidden="true">
      <path d="M16 2.5 27 6.5v8.2c0 7-4.6 12.2-11 14.8C9.6 26.9 5 21.7 5 14.7V6.5z" fill="#14a3a3" />
      <path d="M16 2.5 27 6.5v8.2c0 7-4.6 12.2-11 14.8z" fill="#0e8a8c" />
      <path d="M8.5 16h4l1.6-3.4 2.8 6.8 1.6-3.4h5" stroke="#fff" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  Bell: () => (
    <Svg>
      <path d="M6 9a6 6 0 0 1 12 0c0 5 2 6.5 2 6.5H4S6 14 6 9z" />
      <path d="M10 19a2 2 0 0 0 4 0" />
    </Svg>
  ),
  Command: () => (
    <Svg size={16}>
      <path d="M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3z" />
    </Svg>
  ),
  Info: () => (
    <Svg size={14}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v6M12 7.5h.01" />
    </Svg>
  ),
  Search: () => (
    <Svg size={16}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </Svg>
  ),
  ZoomIn: () => (
    <Svg>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5M11 8v6M8 11h6" />
    </Svg>
  ),
  ZoomOut: () => (
    <Svg>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5M8 11h6" />
    </Svg>
  ),
  Contrast: () => (
    <Svg>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 3v18a9 9 0 0 0 0-18z" fill="currentColor" />
    </Svg>
  ),
  Invert: () => (
    <Svg>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 21 21 3V21z" fill="currentColor" />
    </Svg>
  ),
  Reset: () => (
    <Svg>
      <path d="M4 12a8 8 0 1 0 2.4-5.7L4 8.6" />
      <path d="M4 4v4.6h4.6" />
    </Svg>
  ),
  Layers: () => (
    <Svg>
      <path d="m12 3 9 5-9 5-9-5z" />
      <path d="m3 13 9 5 9-5" />
    </Svg>
  ),
  Expand: () => (
    <Svg>
      <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />
    </Svg>
  ),
  Keyboard: () => (
    <Svg>
      <rect x="2" y="6" width="20" height="12" rx="2" />
      <path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10" />
    </Svg>
  ),
  Sparkle: () => (
    <Svg size={14}>
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6.3 6.3l2.5 2.5M15.2 15.2l2.5 2.5M6.3 17.7l2.5-2.5M15.2 8.8l2.5-2.5" />
    </Svg>
  ),
  Chevron: () => (
    <Svg size={14}>
      <path d="m9 6 6 6-6 6" />
    </Svg>
  ),
  Overview: () => (
    <Svg>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </Svg>
  ),
  Worklist: () => (
    <Svg>
      <path d="M9 6h11M9 12h11M9 18h11" />
      <circle cx="4.5" cy="6" r="1" />
      <circle cx="4.5" cy="12" r="1" />
      <circle cx="4.5" cy="18" r="1" />
    </Svg>
  ),
  Upload: () => (
    <Svg>
      <path d="M12 16V4M7 9l5-5 5 5" />
      <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
    </Svg>
  ),
  Models: () => (
    <Svg>
      <rect x="6" y="6" width="12" height="12" rx="2" />
      <path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4" />
    </Svg>
  ),
  Audit: () => (
    <Svg>
      <path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z" />
      <path d="M9 12l2 2 4-4" />
    </Svg>
  ),
  Network: () => (
    <Svg>
      <rect x="9" y="3" width="6" height="5" rx="1" />
      <rect x="3" y="16" width="6" height="5" rx="1" />
      <rect x="15" y="16" width="6" height="5" rx="1" />
      <path d="M12 8v4M6 16v-4h12v4" />
    </Svg>
  ),
  SignOut: () => (
    <Svg size={16}>
      <path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l5-5-5-5M15 12H4" />
    </Svg>
  ),
  Clock: () => (
    <Svg size={14}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </Svg>
  ),
  Chat: () => (
    <Svg>
      <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-4.6A8 8 0 1 1 21 12z" />
      <path d="M8.5 10.5h7M8.5 13.5h4.5" />
    </Svg>
  ),
  Plus: () => (
    <Svg>
      <path d="M12 5v14M5 12h14" />
    </Svg>
  ),
  Minimise: () => (
    <Svg>
      <path d="M13 5l7 7-7 7M4 12h16" />
    </Svg>
  ),
  Restore: () => (
    <Svg>
      <path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" />
    </Svg>
  ),
  Check: () => (
    <Svg size={16}>
      <path d="m5 12.5 4.5 4.5L19 7.5" />
    </Svg>
  ),
  Send: () => (
    <Svg size={16}>
      <path d="M21 3 10 14M21 3l-7 18-4-7-7-4z" />
    </Svg>
  ),
  Moon: () => (
    <Svg>
      <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />
    </Svg>
  ),
  Sun: () => (
    <Svg>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </Svg>
  ),
  Alert: () => (
    <Svg size={16}>
      <path d="M12 3l10 18H2z" />
      <path d="M12 10v5M12 18h.01" />
    </Svg>
  ),
};

const specialtyIcons: Record<Specialty, () => ReactNode> = {
  RADIOLOGY: () => (
    <Svg>
      <path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3" />
      <path d="M12 7v10M9 9.5c1 .8 5 .8 6 0M8.5 13c1.2 1 5.8 1 7 0" />
    </Svg>
  ),
  CARDIOLOGY: () => (
    <Svg>
      <path d="M20.5 9.5c0 5-8.5 10.5-8.5 10.5S3.5 14.5 3.5 9.5A4.5 4.5 0 0 1 12 7a4.5 4.5 0 0 1 8.5 2.5z" />
      <path d="M3.5 12h4l1.5-2.5 2 5 1.5-2.5h8" />
    </Svg>
  ),
  DERMATOLOGY: () => (
    <Svg>
      <path d="M3 14c2.5-1.5 4.5-1.5 6 0s3.5 1.5 6 0 4.5-1.5 6 0" />
      <path d="M3 19c2.5-1.5 4.5-1.5 6 0s3.5 1.5 6 0 4.5-1.5 6 0" />
      <circle cx="12" cy="7" r="3" />
    </Svg>
  ),
  OPHTHALMOLOGY: () => (
    <Svg>
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
    </Svg>
  ),
  PATHOLOGY: () => (
    <Svg>
      <path d="M9 3h4M11 3v4M8 7h6l-1 6H9zM11 13v3" />
      <path d="M5 21h14M7 21a5 5 0 0 1 4-5M17 14a4 4 0 0 1-2 7" />
    </Svg>
  ),
  GASTROENTEROLOGY: () => (
    <Svg>
      <path d="M8 3v4a4 4 0 0 0 4 4h2a4 4 0 0 1 4 4v1a5 5 0 0 1-5 5H9a4 4 0 0 1-4-4v-1" />
      <circle cx="13" cy="16" r="1" />
    </Svg>
  ),
  NEUROLOGY: () => (
    <Svg>
      <path d="M12 5a3 3 0 0 0-5.8-1A3 3 0 0 0 4 9a3 3 0 0 0 0 5 3 3 0 0 0 3 5 3 3 0 0 0 5 1z" />
      <path d="M12 5a3 3 0 0 1 5.8-1A3 3 0 0 1 20 9a3 3 0 0 1 0 5 3 3 0 0 1-3 5 3 3 0 0 1-5 1z" />
      <path d="M12 5v15" />
    </Svg>
  ),
};

export function SpecialtyIcon({ specialty }: { specialty: Specialty }) {
  return <>{specialtyIcons[specialty]()}</>;
}
