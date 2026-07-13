// src/shared/colorscales.ts
import * as d3 from "d3";

/**
 * Plotly.js-compatible colorscale vector: an array of [stop, color] pairs
 * where stop is normalized to [0, 1]. Used both as documentation of the exact
 * intended gradient and as the source of truth for the D3 interpolator below.
 */
export type PlotlyColorStop = [number, string];

/**
 * Default Z-Score diverging scale: custom Blue-White-Red gradient
 * (inverted RdBu), zero anchored exactly at white (#f7f7f7).
 */
export const BLUE_WHITE_RED_PLOTLY_SCALE: PlotlyColorStop[] = [
  [0.0, "#053061"], // Extreme Down-regulation (Deep Blue)
  [0.15, "#2166ac"],
  [0.35, "#92c5de"],
  [0.5, "#f7f7f7"], // Zero Point (Neutral/White)
  [0.65, "#f4a582"],
  [0.85, "#b2182b"],
  [1.0, "#67001f"], // Extreme Up-regulation (Deep Red)
];

/** Classic microarray Green-Black-Red gradient, zero anchored at black. */
export const GREEN_BLACK_RED_PLOTLY_SCALE: PlotlyColorStop[] = [
  [0.0, "#00cc44"],
  [0.5, "#000000"],
  [1.0, "#ff3333"],
];

/**
 * Build a `(t: number) => string` interpolator (matching d3's
 * `interpolateXxx` shape) from a Plotly-style [stop, color] vector, so custom
 * gradients can be dropped into COLORSCALES alongside the built-in d3 scales.
 */
function fromPlotlyColorStops(stops: PlotlyColorStop[]): (t: number) => string {
  const scale = d3
    .scaleLinear<string>()
    .domain(stops.map(([stop]) => stop))
    .range(stops.map(([, color]) => color))
    .interpolate(d3.interpolateRgb)
    .clamp(true);
  return (t: number) => scale(t);
}

export const COLORSCALES = {
  VIRIDIS: d3.interpolateViridis,
  BLUES: d3.interpolateBlues,
  GREENS: d3.interpolateGreens,
  REDS: d3.interpolateReds,
  GREYS: d3.interpolateGreys,
  ORANGES: d3.interpolateOranges,
  PURPLES: d3.interpolatePurples,
  TURBO: d3.interpolateTurbo,
  INFERNO: d3.interpolateInferno,
  MAGMA: d3.interpolateMagma,
  PLASMA: d3.interpolatePlasma,
  CIVIDIS: d3.interpolateCividis,
  WARM: d3.interpolateWarm,
  COOL: d3.interpolateCool,
  CUBEHELIXDEFAULT: d3.interpolateCubehelixDefault,
  BUGN: d3.interpolateBuGn,
  BUPU: d3.interpolateBuPu,
  GNBU: d3.interpolateGnBu,
  ORRD: d3.interpolateOrRd,
  PUBUGN: d3.interpolatePuBuGn,
  PUBU: d3.interpolatePuBu,
  PURD: d3.interpolatePuRd,
  RDPU: d3.interpolateRdPu,
  YLGNBU: d3.interpolateYlGnBu,
  YLGN: d3.interpolateYlGn,
  YLORBR: d3.interpolateYlOrBr,
  YLORRD: d3.interpolateYlOrRd,
  // Diverging (tri-color, zero-centered) scales
  RDBU: d3.interpolateRdBu,
  RDYLBU: d3.interpolateRdYlBu,
  RDYLGN: d3.interpolateRdYlGn,
  PIYG: d3.interpolatePiYG,
  PRGN: d3.interpolatePRGn,
  PUOR: d3.interpolatePuOr,
  RDGY: d3.interpolateRdGy,
  SPECTRAL: d3.interpolateSpectral,
  BRBG: d3.interpolateBrBG,
  // Custom diverging scales (exact publication-grade gradients)
  BLUEWHITERED: fromPlotlyColorStops(BLUE_WHITE_RED_PLOTLY_SCALE),
  GREENBLACKRED: fromPlotlyColorStops(GREEN_BLACK_RED_PLOTLY_SCALE),
};

/**
 * Friendly display labels for ColorScale dropdown entries whose key doesn't
 * beautify well on its own (single all-caps word). Falls back to
 * `beautifyLabel(key)` for anything not listed here.
 */
export const COLORSCALE_LABELS: Partial<Record<keyof typeof COLORSCALES, string>> = {
  BLUEWHITERED: "BlueWhiteRed (Default)",
  GREENBLACKRED: "GreenBlackRed",
  PIYG: "ColorblindFriendly (PiYG)",
  BRBG: "BrBG",
};

/**
 * Keys in COLORSCALES that are diverging (tri-color, neutral-midpoint) scales.
 * These are the only scales considered safe for zero-centered data such as
 * Z-Scores, where the neutral middle color must represent 0.
 */
export const DIVERGING_COLORSCALES = new Set<string>([
  "BLUEWHITERED",
  "GREENBLACKRED",
  "CUBEHELIXDEFAULT",
  "RDBU",
  "RDYLBU",
  "RDYLGN",
  "PIYG",
  "PRGN",
  "PUOR",
  "RDGY",
  "SPECTRAL",
  "BRBG",
]);

export const DEFAULT_DIVERGING_COLORSCALE = "BLUEWHITERED";


/**
 * Compute a symmetric, zero-centered [min, max] domain from raw data bounds:
 * bound = max(|min|, |max|); domain = [-bound, bound].
 * Used for Z-Score color mapping so a diverging scale's neutral midpoint
 * always lands exactly on 0, regardless of data skew.
 */
export function getZeroCenteredDomain(minVal: number, maxVal: number): [number, number] {
  const safeMin = Number.isFinite(minVal) ? minVal : 0;
  const safeMax = Number.isFinite(maxVal) ? maxVal : 0;
  const bound = Math.max(Math.abs(safeMin), Math.abs(safeMax)) || 1;
  return [-bound, bound];
}

/**
 * Maximally distinct color palette using CIE Lab color space principles.
 * Colors are chosen to be as perceptually different as possible.
 * Each color has distinct hue, saturation, and lightness.
 */
const DISTINCT_COLORS = [
  // Primary distinct hues - maximum saturation difference
  "#e6194b",  // Vivid Red
  "#3cb44b",  // Vivid Green
  "#4363d8",  // Vivid Blue
  "#f58231",  // Vivid Orange
  "#911eb4",  // Vivid Purple
  "#42d4f4",  // Vivid Cyan
  "#f032e6",  // Vivid Magenta
  "#bfef45",  // Vivid Lime
  "#fabed4",  // Pink
  "#469990",  // Teal
  "#dcbeff",  // Lavender
  "#9a6324",  // Brown
  "#fffac8",  // Beige/Cream
  "#800000",  // Maroon
  "#aaffc3",  // Mint
  "#808000",  // Olive
  "#ffd8b1",  // Apricot
  "#000075",  // Navy
  "#a9a9a9",  // Gray
  "#000000",  // Black
  // Extended palette - still distinct
  "#e6beff",  // Light Violet
  "#aa6e28",  // Chocolate
  "#ffffd8",  // Light Yellow
  "#7f0000",  // Dark Red
  "#17b584",  // Sea Green
  "#6a3d9a",  // Dark Purple
  "#ff7f50",  // Coral
  "#1e90ff",  // Dodger Blue
  "#228b22",  // Forest Green
  "#ff1493",  // Deep Pink
  "#00ced1",  // Dark Turquoise
  "#8b4513",  // Saddle Brown
  "#9932cc",  // Dark Orchid
  "#ffa500",  // Orange
  "#2f4f4f",  // Dark Slate Gray
  "#7fff00",  // Chartreuse
  "#dc143c",  // Crimson
  "#00bfff",  // Deep Sky Blue
  "#8b008b",  // Dark Magenta
  "#b8860b",  // Dark Goldenrod
  // Additional distinct hues to delay rainbow fallback
  "#4682b4",  // Steel Blue
  "#daa520",  // Goldenrod
  "#5f9ea0",  // Cadet Blue
  "#9acd32",  // Yellow Green
  "#cd5c5c",  // Indian Red
  "#20b2aa",  // Light Sea Green
  "#ff69b4",  // Hot Pink
  "#bdb76b",  // Dark Khaki
  "#483d8b",  // Dark Slate Blue
  "#008080",  // Classic Teal
  "#b22222",  // Firebrick
  "#7cfc00",  // Lawn Green
  "#ba55d3",  // Medium Orchid
  "#ff8c00",  // Dark Orange
  "#4169e1",  // Royal Blue
  "#3cb371",  // Medium Sea Green
  "#c71585",  // Medium Violet Red
  "#48d1cc",  // Medium Turquoise
  "#cd853f",  // Peru
  "#556b2f",  // Dark Olive Green
];

/**
 * Generate a categorical color palette with enough distinct colors.
 * Uses hand-picked maximally distinct colors for better differentiation.
 * For n > 40: falls back to golden ratio rainbow interpolation.
 */
export function getCategoricalColors(n: number): string[] {
  if (n <= 0) return [];
  
  if (n <= DISTINCT_COLORS.length) {
    return DISTINCT_COLORS.slice(0, n);
  } else {
    // For many categories, use quantized rainbow with golden ratio offset for max distinction
    const colors: string[] = [];
    const goldenRatio = 0.618033988749895;
    let hue = 0;
    for (let i = 0; i < n; i++) {
      hue = (hue + goldenRatio) % 1;
      colors.push(d3.interpolateRainbow(hue));
    }
    return colors;
  }
}
