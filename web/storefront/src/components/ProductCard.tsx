import { Link } from "react-router-dom";
import { useStore } from "../store";
import type { Article } from "../types";
import { colourHex } from "../lib/colour";
import { GarmentArt } from "./GarmentArt";

/** Product card: the image turns in 3D to the back view on hover, like a second product photo. */
export function ProductCard({
  article,
  placement,
  showWhy = true,
  rank,
}: {
  article: Article;
  placement: string;
  showWhy?: boolean;
  rank?: number;
}) {
  const { log, addToBag } = useStore();
  return (
    <article className="card">
      <Link
        to={`/p/${article.article_id}`}
        className="card-link"
        onClick={() => log("click", article.article_id, placement)}
        aria-label={`${article.prod_name}, £${article.price}`}
      >
        <div className="flip">
          <div className="flip-inner">
            <GarmentArt article={article} className="face front" />
            <GarmentArt article={article} view="back" className="face back" />
          </div>
          {rank !== undefined && <span className="rank">{String(rank).padStart(2, "0")}</span>}
        </div>
        <div className="card-body">
          <h3 className="card-title">{article.prod_name}</h3>
          <p className="price">£{article.price}</p>
        </div>
        <p className="card-meta">
          <span className="dot" style={{ background: colourHex(article.colour) }} aria-hidden="true" />
          {article.colour}
        </p>
      </Link>
      {showWhy && article.reason && <p className="why">{article.reason}</p>}
      <button className="quick-add" onClick={() => addToBag(article, placement)} aria-label={`Add ${article.prod_name} to bag`}>
        +
      </button>
    </article>
  );
}
