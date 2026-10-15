import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { Icon } from "./Icons";

const MIN_ZOOM = 0.5;
const MAX_ZOOM = 8;

type Props = {
  imageUrl: string | null;
  heatmapUrl: string | null;
  /** ECG/EEG: the AI view is a separate drawing that replaces the tracing, not an overlay. */
  recording: boolean;
  aiViewLabel: string;
  corners: { topLeft: string[]; topRight: string[] };
};

/**
 * A small PACS-style viewer: wheel to zoom about the cursor, drag to pan, brightness and
 * contrast (a stand-in for window/level on an 8-bit rendering), invert, and the AI overlay.
 * Every tool has a key, because radiologists keep a hand on the keyboard while reading.
 */
export function ImageViewer({ imageUrl, heatmapUrl, recording, aiViewLabel, corners }: Props) {
  // Zoom and pan change together (zooming about the cursor moves the image), so one state.
  const [view, setView] = useState({ zoom: 1, x: 0, y: 0 });
  const { zoom } = view;
  const [brightness, setBrightness] = useState(100);
  const [contrast, setContrast] = useState(100);
  const [invert, setInvert] = useState(false);
  const [showAi, setShowAi] = useState(true);
  const [opacity, setOpacity] = useState(0.45);
  const [help, setHelp] = useState(false);
  const stage = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number; px: number; py: number } | null>(null);

  const reset = useCallback(() => {
    setView({ zoom: 1, x: 0, y: 0 });
    setBrightness(100);
    setContrast(100);
    setInvert(false);
  }, []);

  const zoomBy = useCallback((factor: number, cx = 0, cy = 0) => {
    setView((v) => {
      const next = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, v.zoom * factor));
      const k = next / v.zoom;
      // Keep the point under the cursor still while zooming.
      return { zoom: next, x: cx - (cx - v.x) * k, y: cy - (cy - v.y) * k };
    });
  }, []);

  // Non-passive wheel listener, so the page does not scroll while zooming the image.
  useEffect(() => {
    const el = stage.current;
    if (!el) return;
    function onWheel(e: WheelEvent) {
      e.preventDefault();
      const r = el!.getBoundingClientRect();
      zoomBy(e.deltaY < 0 ? 1.12 : 1 / 1.12, e.clientX - r.left - r.width / 2, e.clientY - r.top - r.height / 2);
    }
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [zoomBy]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName) || e.metaKey || e.ctrlKey) return;
      const k = e.key.toLowerCase();
      if (k === "+" || k === "=") zoomBy(1.25);
      else if (k === "-") zoomBy(1 / 1.25);
      else if (k === "0" || k === "r") reset();
      else if (k === "i") setInvert((v) => !v);
      else if (k === "h" && heatmapUrl) setShowAi((v) => !v);
      else if (k === "?") setHelp((v) => !v);
      else if (k === "escape") setHelp(false);
      else return;
      e.preventDefault();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [zoomBy, reset, heatmapUrl]);

  function onPointerDown(e: ReactPointerEvent) {
    (e.target as Element).setPointerCapture?.(e.pointerId);
    drag.current = { x: e.clientX, y: e.clientY, px: view.x, py: view.y };
  }
  function onPointerMove(e: ReactPointerEvent) {
    const d = drag.current;
    if (d) setView((v) => ({ ...v, x: d.px + e.clientX - d.x, y: d.py + e.clientY - d.y }));
  }
  function onPointerUp() {
    drag.current = null;
  }

  const filter = `brightness(${brightness}%) contrast(${contrast}%)${invert ? " invert(1)" : ""}`;
  const aiOn = !!heatmapUrl && showAi;
  const src = recording && aiOn ? heatmapUrl : imageUrl;

  return (
    <section className="viewer" aria-label="Image viewer">
      <div className="viewer-toolbar" role="toolbar" aria-label="Image tools">
        <button className="tool" onClick={() => zoomBy(1.25)} title="Zoom in (+)" aria-label="Zoom in">
          <Icon.ZoomIn />
        </button>
        <button className="tool" onClick={() => zoomBy(1 / 1.25)} title="Zoom out (−)" aria-label="Zoom out">
          <Icon.ZoomOut />
        </button>
        <button className={`tool${invert ? " on" : ""}`} onClick={() => setInvert((v) => !v)} title="Invert (I)" aria-pressed={invert} aria-label="Invert">
          <Icon.Invert />
        </button>
        <button className="tool" onClick={reset} title="Reset view (R)" aria-label="Reset view">
          <Icon.Reset />
        </button>
        <span className="tool-sep" />
        <label className="tool-slider" title="Brightness">
          <Icon.Sparkle />
          <input type="range" min={40} max={200} value={brightness} onChange={(e) => setBrightness(Number(e.target.value))} aria-label="Brightness" />
        </label>
        <label className="tool-slider" title="Contrast">
          <Icon.Contrast />
          <input type="range" min={40} max={250} value={contrast} onChange={(e) => setContrast(Number(e.target.value))} aria-label="Contrast" />
        </label>
        <span className="tool-sep" />
        {heatmapUrl ? (
          <>
            <button className={`tool tool-ai${aiOn ? " on" : ""}`} onClick={() => setShowAi((v) => !v)} aria-pressed={aiOn} title="AI overlay (H)">
              <Icon.Layers /> {aiViewLabel}
            </button>
            {!recording && (
              <label className="tool-slider" title="Overlay opacity">
                <input
                  type="range"
                  min={0.1}
                  max={1}
                  step={0.05}
                  value={opacity}
                  disabled={!aiOn}
                  onChange={(e) => setOpacity(Number(e.target.value))}
                  aria-label="AI overlay opacity"
                />
              </label>
            )}
            {!recording && (
              <span className="heat-legend" aria-label="Colour scale: blue is low, red is high model attention">
                low <span className="heat-legend-bar" /> high
              </span>
            )}
          </>
        ) : (
          <span className="viewer-note">No AI overlay for this study</span>
        )}
        <span className="appbar-spacer" />
        <button className={`tool${help ? " on" : ""}`} onClick={() => setHelp((v) => !v)} title="Keyboard shortcuts (?)" aria-label="Keyboard shortcuts">
          <Icon.Keyboard />
        </button>
      </div>

      <div
        ref={stage}
        className="viewer-stage"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onDoubleClick={reset}
      >
        {src ? (
          <div className="image-stack" style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${zoom})` }}>
            <img src={src} alt={recording && aiOn ? "Recording with AI annotations" : "Study image"} style={{ filter }} draggable={false} />
            {!recording && aiOn && (
              <img src={heatmapUrl!} alt="Grad-CAM heatmap overlay" className="heatmap-overlay" style={{ opacity }} draggable={false} />
            )}
          </div>
        ) : (
          <p className="viewer-note">Loading image…</p>
        )}

        {!recording && (
          <>
            <div className="corner corner-tl">
              {corners.topLeft.map((l) => (
                <div key={l}>{l}</div>
              ))}
            </div>
            <div className="corner corner-tr">
              {corners.topRight.map((l) => (
                <div key={l}>{l}</div>
              ))}
            </div>
          </>
        )}
        <div className="corner corner-bl">
          Zoom {Math.round(zoom * 100)}% · B {brightness} C {contrast}
          {invert ? " · INV" : ""}
        </div>
        {aiOn && !recording && <div className="corner corner-br">AI overlay: Grad-CAM {Math.round(opacity * 100)}%</div>}

        {help && (
          <div className="shortcut-card" role="dialog" aria-label="Keyboard shortcuts" onPointerDown={(e) => e.stopPropagation()}>
            <h3>Viewer shortcuts</h3>
            <dl>
              <dt>Scroll</dt>
              <dd>Zoom about the cursor</dd>
              <dt>Drag</dt>
              <dd>Pan</dd>
              <dt>
                <kbd>+</kbd> <kbd>−</kbd>
              </dt>
              <dd>Zoom in / out</dd>
              <dt>
                <kbd>I</kbd>
              </dt>
              <dd>Invert greyscale</dd>
              <dt>
                <kbd>H</kbd>
              </dt>
              <dd>Toggle AI overlay</dd>
              <dt>
                <kbd>R</kbd> / double-click
              </dt>
              <dd>Reset view</dd>
            </dl>
            <p>Reviews are never signed from the keyboard: a stray key must not record a clinical decision.</p>
          </div>
        )}
      </div>
    </section>
  );
}
