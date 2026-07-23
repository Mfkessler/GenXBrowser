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

function relativeLuminance(red: number, green: number, blue: number): number {
  const channels = [red, green, blue].map((channel) => {
    const normalized = channel / 255;
    return normalized <= 0.04045
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4;
  });
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}

const categoricalPaletteCache = new Map<number, string[]>();
type CategoricalColorCandidate = {
  color: string;
  lab: d3.LabColor;
};

const categoricalColorCandidates: CategoricalColorCandidate[] = [];
for (let red = 0; red <= 255; red += 17) {
  for (let green = 0; green <= 255; green += 17) {
    for (let blue = 0; blue <= 255; blue += 17) {
      const color = d3.rgb(red, green, blue).formatHex();
      const lab = d3.lab(color);
      const chroma = Math.hypot(lab.a, lab.b);
      if (lab.l >= 35 && lab.l <= 70 && chroma >= 40 &&
          1.05 / (relativeLuminance(red, green, blue) + 0.05) >= 3) {
        categoricalColorCandidates.push({ color, lab });
      }
    }
  }
}

function labDistance(first: d3.LabColor, second: d3.LabColor): number {
  return Math.hypot(first.l - second.l, first.a - second.a, first.b - second.b);
}

function createMaximinPalette(count: number, startIndex: number): CategoricalColorCandidate[] {
  const selected = [categoricalColorCandidates[startIndex]];
  while (selected.length < count) {
    let bestCandidate: CategoricalColorCandidate | undefined;
    let bestDistance = -Infinity;
    for (const candidate of categoricalColorCandidates) {
      if (selected.includes(candidate)) continue;
      const nearestDistance = Math.min(...selected.map((color) => labDistance(candidate.lab, color.lab)));
      if (nearestDistance > bestDistance) {
        bestCandidate = candidate;
        bestDistance = nearestDistance;
      }
    }
    if (!bestCandidate) break;
    selected.push(bestCandidate);
  }
  return selected;
}

function minimumPaletteDistance(palette: CategoricalColorCandidate[]): number {
  let minimum = Infinity;
  for (let index = 0; index < palette.length; index++) {
    for (let otherIndex = index + 1; otherIndex < palette.length; otherIndex++) {
      minimum = Math.min(minimum, labDistance(palette[index].lab, palette[otherIndex].lab));
    }
  }
  return minimum;
}

/**
 * Generate a set-specific palette by choosing the strongest result from
 * deterministic multi-start farthest-first CIE Lab searches.
 */
export function getCategoricalColors(n: number): string[] {
  if (n <= 0) return [];

  const cached = categoricalPaletteCache.get(n);
  if (cached) return [...cached];

  const count = Math.min(n, categoricalColorCandidates.length);
  const attemptCount = Math.min(12, categoricalColorCandidates.length);
  const stride = Math.ceil(categoricalColorCandidates.length / attemptCount);
  let bestPalette: CategoricalColorCandidate[] = [];
  let bestDistance = -Infinity;

  for (let startIndex = 0; startIndex < categoricalColorCandidates.length; startIndex += stride) {
    const palette = createMaximinPalette(count, startIndex);
    const minimumDistance = minimumPaletteDistance(palette);
    if (minimumDistance > bestDistance) {
      bestPalette = palette;
      bestDistance = minimumDistance;
    }
  }

  const colors = bestPalette.map((candidate) => candidate.color);
  for (let index = colors.length; index < n; index++) {
    colors.push(d3.hsl((index * 137.50776405003785) % 360, 0.72, 0.45).formatHex());
  }
  categoricalPaletteCache.set(n, colors);
  return [...colors];
}
