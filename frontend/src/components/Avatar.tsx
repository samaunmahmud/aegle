import { useState } from "react";

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("");
}

/**
 * A clinician's picture (bundled illustrations, named by the user's profile), falling back
 * to initials. Decorative: the name always appears beside it.
 */
export function Avatar({ name, avatar, size = 32, ring }: { name: string; avatar?: string | null; size?: number; ring?: boolean }) {
  const [broken, setBroken] = useState(false);
  const style = { width: size, height: size, fontSize: Math.max(10, size * 0.38) };
  const cls = `avatar${ring ? " avatar-ring" : ""}`;
  if (avatar && !broken) {
    return (
      <img className={cls} style={style} src={`/avatars/${avatar}.webp`} alt="" aria-hidden="true" onError={() => setBroken(true)} />
    );
  }
  return (
    <span className={cls} style={style} aria-hidden="true">
      {initials(name)}
    </span>
  );
}
