export interface CardBoxSize {
  width: number;
  height: number;
}

export function readCardBoxSize(rect: Pick<DOMRectReadOnly, "width" | "height">): CardBoxSize | null {
  const width = Math.round(rect.width);
  const height = Math.round(rect.height);

  if (width <= 0 || height <= 0) {
    return null;
  }

  return { width, height };
}

export function getMirroredCardStyle(size: CardBoxSize | null): Record<string, string> | undefined {
  if (!size) {
    return undefined;
  }

  return {
    minHeight: `${size.height}px`,
    height: `${size.height}px`,
  };
}

/**
 * Subtracts the occupied height of dynamically-growing regions (e.g. a dataset
 * card's filter-chain/ID-filter chip rows) from a card's total measured height,
 * so mirrored sizing (see `getMirroredCardStyle`) reflects only the card's
 * structural/initialization size and never grows as chips are appended.
 */
export function subtractDynamicRegionsHeight(totalHeight: number, dynamicRegionHeights: number[]): number {
  const dynamicTotal = dynamicRegionHeights.reduce((sum, height) => sum + Math.max(0, height), 0);
  return Math.max(0, totalHeight - dynamicTotal);
}

/** Full occupied height of an element (border-box height + vertical margins), used to
 *  measure how much a dynamic region contributes to its parent's overall height. */
export function measureOccupiedHeight(rect: Pick<DOMRectReadOnly, "height">, style: Pick<CSSStyleDeclaration, "marginTop" | "marginBottom">): number {
  const marginTop = parseFloat(style.marginTop) || 0;
  const marginBottom = parseFloat(style.marginBottom) || 0;
  return rect.height + marginTop + marginBottom;
}