import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useStore } from "../store";
import type { Article } from "../types";
import { GarmentArt } from "./GarmentArt";

/**
 * 3D coverflow: the active item faces the viewer, neighbours turn away in perspective.
 * Arrow keys, buttons, swipe/drag and clicking a side item all move it; autoplay pauses on
 * hover and is off when the user prefers reduced motion.
 */
export function CoverFlow({ items, placement }: { items: Article[]; placement: string }) {
  const { log, addToBag } = useStore();
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);
  const drag = useRef<{ x: number; moved: boolean } | null>(null);
  const logged = useRef("");
  const n = items.length;

  const go = useCallback((i: number) => setActive(((i % n) + n) % n), [n]);

  useEffect(() => setActive(0), [items]);

  useEffect(() => {
    const key = items.map((i) => i.article_id).join(",");
    if (!n || logged.current === key) return;
    logged.current = key;
    items.slice(0, 5).forEach((a) => log("impression", a.article_id, placement));
  }, [items, n, log, placement]);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (paused || reduce || n < 2) return;
    const t = window.setInterval(() => setActive((a) => (a + 1) % n), 4200);
    return () => window.clearInterval(t);
  }, [paused, n]);

  if (!n) return null;
  const current = items[active];

  return (
    <div
      className="coverflow"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onKeyDown={(e) => {
        if (e.key === "ArrowRight") go(active + 1);
        if (e.key === "ArrowLeft") go(active - 1);
      }}
    >
      <div
        className="cf-stage"
        tabIndex={0}
        role="group"
        aria-roledescription="carousel"
        aria-label="Picked for you"
        onPointerDown={(e) => {
          drag.current = { x: e.clientX, moved: false };
        }}
        onPointerMove={(e) => {
          const d = drag.current;
          if (!d) return;
          const dx = e.clientX - d.x;
          if (Math.abs(dx) > 50) {
            go(active + (dx < 0 ? 1 : -1));
            drag.current = { x: e.clientX, moved: true };
          }
        }}
        onPointerUp={() => {
          window.setTimeout(() => (drag.current = null), 0);
        }}
        onPointerLeave={() => (drag.current = null)}
      >
        {items.map((a, i) => {
          let off = i - active;
          if (off > n / 2) off -= n;
          if (off < -n / 2) off += n;
          const abs = Math.abs(off);
          const hidden = abs > 2;
          const style = {
            transform: `translateX(${off * 50}%) translateZ(${-abs * 150}px) rotateY(${off === 0 ? 0 : off < 0 ? 42 : -42}deg) scale(${off === 0 ? 1 : 0.9})`,
            zIndex: 10 - abs,
            opacity: hidden ? 0 : 1 - abs * 0.2,
            pointerEvents: hidden ? ("none" as const) : undefined,
          };
          const body = <GarmentArt article={a} className="cf-art" />;
          return off === 0 ? (
            <Link
              key={a.article_id}
              to={`/p/${a.article_id}`}
              className="cf-item active"
              style={style}
              onClick={(e) => {
                if (drag.current?.moved) e.preventDefault();
                else log("click", a.article_id, placement);
              }}
              aria-label={`${a.prod_name}, £${a.price}`}
            >
              {body}
              <span className="cf-glare" aria-hidden="true" />
            </Link>
          ) : (
            <button
              key={a.article_id}
              className="cf-item"
              style={style}
              onClick={() => go(i)}
              tabIndex={-1}
              aria-label={`Show ${a.prod_name}`}
            >
              {body}
            </button>
          );
        })}
      </div>

      <div className="cf-caption" aria-live="polite">
        <div>
          <p className="cf-reason">{current.reason}</p>
          <p className="cf-name">{current.prod_name}</p>
          <p className="price">£{current.price}</p>
        </div>
        <div className="cf-controls">
          <button className="round-btn" onClick={() => go(active - 1)} aria-label="Previous item">
            <span aria-hidden="true">←</span>
          </button>
          <span className="cf-count">
            {String(active + 1).padStart(2, "0")} / {String(n).padStart(2, "0")}
          </span>
          <button className="round-btn" onClick={() => go(active + 1)} aria-label="Next item">
            <span aria-hidden="true">→</span>
          </button>
          <button className="pill-btn" onClick={() => addToBag(current, placement)}>
            Add to bag
          </button>
        </div>
      </div>
    </div>
  );
}
