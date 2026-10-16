import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { SPECIALTIES } from "../specialties";
import { setTheme, useTheme } from "../theme";
import { Icon, SpecialtyIcon } from "./Icons";

type Command = { id: string; label: string; hint: string; icon: ReactNode; to?: string; run?: () => void; keywords?: string };

/** Ctrl/Cmd+K: jump anywhere, or to a patient by MRN, without leaving the keyboard. */
export function CommandPalette() {
  const { roles } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [cursor, setCursor] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const clinician = roles.includes("RADIOLOGIST") || roles.includes("PHYSICIAN");
  const dark = useTheme() === "dark";

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    }
    const openEvt = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("aegle:command-palette", openEvt);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("aegle:command-palette", openEvt);
    };
  }, []);

  // Clear on close (not on open), so keys typed straight after the shortcut are kept.
  useEffect(() => {
    if (!open) {
      setQ("");
      setCursor(0);
    }
  }, [open]);

  const commands = useMemo<Command[]>(() => {
    const list: Command[] = [];
    if (clinician) {
      list.push(
        { id: "overview", label: "Department overview", hint: "Page", icon: <Icon.Overview />, to: "/overview", keywords: "home dashboard" },
        { id: "worklist", label: "Reporting worklist", hint: "Page", icon: <Icon.Worklist />, to: "/worklist", keywords: "cases reading list" },
        { id: "upload", label: "New study", hint: "Page", icon: <Icon.Upload />, to: "/upload", keywords: "upload image scan" },
        ...SPECIALTIES.map((s) => ({
          id: s.slug,
          label: `${s.name} worklist`,
          hint: s.imaging,
          icon: <SpecialtyIcon specialty={s.id} />,
          to: `/worklist/${s.slug}`,
          keywords: s.summary,
        })),
      );
    }
    list.push({ id: "models", label: "AI model registry", hint: "Page", icon: <Icon.Models />, to: "/models", keywords: "performance validation" });
    if (roles.includes("ADMIN") || roles.includes("AUDITOR")) {
      list.push({ id: "audit", label: "Audit log", hint: "Page", icon: <Icon.Audit />, to: "/audit", keywords: "access integrity" });
    }
    if (roles.includes("ADMIN")) {
      list.push({ id: "dicom", label: "DICOM senders", hint: "Admin", icon: <Icon.Network />, to: "/admin/dicom", keywords: "modality pacs ae title" });
    }
    list.push(
      dark
        ? { id: "theme", label: "Lights on", hint: "Display", icon: <Icon.Sun />, run: () => setTheme("light"), keywords: "theme light mode" }
        : { id: "theme", label: "Lights off (reading room)", hint: "Display", icon: <Icon.Moon />, run: () => setTheme("dark"), keywords: "theme dark mode night" },
    );
    return list;
  }, [clinician, roles, dark]);

  const term = q.trim().toLowerCase();
  const matches = commands.filter((c) => !term || `${c.label} ${c.hint} ${c.keywords ?? ""}`.toLowerCase().includes(term));
  // Patient lookup leads when the text looks like an MRN (has a digit), otherwise trails.
  const mrnCommand: Command[] =
    clinician && term
      ? [{ id: "mrn", label: `Find patient “${q.trim()}”`, hint: "By MRN", icon: <Icon.Search />, to: `/worklist?mrn=${encodeURIComponent(q.trim())}` }]
      : [];
  const results: Command[] = /\d/.test(term) ? [...mrnCommand, ...matches] : [...matches, ...mrnCommand];

  function go(c: Command) {
    setOpen(false);
    if (c.run) c.run();
    else if (c.to) navigate(c.to);
  }

  if (!open) return null;
  return (
    <div className="palette-backdrop" onMouseDown={() => setOpen(false)}>
      <div className="palette" role="dialog" aria-label="Command palette" onMouseDown={(e) => e.stopPropagation()}>
        <div className="palette-input">
          <Icon.Search />
          <input
            ref={input}
            autoFocus
            value={q}
            placeholder="Go to a page or department, or type an MRN"
            aria-label="Command"
            onChange={(e) => {
              setQ(e.target.value);
              setCursor(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setCursor((c) => Math.min(results.length - 1, c + 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setCursor((c) => Math.max(0, c - 1));
              } else if (e.key === "Enter" && results[cursor]) {
                go(results[cursor]);
              } else if (e.key === "Escape") {
                setOpen(false);
              }
            }}
          />
          <kbd>esc</kbd>
        </div>
        <ul className="palette-list" role="listbox">
          {results.length === 0 && <li className="palette-empty">Nothing matches “{q}”.</li>}
          {results.map((c, i) => (
            <li
              key={c.id}
              role="option"
              aria-selected={i === cursor}
              className={i === cursor ? "on" : ""}
              onMouseEnter={() => setCursor(i)}
              onClick={() => go(c)}
            >
              <span className="palette-icon">{c.icon}</span>
              <span className="palette-label">{c.label}</span>
              <span className="palette-hint">{c.hint}</span>
            </li>
          ))}
        </ul>
        <div className="palette-foot">
          <span>
            <kbd>↑</kbd> <kbd>↓</kbd> choose
          </span>
          <span>
            <kbd>Enter</kbd> open
          </span>
          <span>
            <kbd>⌘</kbd>/<kbd>Ctrl</kbd> <kbd>K</kbd> toggle
          </span>
        </div>
      </div>
    </div>
  );
}
