import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useStore } from "../store";
import { ShopperPicker } from "./ShopperPicker";

// Store sections map to the catalogue's index groups.
export const SECTIONS: { label: string; group: string }[] = [
  { label: "Women", group: "Ladieswear" },
  { label: "Men", group: "Menswear" },
  { label: "Divided", group: "Divided" },
  { label: "Sport", group: "Sport" },
  { label: "Kids", group: "Baby/Children" },
];

export function Header() {
  const { bag, setBagOpen, modelVersion } = useStore();
  const [searchOpen, setSearchOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [q, setQ] = useState("");
  const [scrolled, setScrolled] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const currentGroup = location.pathname === "/shop" ? new URLSearchParams(location.search).get("index_group") : null;

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (searchOpen) inputRef.current?.focus();
  }, [searchOpen]);

  function submit(e: FormEvent) {
    e.preventDefault();
    setSearchOpen(false);
    navigate(q.trim() ? `/shop?q=${encodeURIComponent(q.trim())}` : "/shop");
  }

  return (
    <>
      <div className="announce">
        <span>Your edit updates as you browse</span>
        <span className="announce-sep" aria-hidden="true">/</span>
        <span>Demo store: no real orders or payments</span>
      </div>
      <header className={scrolled ? "masthead scrolled" : "masthead"}>
        <div className="masthead-row">
          <button className="icon-btn menu-btn" aria-label="Open menu" aria-expanded={menuOpen} onClick={() => setMenuOpen((v) => !v)}>
            <span className="burger" aria-hidden="true" />
          </button>
          <nav className={menuOpen ? "sections open" : "sections"} aria-label="Store sections">
            {SECTIONS.map((s) => (
              <Link
                key={s.group}
                to={`/shop?index_group=${encodeURIComponent(s.group)}`}
                className={currentGroup === s.group ? "active" : undefined}
                aria-current={currentGroup === s.group ? "page" : undefined}
                onClick={() => setMenuOpen(false)}
              >
                {s.label}
              </Link>
            ))}
          </nav>
          <Link to="/" className="wordmark" aria-label="Threadline home">
            Threadline
          </Link>
          <div className="actions">
            <button className="text-btn" onClick={() => setSearchOpen((v) => !v)} aria-expanded={searchOpen}>
              Search
            </button>
            <button className="text-btn bag-link" onClick={() => setBagOpen(true)} aria-label={`Open bag, ${bag.length} items`}>
              Bag <span className="bag-count">{bag.length}</span>
            </button>
          </div>
        </div>
        {searchOpen && (
          <form className="search-panel" role="search" onSubmit={submit}>
            <label htmlFor="q" className="sr-only">
              Search products
            </label>
            <input
              id="q"
              ref={inputRef}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search: satin dress, denim, black boots"
              autoComplete="off"
            />
            <button type="submit" className="text-btn">
              Search
            </button>
          </form>
        )}
        <div className="demo-bar">
          <ShopperPicker />
          {modelVersion && (
            <span className="model-tag" title="Recommender version serving this page">
              {/^\d+$/.test(modelVersion) ? `Model v${modelVersion}` : `Model: ${modelVersion}`}
            </span>
          )}
        </div>
      </header>
    </>
  );
}
