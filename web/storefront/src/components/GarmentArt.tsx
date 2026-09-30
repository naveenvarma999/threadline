import { useId } from "react";
import { mix, shadesFor } from "../lib/colour";
import type { Article } from "../types";

/*
 * Studio-style garment renders drawn in SVG.
 *
 * The synthetic dataset has no product photos, so each article gets a shaded "product shot":
 * a silhouette chosen from its product type, a light-to-dark fabric gradient, fold lines,
 * construction details (collars, seams, stitching) and a material texture (denim twill, knit rib,
 * satin sheen). When real photos are configured (IMAGE_BASE_URL on the API) they are used instead.
 */

type ShapeKey =
  | "tee" | "longsleeve" | "hoodie" | "shirt" | "jacket" | "blouse"
  | "trousers" | "jeans" | "shorts" | "skirt"
  | "dress" | "jumpsuit"
  | "sneaker" | "boot" | "sandal"
  | "bag" | "hat" | "scarf" | "belt"
  | "bra" | "briefs" | "socks"
  | "swimsuit" | "bikini";

const BY_TYPE: Record<string, ShapeKey> = {
  "T-shirt": "tee", Sweater: "longsleeve", Hoodie: "hoodie", Shirt: "shirt", Jacket: "jacket", Blouse: "blouse",
  Trousers: "trousers", Jeans: "jeans", Shorts: "shorts", Skirt: "skirt", Dress: "dress", Jumpsuit: "jumpsuit",
  Sneakers: "sneaker", Boots: "boot", Sandals: "sandal", Bag: "bag", Hat: "hat", Scarf: "scarf", Belt: "belt",
  Bra: "bra", Briefs: "briefs", Socks: "socks", Swimsuit: "swimsuit", "Bikini top": "bikini",
};

const BY_GROUP: Record<string, ShapeKey> = {
  "Garment Upper body": "tee", "Garment Lower body": "trousers", "Garment Full body": "dress", Shoes: "sneaker",
  Accessories: "bag", Underwear: "briefs", Swimwear: "swimsuit",
};

interface Shape {
  body: string; // silhouette
  under?: string; // drawn behind the body (hood, inside of a bag)
  folds: string[]; // soft shadow folds
  highlights?: string[];
  details?: string[]; // front-only construction lines
  dots?: [number, number][]; // buttons, rivets
  band?: string; // darker band (waistband, cuffs, sole)
  hanger?: boolean;
  shoe?: boolean;
  /** Enlarge small items around their centre (cy) and set where the floor shadow sits. */
  fit?: { scale: number; cy: number; floor: number };
}

const HANGER_TOP = "M150 30 q0 -14 12 -14 q11 0 11 11 q0 9 -11 13 l-12 6";

const SHAPES: Record<ShapeKey, Shape> = {
  tee: {
    hanger: true,
    body: "M118 74 Q150 96 182 74 L224 88 L254 142 L226 156 L214 132 L214 322 Q150 332 86 322 L86 132 L74 156 L46 142 L76 88 Z",
    folds: ["M112 160 Q120 240 110 318", "M190 150 Q180 230 192 318", "M150 110 Q140 200 152 300"],
    highlights: ["M132 120 Q128 210 136 300"],
    details: ["M118 74 Q150 102 182 74", "M88 312 Q150 322 212 312", "M60 146 L82 136", "M240 146 L218 136"],
  },
  longsleeve: {
    hanger: true,
    body: "M118 74 Q150 96 182 74 L224 88 Q242 96 248 122 L264 300 L236 306 L218 156 L216 322 Q150 332 84 322 L82 156 L64 306 L36 300 L52 122 Q58 96 76 88 Z",
    folds: ["M110 170 Q118 250 108 318", "M192 160 Q182 240 194 318", "M242 170 Q246 240 250 296", "M58 170 Q54 240 50 296"],
    highlights: ["M134 120 Q128 210 138 300"],
    band: "M84 300 Q150 312 216 300 L216 322 Q150 332 84 322 Z",
    details: ["M118 74 Q150 102 182 74", "M40 284 L64 288", "M260 284 L236 288"],
  },
  hoodie: {
    hanger: true,
    under: "M110 80 Q104 36 150 30 Q196 36 190 80 Q150 100 110 80 Z",
    body: "M114 76 Q150 100 186 76 L226 88 Q244 96 250 122 L266 300 L238 306 L220 156 L218 322 Q150 332 82 322 L80 156 L62 306 L34 300 L50 122 Q56 96 74 88 Z",
    folds: ["M110 170 Q118 240 108 318", "M192 160 Q182 240 194 318", "M60 170 Q54 240 50 296"],
    highlights: ["M134 130 Q128 210 138 240"],
    band: "M82 300 Q150 312 218 300 L218 322 Q150 332 82 322 Z",
    details: ["M110 250 L190 250 L204 298 L96 298 Z", "M140 96 L136 150", "M160 96 L164 150"],
  },
  shirt: {
    hanger: true,
    body: "M120 72 L180 72 L224 88 Q242 96 248 122 L262 300 L236 306 L218 156 L216 326 Q150 336 84 326 L82 156 L64 306 L38 300 L52 122 Q58 96 76 88 Z",
    folds: ["M110 170 Q118 250 108 320", "M192 160 Q182 240 194 320"],
    highlights: ["M132 130 Q128 210 136 300"],
    details: ["M120 72 L138 106 L150 86 L162 106 L180 72", "M150 88 L150 330", "M100 130 L130 130 L130 162 L100 162 Z"],
    dots: [[156, 120], [156, 160], [156, 200], [156, 240], [156, 280]],
  },
  jacket: {
    hanger: true,
    body: "M116 72 L184 72 L228 88 Q246 96 252 124 L266 304 L238 310 L220 160 L220 330 L80 330 L80 160 L62 310 L34 304 L48 124 Q54 96 72 88 Z",
    folds: ["M106 190 Q112 260 104 326", "M196 190 Q188 260 196 326", "M58 180 Q52 250 48 300"],
    highlights: ["M128 150 Q124 230 130 320"],
    details: ["M116 72 L140 160 L150 128", "M184 72 L160 160 L150 128", "M150 128 L150 330", "M96 250 L132 250", "M168 250 L204 250"],
    dots: [[158, 190], [158, 250]],
  },
  blouse: {
    hanger: true,
    body: "M118 74 L150 122 L182 74 L226 90 Q244 100 250 130 L262 250 L238 256 L220 160 L222 318 Q150 336 78 318 L80 160 L62 256 L38 250 L50 130 Q56 100 74 90 Z",
    folds: ["M112 170 Q122 250 108 316", "M190 160 Q178 240 194 316", "M150 150 Q142 230 152 320"],
    highlights: ["M132 140 Q126 220 136 310"],
    details: ["M118 74 L150 122 L182 74"],
  },
  trousers: {
    body: "M96 68 L204 68 L208 90 L228 346 L170 350 L153 146 L147 146 L130 350 L72 346 L92 90 Z",
    folds: ["M112 160 Q118 260 104 344", "M190 160 Q184 260 196 344", "M150 146 L150 146"],
    highlights: ["M120 110 Q114 230 112 340", "M182 110 Q188 230 188 340"],
    band: "M96 68 L204 68 L206 88 L94 88 Z",
    details: ["M150 88 L150 140", "M150 140 Q140 136 138 118", "M98 100 Q116 106 120 90", "M202 100 Q184 106 180 90"],
  },
  jeans: {
    body: "M96 68 L204 68 L208 90 L228 346 L170 350 L153 146 L147 146 L130 350 L72 346 L92 90 Z",
    folds: ["M112 160 Q118 260 104 344", "M190 160 Q184 260 196 344", "M100 300 Q116 306 130 300", "M170 300 Q184 306 200 300"],
    highlights: ["M120 110 Q114 230 112 340", "M182 110 Q188 230 188 340"],
    band: "M96 68 L204 68 L206 88 L94 88 Z",
    details: ["M150 88 L150 138 Q140 138 136 120", "M98 100 Q118 108 122 90", "M202 100 Q182 108 178 90"],
    dots: [[122, 92], [178, 92], [150, 78]],
  },
  shorts: {
    fit: { scale: 1.35, cy: 177, floor: 272 },
    body: "M94 110 L206 110 L210 130 L226 238 L166 244 L153 180 L147 180 L134 244 L74 238 L90 130 Z",
    folds: ["M110 170 Q114 210 104 236", "M190 170 Q186 210 196 236"],
    highlights: ["M120 140 Q116 200 114 234"],
    band: "M94 110 L206 110 L208 128 L92 128 Z",
    details: ["M150 128 L150 172", "M96 140 Q116 146 120 130", "M204 140 Q184 146 180 130"],
  },
  skirt: {
    fit: { scale: 1, cy: 204, floor: 340 },
    body: "M104 80 L196 80 L200 98 L238 320 Q150 336 62 320 L100 98 Z",
    folds: ["M126 110 Q116 220 100 318", "M150 104 Q150 220 150 328", "M174 110 Q184 220 200 318"],
    highlights: ["M136 110 Q130 220 124 324", "M164 110 Q170 220 176 324"],
    band: "M104 80 L196 80 L198 98 L102 98 Z",
  },
  dress: {
    hanger: true,
    body: "M124 108 Q150 124 176 108 L182 150 Q176 176 180 192 L236 344 Q150 362 64 344 L120 192 Q124 176 118 150 Z",
    under: "M122 74 L128 112 L132 112 L126 74 Z M178 74 L172 112 L168 112 L174 74 Z",
    folds: ["M132 210 Q116 280 96 342", "M150 204 Q150 280 150 352", "M168 210 Q184 280 204 342"],
    highlights: ["M140 214 Q130 280 120 348", "M160 214 Q170 280 180 348"],
    details: ["M120 192 Q150 200 180 192"],
  },
  jumpsuit: {
    hanger: true,
    under: "M124 74 L128 96 L132 96 L128 74 Z M176 74 L172 96 L168 96 L172 74 Z",
    body: "M120 92 Q150 110 180 92 L196 104 L200 190 L216 346 L166 350 L153 230 L147 230 L134 350 L84 346 L100 190 L104 104 Z",
    folds: ["M114 240 Q118 300 106 344", "M188 240 Q184 300 196 344", "M150 120 Q146 160 150 186"],
    highlights: ["M126 200 Q120 280 118 340"],
    band: "M100 182 L200 182 L200 198 L100 198 Z",
  },
  sneaker: {
    fit: { scale: 1.05, cy: 245, floor: 306 },
    shoe: true,
    body: "M62 262 Q58 226 92 220 L150 212 Q176 194 198 190 L216 194 Q228 226 246 238 L264 250 Q278 258 276 272 L66 276 Z",
    band: "M58 272 L280 270 Q284 292 268 296 L72 298 Q56 296 58 272 Z",
    folds: ["M100 244 Q140 232 170 236"],
    highlights: ["M88 232 Q130 222 160 224"],
    details: ["M176 204 L196 226", "M186 200 L206 222", "M196 196 L214 216", "M92 262 Q150 256 250 260", "M232 240 Q248 246 256 262"],
  },
  boot: {
    fit: { scale: 1.05, cy: 206, floor: 318 },
    shoe: true,
    body: "M112 110 L182 110 L188 226 Q222 238 252 250 Q272 262 270 280 L98 284 L102 226 Z",
    band: "M94 280 L274 278 Q278 298 262 300 L100 302 Q90 300 94 280 Z",
    folds: ["M126 150 Q122 200 128 250", "M170 150 Q176 200 170 240"],
    highlights: ["M138 130 Q132 200 136 260"],
    details: ["M112 124 L182 124", "M184 150 L184 224"],
  },
  sandal: {
    fit: { scale: 1.2, cy: 262, floor: 300 },
    shoe: true,
    body: "M70 268 Q66 252 90 250 L250 248 Q278 250 276 266 Q270 280 250 280 L90 282 Q72 282 70 268 Z",
    band: "M68 278 L278 276 Q280 292 262 294 L84 296 Q66 294 68 278 Z",
    under: "M130 250 Q150 200 186 206 L196 250 L184 250 L176 218 Q156 216 142 250 Z M214 250 L222 214 L236 216 L230 250 Z",
    folds: [],
    details: [],
  },
  bag: {
    fit: { scale: 1, cy: 204, floor: 332 },
    under: "M112 150 Q112 84 150 84 Q188 84 188 150 L178 150 Q178 96 150 96 Q122 96 122 150 Z",
    body: "M84 150 L216 150 L232 324 L68 324 Z",
    folds: ["M110 170 Q104 250 98 318", "M190 170 Q196 250 202 318"],
    highlights: ["M130 164 Q126 250 122 318"],
    details: ["M84 176 L216 176", "M136 150 L136 176", "M164 150 L164 176"],
  },
  hat: {
    fit: { scale: 1.45, cy: 184, floor: 262 },
    body: "M104 196 Q106 138 150 134 Q194 138 196 196 L230 208 Q228 234 150 230 Q72 234 70 208 Z",
    folds: ["M126 150 Q120 176 122 198", "M174 150 Q180 176 178 198"],
    highlights: ["M136 146 Q132 170 134 196"],
    band: "M104 186 Q150 196 196 186 L196 200 Q150 208 104 200 Z",
  },
  scarf: {
    hanger: true,
    body: "M108 76 L192 76 L188 330 L158 330 L150 152 L142 330 L112 330 Z",
    folds: ["M122 110 Q128 220 124 326", "M178 110 Q172 220 176 326", "M150 90 Q150 120 150 150"],
    highlights: ["M132 100 Q136 220 132 326"],
    details: ["M114 330 L114 346 M122 330 L122 346 M130 330 L130 346 M138 330 L138 346", "M162 330 L162 346 M170 330 L170 346 M178 330 L178 346 M186 330 L186 346"],
  },
  belt: {
    fit: { scale: 1.1, cy: 216, floor: 282 },
    body: "M54 196 Q150 170 246 196 L246 216 Q150 190 54 216 Z M54 216 Q150 250 246 216 L246 236 Q150 270 54 236 Z",
    folds: [],
    highlights: ["M70 198 Q150 176 230 198"],
    details: ["M226 186 L262 186 L262 246 L226 246 Z", "M236 206 L252 206"],
    dots: [[100, 234], [124, 240], [148, 244]],
  },
  bra: {
    fit: { scale: 1.45, cy: 150, floor: 262 },
    body: "M84 168 Q94 122 146 152 L150 158 L154 152 Q206 122 216 168 Q212 206 176 212 L150 196 L124 212 Q88 206 84 168 Z",
    under: "M98 150 L112 84 L116 84 L104 150 Z M202 150 L188 84 L184 84 L196 150 Z",
    folds: ["M104 170 Q116 150 138 162", "M196 170 Q184 150 162 162"],
    highlights: ["M110 160 Q120 146 134 152"],
    band: "M80 198 Q150 214 220 198 L220 214 Q150 228 80 214 Z",
  },
  briefs: {
    fit: { scale: 1.45, cy: 194, floor: 272 },
    body: "M74 148 L226 148 L214 180 Q176 196 164 240 L136 240 Q124 196 86 180 Z",
    folds: ["M110 170 Q128 188 138 230", "M190 170 Q172 188 162 230"],
    highlights: ["M120 160 Q134 180 142 226"],
    band: "M74 148 L226 148 L222 162 L78 162 Z",
  },
  socks: {
    fit: { scale: 1, cy: 210, floor: 340 },
    body: "M96 90 L136 90 L136 252 Q136 284 170 292 L196 296 Q214 300 212 318 Q208 332 188 330 L134 324 Q98 316 96 280 Z M160 90 L200 90 L200 220 Q200 244 222 250 L240 254 Q256 258 254 274 Q250 288 232 286 L196 282 Q160 276 160 246 Z",
    folds: ["M110 120 Q114 200 110 260"],
    band: "M96 90 L136 90 L136 116 L96 116 Z M160 90 L200 90 L200 116 L160 116 Z",
  },
  swimsuit: {
    fit: { scale: 1.05, cy: 190, floor: 318 },
    hanger: true,
    body: "M118 88 L128 88 Q150 150 172 88 L182 88 Q192 170 198 220 Q178 268 164 304 L136 304 Q122 268 102 220 Q108 170 118 88 Z",
    folds: ["M124 180 Q132 240 140 296", "M176 180 Q168 240 160 296"],
    highlights: ["M134 170 Q138 230 144 290"],
    under: "M118 88 L124 76 L130 76 L128 88 Z M182 88 L176 76 L170 76 L172 88 Z",
  },
  bikini: {
    fit: { scale: 1.45, cy: 150, floor: 262 },
    body: "M94 170 Q102 130 144 156 L150 162 L156 156 Q198 130 206 170 Q202 202 174 206 L150 192 L126 206 Q98 202 94 170 Z",
    under: "M106 154 L120 96 L124 96 L112 154 Z M194 154 L180 96 L176 96 L188 154 Z",
    folds: ["M110 172 Q120 154 140 164"],
    highlights: ["M116 164 Q124 150 136 156"],
    details: ["M94 190 Q70 196 60 214", "M206 190 Q230 196 240 214"],
  },
};

function material(article: Article): "denim" | "knit" | "satin" | "plain" {
  const text = `${article.prod_name} ${article.description} ${article.product_type}`.toLowerCase();
  if (text.includes("denim") || article.product_type === "Jeans") return "denim";
  if (text.includes("knit") || text.includes("wool") || text.includes("rib") || article.product_type === "Sweater") return "knit";
  if (text.includes("satin") || text.includes("silk")) return "satin";
  return "plain";
}

export function shapeFor(article: Article): ShapeKey {
  return BY_TYPE[article.product_type] ?? BY_GROUP[article.product_group] ?? "tee";
}

export function GarmentArt({
  article,
  view = "front",
  className,
  backdrop = true,
}: {
  article: Article;
  view?: "front" | "back";
  className?: string;
  backdrop?: boolean;
}) {
  const uid = useId().replace(/:/g, "");
  if (article.image_url) {
    return <img className={className} src={article.image_url} alt={article.prod_name} loading="lazy" />;
  }
  const s = SHAPES[shapeFor(article)];
  const c = shadesFor(article.colour);
  const mat = material(article);
  const studioTop = mix("#f2f1ed", c.base, 0.06);
  const studioBottom = mix("#dcd9d1", c.base, 0.1);
  const lightFabric = ["White", "Off White", "Light Beige", "Yellow", "Light Pink", "Light Blue", "Beige"].includes(article.colour);
  const outline = lightFabric ? mix(c.base, "#000000", 0.25) : c.deep;
  const back = view === "back";
  const flip = back && s.shoe ? "translate(300 0) scale(-1 1)" : undefined;
  const id = (name: string) => `${name}-${uid}`;
  const fitTransform = s.fit
    ? `translate(150 ${s.fit.cy}) scale(${s.fit.scale}) translate(-150 -${s.fit.cy})`
    : undefined;

  return (
    <svg
      className={className}
      viewBox="0 -10 300 400"
      preserveAspectRatio="xMidYMid slice"
      role="img"
      aria-label={`${article.colour} ${article.product_type}${back ? ", back view" : ""}`}
    >
      <defs>
        <linearGradient id={id("studio")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={studioTop} />
          <stop offset="1" stopColor={studioBottom} />
        </linearGradient>
        <radialGradient id={id("floor")} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#000" stopOpacity="0.28" />
          <stop offset="1" stopColor="#000" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={id("fabric")} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor={c.shade} />
          <stop offset="0.28" stopColor={c.base} />
          <stop offset="0.42" stopColor={mat === "satin" ? c.highlight : c.light} />
          <stop offset="0.62" stopColor={c.base} />
          <stop offset="1" stopColor={c.deep} />
        </linearGradient>
        <linearGradient id={id("vshade")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity={mat === "satin" ? 0.22 : 0.1} />
          <stop offset="0.5" stopColor="#fff" stopOpacity="0" />
          <stop offset="1" stopColor="#000" stopOpacity="0.22" />
        </linearGradient>
        <pattern id={id("twill")} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(35)">
          <line x1="0" y1="0" x2="0" y2="6" stroke="#fff" strokeOpacity="0.16" strokeWidth="2" />
        </pattern>
        <pattern id={id("rib")} width="5" height="10" patternUnits="userSpaceOnUse">
          <line x1="1" y1="0" x2="1" y2="10" stroke="#000" strokeOpacity="0.14" strokeWidth="1.4" />
        </pattern>
        <clipPath id={id("clip")}>
          <path d={s.body} />
        </clipPath>
      </defs>

      {backdrop && <rect x="0" y="-10" width="300" height="400" fill={`url(#${id("studio")})`} />}
      {backdrop && (
        <ellipse cx="150" cy={s.fit?.floor ?? 360} rx={s.shoe ? 130 : 96} ry="12" fill={`url(#${id("floor")})`} />
      )}

      <g transform={fitTransform}>
      <g transform={flip}>
        {s.hanger && (
          <g fill="none" stroke="#8d8a84" strokeWidth="3" strokeLinecap="round">
            <path d={HANGER_TOP} />
            <path d="M150 36 L90 76 L210 76 Z" strokeLinejoin="round" />
          </g>
        )}
        {s.under && <path d={s.under} fill={shapeFor(article) === "hoodie" ? c.shade : c.deep} />}
        <path d={s.body} fill={`url(#${id("fabric")})`} />
        <g clipPath={`url(#${id("clip")})`}>
          {mat === "denim" && <rect x="0" y="0" width="300" height="400" fill={`url(#${id("twill")})`} />}
          {mat === "knit" && <rect x="0" y="0" width="300" height="400" fill={`url(#${id("rib")})`} />}
          <rect x="0" y="0" width="300" height="400" fill={`url(#${id("vshade")})`} />
          {s.band && <path d={s.band} fill={s.shoe ? "#f4f2ec" : c.shade} opacity={s.shoe ? 1 : 0.9} />}
          <g fill="none" strokeLinecap="round">
            {s.folds.map((d, i) => (
              <path key={`f${i}`} d={d} stroke="#000" strokeOpacity="0.16" strokeWidth="7" />
            ))}
            {(s.highlights ?? []).map((d, i) => (
              <path key={`h${i}`} d={d} stroke="#fff" strokeOpacity={mat === "satin" ? 0.32 : 0.14} strokeWidth="9" />
            ))}
          </g>
        </g>
        {s.shoe && s.band && <path d={s.band} fill="#f4f2ec" stroke="#b9b5ab" strokeWidth="1" />}
        <path d={s.body} fill="none" stroke={outline} strokeOpacity="0.55" strokeWidth="1.2" strokeLinejoin="round" />
        {!back && (
          <g fill="none" stroke={mat === "denim" ? "#c9a25a" : c.line} strokeOpacity={mat === "denim" ? 0.9 : 0.55}
             strokeWidth="1.3" strokeDasharray={mat === "denim" ? "3 2.5" : undefined} strokeLinecap="round" strokeLinejoin="round">
            {(s.details ?? []).map((d, i) => (
              <path key={`d${i}`} d={d} />
            ))}
          </g>
        )}
        {!back && (s.dots ?? []).map(([x, y], i) => (
          <circle key={`b${i}`} cx={x} cy={y} r="3.2" fill={mat === "denim" ? "#b88a3e" : c.highlight} stroke={c.line} strokeWidth="0.8" />
        ))}
      </g>
      </g>
    </svg>
  );
}
