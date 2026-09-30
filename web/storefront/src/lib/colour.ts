// Colour helpers for the garment renders.

export const COLOURS: Record<string, string> = {
  Black: "#222224", White: "#f3f2ee", "Off White": "#e9e3d6", "Light Beige": "#d8c6a6", Beige: "#cbb591",
  "Dark Blue": "#23345f", Blue: "#3b5ea6", "Light Blue": "#9ec1df", Grey: "#8d9095", "Dark Grey": "#4b4d51",
  Pink: "#e3a1b4", "Light Pink": "#efc8d3", Red: "#b3312d", "Dark Red": "#76222a", "Khaki green": "#6f7349",
  Green: "#3f7a51", Yellow: "#e2c046", Orange: "#d6782f", Brown: "#6c4b35", Purple: "#6a4b8e",
};

export function colourHex(name: string): string {
  return COLOURS[name] ?? "#9a9a96";
}

function toRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function toHex([r, g, b]: [number, number, number]): string {
  return "#" + [r, g, b].map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, "0")).join("");
}

/** Linear mix of two hex colours; t = 0 returns a, t = 1 returns b. */
export function mix(a: string, b: string, t: number): string {
  const x = toRgb(a);
  const y = toRgb(b);
  return toHex([x[0] + (y[0] - x[0]) * t, x[1] + (y[1] - x[1]) * t, x[2] + (y[2] - x[2]) * t]);
}

export function luminance(hex: string): number {
  const [r, g, b] = toRgb(hex).map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export interface Shades {
  base: string;
  light: string;
  highlight: string;
  shade: string;
  deep: string;
  line: string;
}

export function shadesFor(name: string): Shades {
  const base = colourHex(name);
  const dark = luminance(base) < 0.05;
  return {
    base,
    light: mix(base, "#ffffff", dark ? 0.22 : 0.28),
    highlight: mix(base, "#ffffff", dark ? 0.35 : 0.55),
    shade: mix(base, "#000000", dark ? 0.2 : 0.28),
    deep: mix(base, "#000000", dark ? 0.45 : 0.5),
    line: mix(base, "#000000", dark ? 0.6 : 0.42),
  };
}
