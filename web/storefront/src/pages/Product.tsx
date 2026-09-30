import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { GarmentArt } from "../components/GarmentArt";
import { SECTIONS } from "../components/Header";
import { ProductCard } from "../components/ProductCard";
import { Rail, RailSkeleton } from "../components/Rail";
import { colourHex } from "../lib/colour";
import { useImpressions } from "../lib/useImpressions";
import { useStore } from "../store";
import type { Article } from "../types";

const SIZES = ["XS", "S", "M", "L", "XL"];

/** Drag to spin the garment in 3D; it settles on the nearest face when released. */
function Viewer({ article }: { article: Article }) {
  const [angle, setAngle] = useState(0);
  const [dragging, setDragging] = useState(false);
  const start = useRef<{ x: number; angle: number } | null>(null);
  const face = Math.round(angle / 180) % 2 === 0 ? "front" : "back";

  useEffect(() => setAngle(0), [article.article_id]);

  return (
    <div className="viewer">
      <div
        className={dragging ? "viewer-stage dragging" : "viewer-stage"}
        onPointerDown={(e) => {
          (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
          start.current = { x: e.clientX, angle };
          setDragging(true);
        }}
        onPointerMove={(e) => {
          if (!start.current) return;
          setAngle(start.current.angle + (e.clientX - start.current.x) * 0.6);
        }}
        onPointerUp={() => {
          start.current = null;
          setDragging(false);
          setAngle((a) => Math.round(a / 180) * 180);
        }}
        role="img"
        aria-label={`${article.prod_name}. Drag to turn it around.`}
      >
        <div className="viewer-spin" style={{ transform: `rotateY(${angle}deg)` }}>
          <GarmentArt article={article} className="viewer-face" />
          <GarmentArt article={article} view="back" className="viewer-face back" />
        </div>
        <span className="viewer-hint">Drag to turn</span>
      </div>
      <div className="viewer-thumbs" role="group" aria-label="Views">
        {(["front", "back"] as const).map((v) => (
          <button
            key={v}
            className={face === v ? "thumb active" : "thumb"}
            onClick={() => setAngle(v === "front" ? 0 : 180)}
            aria-pressed={face === v}
            aria-label={`Show ${v}`}
          >
            <GarmentArt article={article} view={v} className="thumb-art" />
          </button>
        ))}
      </div>
    </div>
  );
}

function SimilarGrid({ items }: { items: Article[] }) {
  const ref = useImpressions(items, "similar");
  if (!items.length) return null;
  return (
    <section className="picked reveal" ref={ref} aria-label="Similar items">
      <header className="section-head">
        <div>
          <h2>You may also like</h2>
          <p className="section-note">Closest in style, fabric and cut</p>
        </div>
      </header>
      <div className="grid four">
        {items.slice(0, 8).map((a) => (
          <ProductCard key={a.article_id} article={a} placement="similar" showWhy={false} />
        ))}
      </div>
    </section>
  );
}

export function Product() {
  const { id } = useParams();
  const articleId = Number(id);
  const { noteViewed, addToBag } = useStore();
  const [article, setArticle] = useState<Article | null>(null);
  const [similar, setSimilar] = useState<Article[] | null>(null);
  const [look, setLook] = useState<Article[] | null>(null);
  const [missing, setMissing] = useState(false);
  const [size, setSize] = useState("M");
  const [added, setAdded] = useState(false);

  useEffect(() => {
    setArticle(null);
    setSimilar(null);
    setLook(null);
    setMissing(false);
    setAdded(false);
    api
      .article(articleId)
      .then((a) => {
        setArticle(a);
        noteViewed(a.article_id);
      })
      .catch(() => setMissing(true));
    api.similar(articleId).then(setSimilar).catch(() => setSimilar([]));
    api.completeTheLook(articleId).then(setLook).catch(() => setLook([]));
    window.scrollTo({ top: 0 });
  }, [articleId, noteViewed]);

  if (missing) {
    return (
      <div className="page narrow">
        <p className="notice bad">We could not find item {id}.</p>
        <Link to="/" className="text-link">
          Back to your edit
        </Link>
      </div>
    );
  }

  const section = SECTIONS.find((s) => s.group === article?.index_group);

  return (
    <div className="page">
      {article ? (
        <section className="pdp">
          <Viewer article={article} />
          <div className="pdp-info">
            <nav className="crumbs" aria-label="Breadcrumb">
              <Link to="/">Home</Link>
              <span aria-hidden="true">/</span>
              {section ? <Link to={`/shop?index_group=${encodeURIComponent(section.group)}`}>{section.label}</Link> : <span>{article.index_group}</span>}
              <span aria-hidden="true">/</span>
              <Link to={`/shop?product_group=${encodeURIComponent(article.product_group)}`}>{article.product_type}</Link>
            </nav>
            <h1 className="pdp-title">{article.prod_name}</h1>
            <p className="price big">£{article.price}</p>

            <div className="pdp-colour">
              <span className="dot large" style={{ background: colourHex(article.colour) }} aria-hidden="true" />
              <span>{article.colour}</span>
            </div>

            <fieldset className="sizes">
              <legend>Size</legend>
              {SIZES.map((s) => (
                <label key={s} className={size === s ? "size active" : "size"}>
                  <input type="radio" name="size" value={s} checked={size === s} onChange={() => setSize(s)} />
                  {s}
                </label>
              ))}
            </fieldset>

            <button
              className="block-btn"
              onClick={() => {
                addToBag(article, "product_page");
                setAdded(true);
              }}
            >
              {added ? "Added to bag" : `Add to bag · ${size}`}
            </button>
            <p className="muted small">Opening this piece has already updated your home edit.</p>

            <div className="accordion">
              <details open>
                <summary>Description</summary>
                <p>{article.description}</p>
              </details>
              <details>
                <summary>Details</summary>
                <dl className="spec">
                  <div>
                    <dt>Department</dt>
                    <dd>{article.department}</dd>
                  </div>
                  <div>
                    <dt>Garment group</dt>
                    <dd>{article.garment_group}</dd>
                  </div>
                  <div>
                    <dt>Art. no.</dt>
                    <dd className="tabular">{String(article.article_id).padStart(10, "0")}</dd>
                  </div>
                </dl>
              </details>
              <details>
                <summary>Delivery and returns</summary>
                <p>This is a portfolio demo. Orders are recorded as events for the recommender; nothing is shipped or charged.</p>
              </details>
            </div>
          </div>
        </section>
      ) : (
        <section className="pdp" aria-busy="true">
          <div className="viewer">
            <div className="viewer-stage skeleton" />
          </div>
          <div className="pdp-info" />
        </section>
      )}

      {look === null ? (
        <RailSkeleton title="Complete the look" />
      ) : (
        <Rail title="Complete the look" items={look} placement="complete_the_look" note="Bought in the same basket by other customers" />
      )}
      {similar !== null && <SimilarGrid items={similar} />}
    </div>
  );
}
