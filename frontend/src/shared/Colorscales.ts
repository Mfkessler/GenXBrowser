// src/shared/colorscales.ts
import * as d3 from "d3";

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
};

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
