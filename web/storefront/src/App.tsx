import { useState } from "react";
import { Link, Route, Routes, useLocation } from "react-router-dom";
import { BagDrawer } from "./components/BagDrawer";
import { Header, SECTIONS } from "./components/Header";
import { Catalog } from "./pages/Catalog";
import { Home } from "./pages/Home";
import { Product } from "./pages/Product";

export function App() {
  const [refreshKey, setRefreshKey] = useState(0);
  const location = useLocation();

  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <Header />
      <main id="main" key={location.pathname} className="route">
        <Routes>
          <Route path="/" element={<Home refreshKey={refreshKey} />} />
          <Route path="/shop" element={<Catalog />} />
          <Route path="/p/:id" element={<Product />} />
        </Routes>
      </main>
      <footer className="foot">
        <div className="foot-grid">
          <div>
            <p className="foot-mark">Threadline</p>
            <p className="muted">
              A portfolio demo. Recommendations come from a two-stage model (retrieval and ranking) served by FastAPI.
              Nothing is sold or shipped.
            </p>
          </div>
          <nav aria-label="Sections" className="foot-nav">
            <p className="foot-head">Shop</p>
            {SECTIONS.map((s) => (
              <Link key={s.group} to={`/shop?index_group=${encodeURIComponent(s.group)}`}>
                {s.label}
              </Link>
            ))}
          </nav>
          <div>
            <p className="foot-head">How it works</p>
            <p className="muted small">
              Every view, click and order is logged and used to retrain the model weekly. Product images are generated
              renders, because the dataset has no photos.
            </p>
          </div>
        </div>
      </footer>
      <BagDrawer onOrdered={() => setRefreshKey((k) => k + 1)} />
    </>
  );
}
