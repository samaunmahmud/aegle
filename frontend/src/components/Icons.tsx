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
  Logo: () => (
    <svg width={28} height={28} viewBox="0 0 28 28" aria-hidden="true">
      <rect width="28" height="28" rx="7" fill="currentColor" opacity="0.16" />
      <path d="M14 6v16M6 14h16" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
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
