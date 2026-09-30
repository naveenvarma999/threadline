import { useEffect, useRef } from "react";
import { useStore } from "../store";
import type { Article } from "../types";
import { ProductCard } from "./ProductCard";

/** Horizontal shelf of products. Logs one impression per item when the shelf first scrolls into view. */
export function Shelf({ title, items, placement, note }: { title: string; items: Article[]; placement: string; note?: string }) {
  const { log } = useStore();
  const ref = useRef<HTMLElement>(null);
  const logged = useRef<string>("");

  useEffect(() => {
    const key = items.map((i) => i.article_id).join(",");
    const el = ref.current;
    if (!el || logged.current === key) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting) && logged.current !== key) {
          logged.current = key;
          items.forEach((i) => log("impression", i.article_id, placement));
          obs.disconnect();
        }
      },
      { threshold: 0.3 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [items, log, placement]);

  if (!items.length) return null;
  return (
    <section className="shelf" ref={ref} aria-label={title}>
      <header className="shelf-head">
        <h2>{title}</h2>
        {note && <p className="shelf-note">{note}</p>}
      </header>
      <div className="shelf-track">
        {items.map((a) => (
          <ProductCard key={a.article_id} article={a} placement={placement} />
        ))}
      </div>
    </section>
  );
}

export function ShelfSkeleton({ title }: { title: string }) {
  return (
    <section className="shelf" aria-busy="true" aria-label={`${title} loading`}>
      <header className="shelf-head">
        <h2>{title}</h2>
      </header>
      <div className="shelf-track">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="card skeleton" />
        ))}
      </div>
    </section>
  );
}
