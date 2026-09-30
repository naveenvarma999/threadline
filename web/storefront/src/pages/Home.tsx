import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { CoverFlow } from "../components/CoverFlow";
import { GarmentArt } from "../components/GarmentArt";
import { SECTIONS } from "../components/Header";
import { ProductCard } from "../components/ProductCard";
import { Rail, RailSkeleton } from "../components/Rail";
import { useImpressions } from "../lib/useImpressions";
import { useStore } from "../store";
import type { Article, CustomerDetail, Feed } from "../types";

function Editorial({ items }: { items: Article[] }) {
  const ref = useImpressions(items, "trending");
  if (items.length < 3) return null;
  const [lead, ...rest] = items;
  return (
    <section className="editorial reveal" ref={ref} aria-label="Trending this week">
      <header className="section-head">
        <div>
          <h2>Trending this week</h2>
          <p className="section-note">Best sellers among shoppers your age, ranked by units sold</p>
        </div>
        <Link to="/shop" className="text-link">
          View all
        </Link>
      </header>
      <div className="editorial-grid">
        <div className="editorial-lead">
          <ProductCard article={lead} placement="trending" rank={1} showWhy={false} />
        </div>
        <div className="editorial-rest">
          {rest.slice(0, 4).map((a, i) => (
            <ProductCard key={a.article_id} article={a} placement="trending" rank={i + 2} showWhy={false} />
          ))}
        </div>
      </div>
    </section>
  );
}

function PickedGrid({ items }: { items: Article[] }) {
  const ref = useImpressions(items, "for_you");
  if (!items.length) return null;
  return (
    <section className="picked reveal" ref={ref} id="picked" aria-label="More picked for you">
      <header className="section-head">
        <div>
          <h2>More for you</h2>
          <p className="section-note">Ranked by the model from your history, your style and what is selling now</p>
        </div>
      </header>
      <div className="grid four">
        {items.map((a) => (
          <ProductCard key={a.article_id} article={a} placement="for_you" />
        ))}
      </div>
    </section>
  );
}

function Categories({ sample }: { sample: Article[] }) {
  return (
    <section className="categories reveal" aria-label="Shop by section">
      {SECTIONS.map((s, i) => {
        const art = sample[i % Math.max(sample.length, 1)];
        return (
          <Link key={s.group} to={`/shop?index_group=${encodeURIComponent(s.group)}`} className="category">
            {art && <GarmentArt article={art} className="category-art" />}
            <span className="category-label">{s.label}</span>
          </Link>
        );
      })}
    </section>
  );
}

export function Home({ refreshKey }: { refreshKey: number }) {
  const { shopper, sessionItems, setModelVersion } = useStore();
  const [feed, setFeed] = useState<Feed | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [profile, setProfile] = useState<CustomerDetail | null>(null);

  useEffect(() => {
    let live = true;
    setError(null);
    api
      .feed({ customer_id: shopper.customerId, session_article_ids: sessionItems.slice(0, 10), age: shopper.age })
      .then((f) => {
        if (!live) return;
        setFeed(f);
        setModelVersion(f.model_version);
      })
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [shopper, sessionItems, refreshKey, setModelVersion]);

  useEffect(() => {
    if (!shopper.customerId) return setProfile(null);
    api.customer(shopper.customerId).then(setProfile).catch(() => setProfile(null));
  }, [shopper.customerId, refreshKey]);

  const rows = useMemo(() => Object.fromEntries((feed?.rows ?? []).map((r) => [r.key, r.items])), [feed]);
  const forYou: Article[] = rows.for_you ?? rows.trending ?? [];
  const hero = forYou.slice(0, 7);
  // Fill whole rows of four so the grid never ends on a lone card.
  const rest = forYou.slice(7);
  const more = rest.length >= 4 ? rest.slice(0, rest.length - (rest.length % 4)) : rest;
  const known = Boolean(shopper.customerId);

  return (
    <div className="page home">
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">{known ? "Your edit" : "Guest edit"}</p>
          <h1>
            {known ? (
              <>
                Picked from what <em>you actually wear</em>
              </>
            ) : (
              <>
                Browse a little. <em>The edit learns.</em>
              </>
            )}
          </h1>
          <p className="hero-sub">
            {known && profile
              ? `Built from ${profile.n_purchases} past orders, your style and what is selling this week.`
              : "Every piece you open reshapes this page for the rest of your visit."}
          </p>
          <dl className="hero-facts">
            {profile && (
              <div>
                <dt>Orders</dt>
                <dd>{profile.n_purchases}</dd>
              </div>
            )}
            <div>
              <dt>Viewed today</dt>
              <dd>{sessionItems.length}</dd>
            </div>
            <div>
              <dt>Picks</dt>
              <dd>{forYou.length || "–"}</dd>
            </div>
          </dl>
          <div className="hero-cta">
            <a href="#picked" className="block-btn inline">
              Shop your edit
            </a>
            <Link to="/shop" className="text-link">
              Browse everything
            </Link>
          </div>
        </div>
        <div className="hero-stage">
          {hero.length ? (
            <CoverFlow items={hero} placement="for_you" />
          ) : (
            <div className="cf-placeholder skeleton" aria-busy={!error} />
          )}
        </div>
      </section>

      {feed?.fallback && (
        <p className="notice" role="status">
          Personalisation is paused, so you are seeing best sellers.
        </p>
      )}
      {error && (
        <p className="notice bad" role="alert">
          We could not load your edit ({error}). Check that the API is running.
        </p>
      )}

      {!feed && !error && <RailSkeleton title="More for you" />}
      <PickedGrid items={more} />
      <Rail title="Buy again" items={rows.buy_again ?? []} placement="buy_again" note="Pieces you have bought before that people often repeat" />
      <Editorial items={rows.trending ?? []} />
      <Categories sample={(rows.trending ?? forYou).slice(4, 9)} />
      {profile && profile.recent_purchases.length > 0 && (
        <Rail title="Your recent orders" items={profile.recent_purchases} placement="history" />
      )}
    </div>
  );
}
