import { useEffect, useRef } from "react";
import { useStore } from "../store";
import type { Article } from "../types";

/** Log one impression per item the first time a section scrolls into view. */
export function useImpressions(items: Article[], placement: string) {
  const { log } = useStore();
  const ref = useRef<HTMLElement>(null);
  const logged = useRef("");

  useEffect(() => {
    const key = items.map((i) => i.article_id).join(",");
    const el = ref.current;
    if (!el || !items.length || logged.current === key) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting) && logged.current !== key) {
          logged.current = key;
          items.forEach((i) => log("impression", i.article_id, placement));
          obs.disconnect();
        }
      },
      { threshold: 0.25 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [items, log, placement]);

  return ref;
}
