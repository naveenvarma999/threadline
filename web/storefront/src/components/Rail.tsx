import { useRef } from "react";
import { useImpressions } from "../lib/useImpressions";
import type { Article } from "../types";
import { ProductCard } from "./ProductCard";

/** Horizontal, snap-scrolling row of products with arrow buttons. */
export function Rail({ title, items, placement, note }: { title: string; items: Article[]; placement: string; note?: string }) {
  const ref = useImpressions(items, placement);
  const track = useRef<HTMLDivElement>(null);
  if (!items.length) return null;

  const scroll = (dir: number) => track.current?.scrollBy({ left: dir * track.current.clientWidth * 0.8, behavior: "smooth" });

  return (
    <section className="rail reveal" ref={ref} aria-label={title}>
      <header className="section-head">
        <div>
          <h2>{title}</h2>
          {note && <p className="section-note">{note}</p>}
        </div>
        <div className="rail-arrows">
          <button className="round-btn" onClick={() => scroll(-1)} aria-label={`Scroll ${title} left`}>
            <span aria-hidden="true">←</span>
          </button>
          <button className="round-btn" onClick={() => scroll(1)} aria-label={`Scroll ${title} right`}>
            <span aria-hidden="true">→</span>
          </button>
        </div>
      </header>
      <div className="rail-track" ref={track}>
        {items.map((a) => (
          <ProductCard key={a.article_id} article={a} placement={placement} />
        ))}
      </div>
    </section>
  );
}

export function RailSkeleton({ title }: { title: string }) {
  return (
    <section className="rail" aria-busy="true" aria-label={`${title} loading`}>
      <header className="section-head">
        <h2>{title}</h2>
      </header>
      <div className="rail-track">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="card">
            <div className="skeleton" />
          </div>
        ))}
      </div>
    </section>
  );
}
