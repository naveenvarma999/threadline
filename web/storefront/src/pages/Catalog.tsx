import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { SECTIONS } from "../components/Header";
import { ProductCard } from "../components/ProductCard";
import type { Article } from "../types";

const FILTERS: { key: string; label: string }[] = [
  { key: "index_group", label: "Section" },
  { key: "product_group", label: "Category" },
  { key: "colour", label: "Colour" },
];

const DENSITY = [2, 4, 6] as const;

export function Catalog() {
  const [params, setParams] = useSearchParams();
  const [facets, setFacets] = useState<Record<string, string[]>>({});
  const [items, setItems] = useState<Article[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cols, setCols] = useState<(typeof DENSITY)[number]>(4);

  useEffect(() => {
    api.facets().then(setFacets).catch(() => setFacets({}));
  }, []);

  useEffect(() => setPage(1), [params]);

  useEffect(() => {
    const q = new URLSearchParams(params);
    q.set("page", String(page));
    setLoading(true);
    setError(null);
    api
      .search(q)
      .then((r) => {
        setItems((prev) => (page === 1 ? r.results : [...prev, ...r.results]));
        setCount(r.count);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [params, page]);

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
  }

  const section = SECTIONS.find((s) => s.group === params.get("index_group"));
  const title = params.get("q") ? `“${params.get("q")}”` : section ? section.label : "All products";
  const active = FILTERS.filter((f) => params.get(f.key));

  return (
    <div className="page catalog">
      <header className="catalog-head">
        <div>
          <p className="eyebrow">{params.get("q") ? "Search" : "Shop"}</p>
          <h1 className="catalog-title">{title}</h1>
        </div>
        <p className="muted tabular">{count.toLocaleString()} pieces</p>
      </header>

      <div className="toolbar">
        <div className="filters" role="group" aria-label="Filters">
          {FILTERS.map((f) => (
            <label key={f.key} className={params.get(f.key) ? "filter set" : "filter"}>
              <span className="sr-only">{f.label}</span>
              <select id={`filter-${f.key}`} value={params.get(f.key) ?? ""} onChange={(e) => setFilter(f.key, e.target.value)}>
                <option value="">{f.label}</option>
                {(facets[f.key] ?? []).map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
          ))}
          {active.length > 0 && (
            <button className="text-btn small" onClick={() => setParams(params.get("q") ? { q: params.get("q")! } : {})}>
              Clear filters
            </button>
          )}
        </div>
        <div className="density" role="group" aria-label="Items per row">
          {DENSITY.map((d) => (
            <button key={d} className={cols === d ? "density-btn active" : "density-btn"} onClick={() => setCols(d)} aria-pressed={cols === d}>
              <span className="density-icon" style={{ gridTemplateColumns: `repeat(${d === 2 ? 2 : d === 4 ? 3 : 4}, 1fr)` }} aria-hidden="true">
                {Array.from({ length: d === 2 ? 2 : d === 4 ? 3 : 4 }).map((_, i) => (
                  <i key={i} />
                ))}
              </span>
              <span className="sr-only">{d} per row</span>
            </button>
          ))}
        </div>
      </div>

      {error && <p className="notice bad">Search failed ({error}).</p>}
      {!loading && !error && items.length === 0 && <p className="muted">Nothing matches these filters yet.</p>}
      <div className={`grid cols-${cols}`}>
        {items.map((a) => (
          <ProductCard key={a.article_id} article={a} placement="catalog" showWhy={false} />
        ))}
      </div>
      {items.length < count && (
        <div className="load-more">
          <p className="muted small tabular">
            Showing {items.length} of {count}
          </p>
          <button className="outline-btn" onClick={() => setPage((p) => p + 1)} disabled={loading}>
            {loading ? "Loading…" : "Show more"}
          </button>
        </div>
      )}
    </div>
  );
}
