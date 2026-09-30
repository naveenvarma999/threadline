import type { Article } from "../types";

// Colour names used in the H&M catalogue -> display colours.
const COLOURS: Record<string, string> = {
  Black: "#1c1c1e", White: "#f4f4f1", "Off White": "#ece7dc", "Light Beige": "#d9c7a7", "Dark Blue": "#1f2f5a",
  Grey: "#8b8e93", Pink: "#e6a3b8", Red: "#b8322f", "Khaki green": "#6d7148", "Light Blue": "#9cc0e0",
  Yellow: "#e7c440", Brown: "#6b4a34", "Dark Grey": "#4a4c50", Beige: "#cdb893", Blue: "#3a5ea8",
  Green: "#3f7a4f", Orange: "#d9772e", Purple: "#6c4a8f", "Light Pink": "#f0c9d4", "Dark Red": "#7c1f25",
};

// Simple silhouettes on a 100x120 canvas, one per product group.
const SHAPES: Record<string, string> = {
  "Garment Upper body": "M30 18 L42 12 Q50 20 58 12 L70 18 L86 36 L76 46 L70 40 L70 104 L30 104 L30 40 L24 46 L14 36 Z",
  "Garment Lower body": "M30 14 L70 14 L74 106 L56 106 L50 44 L44 106 L26 106 Z",
  "Garment Full body": "M38 10 L46 10 Q50 18 54 10 L62 10 L64 34 L80 106 L20 106 L36 34 Z",
  Shoes: "M16 74 L40 70 Q52 62 58 50 L66 50 Q70 64 84 72 Q90 80 84 86 L16 86 Z",
  Accessories: "M34 44 Q34 20 50 20 Q66 20 66 44 L60 44 Q60 27 50 27 Q40 27 40 44 Z M22 44 L78 44 L84 100 L16 100 Z",
  Underwear: "M22 40 L78 40 L74 58 Q60 64 56 84 L44 84 Q40 64 26 58 Z",
  Swimwear: "M34 16 L40 16 L46 46 Q50 50 54 46 L60 16 L66 16 L68 60 Q70 74 62 90 L38 90 Q30 74 32 60 Z",
};

export function colourHex(name: string): string {
  return COLOURS[name] ?? "#9a9a96";
}

export function Swatch({ article, large = false }: { article: Article; large?: boolean }) {
  if (article.image_url) {
    return <img className="swatch-img" src={article.image_url} alt={article.prod_name} loading="lazy" />;
  }
  const fill = colourHex(article.colour);
  const path = SHAPES[article.product_group] ?? SHAPES["Garment Upper body"];
  return (
    <svg
      className={large ? "swatch swatch-large" : "swatch"}
      viewBox="0 0 100 120"
      role="img"
      aria-label={`${article.colour} ${article.product_type}`}
    >
      <rect width="100" height="120" fill="var(--tile)" />
      {/* A thin outline keeps white items visible in light mode and black items visible in dark mode. */}
      <path d={path} fill={fill} stroke="var(--line-strong)" strokeWidth="1" />
      <text x="6" y="115" className="swatch-code">
        {String(article.article_id).padStart(10, "0")}
      </text>
    </svg>
  );
}
