// Illustrations of what each specialty's AI reads: a chest radiograph, an ECG strip, a
// dermoscopy field, a retinal photograph, an H&E slide, a colonoscopy view and a brain MRI.
// Drawn procedurally (seeded, so every render is identical) rather than taken from patient
// data: the repository never holds imaging data, and the app never shows a patient's image
// that the clinician has not opened (every image view is audited).
//
// The same components render the login page artwork (scripts/render-art.tsx), so the
// Keycloak theme and the app share one visual language.
import { useId, useMemo, type ReactNode } from "react";
import { specialtyById, type Specialty } from "../specialties";
import "./MedicalArt.css";

const W = 320;
const H = 200;

/** Deterministic PRNG (mulberry32), so illustrations are stable across renders. */
function rng(seed: number) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const f1 = (n: number) => n.toFixed(1);

/** A closed blob: radius varies smoothly with angle (lesions, glands). */
function blob(cx: number, cy: number, r: number, wobble: number[], phase = 0, points = 72) {
  const pts: string[] = [];
  for (let i = 0; i < points; i++) {
    const t = (i / points) * Math.PI * 2;
    const rr = r * (1 + wobble.reduce((s, w, k) => s + w * Math.sin((k + 2) * t + phase * (k + 1)), 0));
    pts.push(`${f1(cx + rr * Math.cos(t))},${f1(cy + rr * Math.sin(t))}`);
  }
  return `M${pts.join("L")}Z`;
}


type ArtProps = { uid: string };

function ChestXray({ uid }: ArtProps) {
  const ribs: ReactNode[] = [];
  for (let i = 0; i < 9; i++) {
    const y = 44 + i * 15;
    const span = 70 + Math.min(i, 5) * 8;
    for (const s of [-1, 1]) {
      const x0 = 160 + s * 8;
      ribs.push(
        <path
          key={`${i}${s}`}
          d={`M${x0},${y} C${x0 + s * span * 0.5},${y - 12} ${x0 + s * span},${y + 2} ${x0 + s * span * 0.92},${y + 26}`}
          stroke="#e8edf2"
          strokeOpacity={0.32 - i * 0.012}
          strokeWidth={4.2}
          fill="none"
          strokeLinecap="round"
        />,
      );
    }
  }
  return (
    <>
      <defs>
        <radialGradient id={`${uid}t`} cx="50%" cy="48%" r="60%">
          <stop offset="0" stopColor="#7d838b" />
          <stop offset=".65" stopColor="#3a3e44" />
          <stop offset="1" stopColor="#0a0b0d" />
        </radialGradient>
        <linearGradient id={`${uid}l`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#111316" />
          <stop offset="1" stopColor="#24272c" />
        </linearGradient>
        <radialGradient id={`${uid}h`}>
          <stop offset="0" stopColor="#ffde59" stopOpacity=".95" />
          <stop offset=".45" stopColor="#ff7a1a" stopOpacity=".6" />
          <stop offset="1" stopColor="#d7263d" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={`${uid}s`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#5ee7ff" stopOpacity="0" />
          <stop offset=".85" stopColor="#5ee7ff" stopOpacity=".28" />
          <stop offset="1" stopColor="#bdf6ff" stopOpacity=".9" />
        </linearGradient>
        <filter id={`${uid}b`}>
          <feGaussianBlur stdDeviation="1.6" />
        </filter>
      </defs>
      <rect width={W} height={H} fill="#050607" />
      <g filter={`url(#${uid}b)`}>
        <path d="M40,200 C44,120 70,40 120,22 L200,22 C250,40 276,120 280,200Z" fill={`url(#${uid}t)`} />
        <path d="M150,40 C120,42 92,70 86,120 C82,150 92,172 120,170 C140,168 150,150 152,120Z" fill={`url(#${uid}l)`} />
        <path d="M170,40 C200,42 228,70 234,120 C238,150 228,172 200,170 C186,169 176,160 172,140Z" fill={`url(#${uid}l)`} />
        {ribs}
        {Array.from({ length: 11 }, (_, i) => (
          <rect key={i} x={153} y={30 + i * 15} width={14} height={11} rx={2} fill="#c9ced4" opacity={0.42} />
        ))}
        <path d="M84,46 C110,34 140,38 154,44 M236,46 C210,34 180,38 166,44" stroke="#e8edf2" strokeOpacity=".5" strokeWidth="5" fill="none" />
        <ellipse cx={178} cy={134} rx={38} ry={30} fill="#9aa0a7" opacity={0.55} />
        <path d="M86,168 C110,150 140,156 154,170 M234,168 C214,152 186,154 168,168" stroke="#d5dadf" strokeOpacity=".55" strokeWidth="6" fill="none" />
      </g>
      <circle className="ma-a" cx={112} cy={128} r={26} fill={`url(#${uid}h)`} style={{ animation: "ma-pulse 2.8s ease-in-out infinite" }} />
      <g className="ma-a" style={{ animation: "ma-scan 4.5s linear infinite" }}>
        <rect x={0} y={-30} width={W} height={30} fill={`url(#${uid}s)`} />
      </g>
      <text x={10} y={16} fill="#9fb1c3" fontSize="8" fontFamily="IBM Plex Mono, monospace">CR CHEST PA</text>
      <text x={310} y={16} fill="#9fb1c3" fontSize="8" fontFamily="IBM Plex Mono, monospace" textAnchor="end">L</text>
    </>
  );
}

function EcgStrip({ uid }: ArtProps) {
  const trace = useMemo(() => {
    const g = (t: number, c: number, w: number) => Math.exp(-(((t - c) / w) ** 2));
    const pts: string[] = [];
    for (let x = 30; x <= W; x += 0.75) {
      const t = ((x - 30) % 84) / 84;
      const v = 7 * g(t, 0.16, 0.035) - 6 * g(t, 0.33, 0.01) + 58 * g(t, 0.355, 0.011) - 15 * g(t, 0.38, 0.011) + 13 * g(t, 0.6, 0.055);
      pts.push(`${f1(x)},${f1(122 - v)}`);
    }
    return `M${pts.join("L")}`;
  }, []);
  return (
    <>
      <defs>
        <pattern id={`${uid}g`} width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M8 0V40M16 0V40M24 0V40M32 0V40M0 8H40M0 16H40M0 24H40M0 32H40" stroke="#f3c3ba" strokeWidth=".5" />
          <path d="M0 0H40V40" fill="none" stroke="#e8968a" strokeWidth=".9" />
        </pattern>
      </defs>
      <rect width={W} height={H} fill="#fff4f1" />
      <rect width={W} height={H} fill={`url(#${uid}g)`} />
      <path d="M6,122 h6 v-40 h8 v40 h6" fill="none" stroke="#22303c" strokeWidth="1.4" />
      <path d={trace} fill="none" stroke="#e8968a" strokeOpacity=".35" strokeWidth="1.5" />
      <path
        className="ma-a"
        d={trace}
        pathLength={1}
        fill="none"
        stroke="#16222d"
        strokeWidth={1.7}
        strokeLinejoin="round"
        strokeDasharray="1 1"
        style={{ animation: "ma-sweep 5s linear infinite" }}
      />
      <g fontFamily="IBM Plex Mono, monospace" fontSize="9" fill="#5b2a22">
        <text x={10} y={18}>II</text>
        <text x={10} y={190}>25 mm/s · 10 mm/mV</text>
        <text x={310} y={18} textAnchor="end">
          HR <tspan fontWeight="700">71</tspan>
        </text>
      </g>
      <path
        className="ma-a"
        d="M291,11.5c-1.6-2.6-5.6-1.6-5.6,1.3 0,2.4 5.6,6 5.6,6s5.6-3.6 5.6-6c0-2.9-4-3.9-5.6-1.3z"
        fill="#d7263d"
        style={{ animation: "ma-blink .85s ease-in-out infinite" }}
        transform="translate(-30 -1)"
      />
    </>
  );
}

function Dermoscopy({ uid }: ArtProps) {
  const r = rng(7);
  const lesion = blob(156, 102, 44, [0.07, 0.05, 0.04, 0.03], 0.6);
  const dots = Array.from({ length: 70 }, () => {
    const a = r() * Math.PI * 2;
    const d = Math.sqrt(r()) * 38;
    return [156 + Math.cos(a) * d, 102 + Math.sin(a) * d, 0.5 + r() * 1.1] as const;
  });
  const hairs = Array.from({ length: 3 }, (_, i) => {
    const y = 30 + r() * 140;
    return `M${60 + i * 8},${f1(y)} C${120 + r() * 40},${f1(y - 30 + r() * 60)} ${180 + r() * 40},${f1(y - 20 + r() * 40)} ${250 + r() * 20},${f1(y + r() * 30)}`;
  });
  return (
    <>
      <defs>
        <clipPath id={`${uid}c`}>
          <circle cx={160} cy={100} r={92} />
        </clipPath>
        <radialGradient id={`${uid}s`} cx="45%" cy="40%" r="70%">
          <stop offset="0" stopColor="#f2c7a5" />
          <stop offset="1" stopColor="#b97a57" />
        </radialGradient>
        <radialGradient id={`${uid}l`} cx="48%" cy="46%">
          <stop offset="0" stopColor="#3d2216" />
          <stop offset=".6" stopColor="#6e4129" />
          <stop offset="1" stopColor="#9a6544" />
        </radialGradient>
        <filter id={`${uid}b`}>
          <feGaussianBlur stdDeviation="1.2" />
        </filter>
      </defs>
      <rect width={W} height={H} fill="#07090b" />
      <g clipPath={`url(#${uid}c)`}>
        <rect width={W} height={H} fill={`url(#${uid}s)`} />
        <path d={lesion} fill={`url(#${uid}l)`} filter={`url(#${uid}b)`} />
        <ellipse cx={168} cy={92} rx={18} ry={13} fill="#7d93b5" opacity={0.32} filter={`url(#${uid}b)`} />
        {dots.map(([x, y, s], i) => (
          <circle key={i} cx={x} cy={y} r={s} fill="#24120b" opacity={0.55} />
        ))}
        {hairs.map((d, i) => (
          <path key={i} d={d} stroke="#3a2418" strokeWidth={0.7} fill="none" opacity={0.45} />
        ))}
      </g>
      <g className="ma-a" style={{ transformOrigin: "160px 100px", animation: "ma-spin 40s linear infinite" }}>
        {Array.from({ length: 48 }, (_, i) => {
          const a = (i / 48) * Math.PI * 2;
          const l = i % 4 === 0 ? 8 : 4;
          return (
            <line
              key={i}
              x1={160 + Math.cos(a) * 92}
              y1={100 + Math.sin(a) * 92}
              x2={160 + Math.cos(a) * (92 - l)}
              y2={100 + Math.sin(a) * (92 - l)}
              stroke="#fff"
              strokeOpacity={0.7}
              strokeWidth={0.8}
            />
          );
        })}
      </g>
      <circle cx={160} cy={100} r={92} fill="none" stroke="#1d2328" strokeWidth={3} />
    </>
  );
}

function Fundus({ uid }: ArtProps) {
  const vessels = useMemo(() => {
    const r = rng(11);
    const out: { d: string; w: number; vein: boolean }[] = [];
    function grow(x: number, y: number, a: number, len: number, w: number, depth: number, vein: boolean, turn = 0) {
      if (depth === 0 || len < 6) return;
      const bend = (r() - 0.5) * 0.5;
      const x2 = x + Math.cos(a) * len;
      const y2 = y + Math.sin(a) * len;
      const cx = x + Math.cos(a + bend) * len * 0.55;
      const cy = y + Math.sin(a + bend) * len * 0.55;
      out.push({ d: `M${f1(x)},${f1(y)} Q${f1(cx)},${f1(cy)} ${f1(x2)},${f1(y2)}`, w, vein });
      grow(x2, y2, a + turn + (r() - 0.5) * 0.25, len * 0.86, w * 0.86, depth - 1, vein, turn);
      if (r() < 0.55) grow(x2, y2, a + (r() < 0.5 ? -1 : 1) * (0.5 + r() * 0.4), len * 0.6, w * 0.6, depth - 2, vein);
    }
    // Arcades sweep from the optic disc around the macula, as in a real fundus.
    const arcades: [number, boolean, number][] = [
      [-2.0, true, -0.16], [-2.2, false, -0.14], [2.0, true, 0.16], [2.2, false, 0.14], // temporal, around the macula
      [-0.8, true, 0.04], [0.8, false, -0.04], [-0.15, false, 0], [0.2, true, 0], // nasal
    ];
    for (const [a, vein, turn] of arcades) grow(212, 96, a, 20, vein ? 3.4 : 2.6, 8, vein, turn);
    return out;
  }, []);
  return (
    <>
      <defs>
        <radialGradient id={`${uid}f`} cx="50%" cy="50%" r="50%">
          <stop offset="0" stopColor="#c8541f" />
          <stop offset=".7" stopColor="#d9692a" />
          <stop offset=".93" stopColor="#8a2c10" />
          <stop offset="1" stopColor="#1a0603" />
        </radialGradient>
        <radialGradient id={`${uid}d`}>
          <stop offset="0" stopColor="#fff8dc" />
          <stop offset=".55" stopColor="#ffd98a" />
          <stop offset="1" stopColor="#f0a24c" stopOpacity="0" />
        </radialGradient>
        <radialGradient id={`${uid}m`}>
          <stop offset="0" stopColor="#5b1906" stopOpacity=".85" />
          <stop offset="1" stopColor="#8a2c10" stopOpacity="0" />
        </radialGradient>
        <clipPath id={`${uid}c`}>
          <circle cx={160} cy={100} r={94} />
        </clipPath>
      </defs>
      <rect width={W} height={H} fill="#030303" />
      <g clipPath={`url(#${uid}c)`}>
        <circle cx={160} cy={100} r={94} fill={`url(#${uid}f)`} />
        <circle cx={150} cy={102} r={26} fill={`url(#${uid}m)`} />
        <circle cx={150} cy={102} r={1.6} fill="#ffe7b8" opacity={0.8} />
        {vessels.map((v, i) => (
          <path
            key={i}
            className="ma-a"
            d={v.d}
            pathLength={1}
            strokeDasharray="1 1"
            stroke={v.vein ? "#6e1a0c" : "#b23a1c"}
            strokeWidth={v.w}
            strokeLinecap="round"
            fill="none"
            style={{ animation: `ma-draw 2.4s ease-out ${(i % 12) * 0.05}s both` }}
          />
        ))}
        <circle cx={212} cy={96} r={17} fill={`url(#${uid}d)`} />
        <circle cx={214} cy={95} r={5.5} fill="#fffaf0" opacity={0.9} />
      </g>
    </>
  );
}

function HistologyHE({ uid }: ArtProps) {
  const cells = useMemo(() => {
    const r = rng(23);
    const nuclei: { x: number; y: number; rx: number; ry: number; a: number; dark: boolean }[] = [];
    const glands: { d: string; x: number; y: number }[] = [];
    for (const [gx, gy, gr] of [[70, 60, 26], [200, 50, 22], [130, 140, 30], [262, 138, 24], [30, 160, 18]] as const) {
      glands.push({ d: blob(gx, gy, gr, [0.08, 0.06, 0.04], r() * 3), x: gx, y: gy });
      const n = Math.round(gr * 1.5);
      for (let i = 0; i < n; i++) {
        const t = (i / n) * Math.PI * 2;
        const rr = gr + 6 + r() * 3;
        nuclei.push({ x: gx + Math.cos(t) * rr, y: gy + Math.sin(t) * rr, rx: 4.2, ry: 2.4, a: (t * 180) / Math.PI + 90, dark: r() < 0.3 });
      }
    }
    for (let i = 0; i < 90; i++) {
      nuclei.push({ x: r() * (W + 40) - 20, y: r() * (H + 20) - 10, rx: 1.8 + r() * 2.6, ry: 1.2 + r() * 1.2, a: r() * 180, dark: r() < 0.5 });
    }
    const fibres = Array.from({ length: 16 }, () => {
      const y = r() * H;
      return `M-20,${f1(y)} C80,${f1(y + (r() - 0.5) * 40)} 200,${f1(y + (r() - 0.5) * 40)} 340,${f1(y + (r() - 0.5) * 30)}`;
    });
    return { nuclei, glands, fibres };
  }, []);
  return (
    <>
      <defs>
        <linearGradient id={`${uid}e`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#f6c4d7" />
          <stop offset="1" stopColor="#eaa3c0" />
        </linearGradient>
      </defs>
      <rect width={W} height={H} fill={`url(#${uid}e)`} />
      <g className="ma-a" style={{ animation: "ma-drift 14s ease-in-out infinite" }}>
        {cells.fibres.map((d, i) => (
          <path key={i} d={d} stroke="#df86aa" strokeWidth={1.2} fill="none" opacity={0.55} />
        ))}
        {cells.glands.map((g, i) => (
          <path key={i} d={g.d} fill="#fdf1f5" stroke="#d47aa0" strokeWidth={1} />
        ))}
        {cells.nuclei.map((n, i) => (
          <ellipse key={i} cx={n.x} cy={n.y} rx={n.rx} ry={n.ry} transform={`rotate(${f1(n.a)} ${f1(n.x)} ${f1(n.y)})`} fill={n.dark ? "#3f2470" : "#6b47a6"} opacity={0.88} />
        ))}
      </g>
      <g className="ma-a" style={{ animation: "ma-tile 9s ease-in-out infinite" }}>
        <rect x={40} y={30} width={64} height={64} fill="none" stroke="#0b5cad" strokeWidth={1.6} strokeDasharray="5 3" />
        <rect x={40} y={20} width={44} height={10} fill="#0b5cad" />
        <text x={43} y={28} fontSize="7" fill="#fff" fontFamily="IBM Plex Mono, monospace">224 px</text>
      </g>
    </>
  );
}

function Colonoscopy({ uid }: ArtProps) {
  return (
    <>
      <defs>
        <radialGradient id={`${uid}m`} cx="56%" cy="44%" r="62%">
          <stop offset="0" stopColor="#1c0505" />
          <stop offset=".18" stopColor="#5e1a14" />
          <stop offset=".5" stopColor="#c45a4a" />
          <stop offset=".85" stopColor="#e98d7c" />
          <stop offset="1" stopColor="#a8473b" />
        </radialGradient>
        <radialGradient id={`${uid}p`} cx="40%" cy="35%">
          <stop offset="0" stopColor="#ffd2c6" />
          <stop offset=".5" stopColor="#e2806d" />
          <stop offset="1" stopColor="#b5503f" />
        </radialGradient>
        <clipPath id={`${uid}c`}>
          <path d="M100,8 H220 L290,60 V140 L220,192 H100 L30,140 V60Z" />
        </clipPath>
        <filter id={`${uid}b`}>
          <feGaussianBlur stdDeviation="1" />
        </filter>
      </defs>
      <rect width={W} height={H} fill="#020202" />
      <g clipPath={`url(#${uid}c)`}>
        <g className="ma-a" style={{ transformOrigin: "178px 88px", animation: "ma-advance 7s ease-in-out infinite" }}>
          <rect width={W} height={H} fill={`url(#${uid}m)`} />
          {[30, 52, 76, 104, 136].map((r, i) => (
            <g key={r} filter={`url(#${uid}b)`}>
              <ellipse cx={178 - i * 2} cy={88 + i * 2} rx={r * 1.25} ry={r} fill="none" stroke="#7a2a20" strokeWidth={5 - i * 0.4} opacity={0.5} />
              <ellipse cx={178 - i * 2} cy={86 + i * 2} rx={r * 1.25} ry={r} fill="none" stroke="#ffc0b0" strokeWidth={1.6} opacity={0.45} />
            </g>
          ))}
          <ellipse cx={104} cy={142} rx={22} ry={17} fill={`url(#${uid}p)`} />
          <ellipse cx={98} cy={135} rx={5} ry={3} fill="#fff" opacity={0.75} />
          {[[230, 60], [250, 128], [140, 48], [70, 92]].map(([x, y], i) => (
            <ellipse key={i} cx={x} cy={y} rx={3.5} ry={1.8} fill="#fff" opacity={0.7} />
          ))}
        </g>
      </g>
      <text x={20} y={20} fill="#d7dde3" fontSize="8" fontFamily="IBM Plex Mono, monospace">WLI</text>
    </>
  );
}

function BrainMri({ uid }: ArtProps) {
  const cortex = blob(160, 100, 76, [0.012, 0.01], 0, 240).replace(/Z$/, "Z");
  const gyri = useMemo(() => {
    const pts: string[] = [];
    for (let i = 0; i <= 240; i++) {
      const t = (i / 240) * Math.PI * 2;
      const rr = 64 + 3.2 * Math.sin(17 * t + 0.4) + 2.4 * Math.sin(29 * t + 1.3) + 1.6 * Math.sin(11 * t + 2.1) + 1.2 * Math.sin(41 * t);
      pts.push(`${f1(160 + rr * Math.cos(t) * 0.86)},${f1(100 + rr * Math.sin(t) * 1.06)}`);
    }
    return `M${pts.join("L")}Z`;
  }, []);
  return (
    <>
      <defs>
        <radialGradient id={`${uid}w`} cx="50%" cy="50%" r="50%">
          <stop offset="0" stopColor="#b9b9b9" />
          <stop offset=".75" stopColor="#9c9c9c" />
          <stop offset="1" stopColor="#6f6f6f" />
        </radialGradient>
        <filter id={`${uid}b`}>
          <feGaussianBlur stdDeviation="1.3" />
        </filter>
      </defs>
      <rect width={W} height={H} fill="#000" />
      <g filter={`url(#${uid}b)`}>
        <ellipse cx={160} cy={100} rx={74} ry={92} fill="none" stroke="#e8e8e8" strokeWidth={5} />
        <ellipse cx={160} cy={100} rx={69} ry={87} fill="#161616" />
        <path d={cortex} transform="translate(160 100) scale(.86 1.07) translate(-160 -100)" fill="#6d6d6d" />
        <path d={gyri} fill={`url(#${uid}w)`} />
        <path d="M160,16 V184" stroke="#3a3a3a" strokeWidth={2} />
        <path d="M150,72 C132,80 130,108 146,124 C150,112 152,96 156,84Z M170,72 C188,80 190,108 174,124 C170,112 168,96 164,84Z" fill="#1b1b1b" />
        <circle cx={196} cy={70} r={20} fill="#555" opacity={0.7} />
        <circle cx={196} cy={70} r={12} fill="#f4f4f4" />
        <circle cx={196} cy={70} r={7.5} fill="#2b2b2b" />
      </g>
      <circle
        className="ma-a"
        cx={196}
        cy={70}
        r={23}
        fill="none"
        stroke="#5ee7ff"
        strokeWidth={1.4}
        strokeDasharray="6 6"
        style={{ animation: "ma-march 1.6s linear infinite" }}
      />
      <g fontFamily="IBM Plex Mono, monospace" fontSize="8" fill="#9fb1c3">
        <text x={10} y={16}>T1 +C  AX</text>
        <text x={10} y={190}>SL 14/24</text>
        <text x={310} y={16} textAnchor="end">R</text>
      </g>
    </>
  );
}

const ART: Record<Specialty, (p: ArtProps) => ReactNode> = {
  RADIOLOGY: ChestXray,
  CARDIOLOGY: EcgStrip,
  DERMATOLOGY: Dermoscopy,
  OPHTHALMOLOGY: Fundus,
  PATHOLOGY: HistologyHE,
  GASTROENTEROLOGY: Colonoscopy,
  NEUROLOGY: BrainMri,
};


/**
 * Illustration of a specialty's imaging. `motion`: "hover" moves only while pointed at
 * (dashboards: seven animations at once would distract), "live" always moves.
 */
export function MedicalArt({
  specialty,
  motion = "hover",
  className,
}: {
  specialty: Specialty;
  motion?: "hover" | "live";
  className?: string;
}) {
  const uid = `ma${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const Art = ART[specialty];
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className={`${motion === "live" ? "ma-live" : "ma-hover"}${className ? ` ${className}` : ""}`}
      role="img"
      aria-label={`Illustration: ${specialtyById(specialty)?.imaging}`}
      preserveAspectRatio="xMidYMid slice"
    >
      <Art uid={uid} />
    </svg>
  );
}
